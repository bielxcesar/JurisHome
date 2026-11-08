import base64
import hashlib
import hmac
import os
import re
import time
from io import BytesIO
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from auth.sessions import (consumir_desafio, consumir_totp, criar_refresh, renovar_sessao,
    salvar_refresh, apagar_cookies)
from services import tentativas_auth as limites_auth
from auth.security import _decodificar_token
from pydantic import BaseModel, Field, field_validator, model_validator
from services.validacao import ModeloSeguro, nome_pessoa, email_valido, nova_senha, area_interesse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.security import (
    cifrar_segredo_2fa, criar_access_token, criar_token_configuracao_2fa, criar_token_nova_senha, criar_token_recuperacao_senha, criar_token_2fa_pendente, decifrar_segredo_2fa,
    decodificar_token_configuracao_2fa, decodificar_token_nova_senha, decodificar_token_recuperacao_senha, decodificar_token_2fa_pendente, get_current_user, get_current_user_optional,
    hash_senha,verificar_senha,
)
from database import get_db
from feedback_database import get_feedback_db
from model.models import TipoUsuario, Usuario, JuridleRodada, JuridleDia, JuridleQuestaoUso, ConteudoLeitura, CategoriaAcesso
from services.auditoria import registrar_auditoria
from services.direitos_titular import (anonimizar_feedbacks_atendimento,anonimizar_feedbacks_legados,anonimizar_usuario,)
from services.lgpd import TERMOS_VERSAO

router = APIRouter(prefix="/api", tags=["Autenticação e usuários"])

TENTATIVAS_ANTES_DO_BLOQUEIO = 6
MINUTOS_DE_BLOQUEIO = 8
JANELA_TOTP = 2
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class CadastroUsuario(ModeloSeguro):
    nome: Annotated[str, Field(min_length=2, max_length=40)]
    sobrenome: Annotated[str, Field(min_length=2, max_length=50)]
    interesse: Annotated[str, Field(max_length=100)]
    email: Annotated[str, Field(max_length=150)]
    senha: Annotated[str, Field(min_length=8, max_length=25)]
    confirmar_senha: Annotated[str, Field(min_length=8, max_length=25)]
    consentimento_lgpd: Annotated[bool, Field(strict=True)]

    @property
    def nome_completo(self):
        return f'{self.nome} {self.sobrenome}'

    @model_validator(mode='after')
    def validar_confirmacao_senha(self):
        if self.senha != self.confirmar_senha:
            raise ValueError('As senhas não conferem.')
        return self

    @field_validator('nome', 'sobrenome')
    @classmethod
    def limpar_texto(cls, valor, info):
        return nome_pessoa(valor, 40 if info.field_name == 'nome' else 50)

    @field_validator('email')
    @classmethod
    def validar_email(cls, valor):
        return email_valido(valor)

    @field_validator('interesse')
    @classmethod
    def validar_interesse(cls, valor):
        return area_interesse(valor)

    @field_validator('senha')
    @classmethod
    def validar_senha(cls, valor):
        return nova_senha(valor)


class Credenciais(ModeloSeguro):
    email: Annotated[str, Field(max_length=150)]
    senha: Annotated[str, Field(min_length=1, max_length=72)]

    @field_validator("email")
    @classmethod
    def limpar_email(cls, valor: str) -> str:
        return email_valido(valor)


class Codigo2FA(ModeloSeguro):
    desafio_token: Annotated[str, Field(min_length=20, max_length=8192)]
    codigo: Annotated[str, Field(pattern=r"^\d{6}$")]
    lembrar_conectado: Annotated[bool, Field(strict=True)] = False


class InicioRecuperacaoSenha(ModeloSeguro):
    email: Annotated[str, Field(max_length=150)]

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        return email_valido(valor)


class ConfirmacaoRecuperacaoSenha(InicioRecuperacaoSenha):
    desafio_token: Annotated[str, Field(min_length=20, max_length=8192)]
    codigo: Annotated[str, Field(pattern=r"^\d{6}$")]


class NovaSenhaRecuperacao(ModeloSeguro):
    token_redefinicao: Annotated[str, Field(min_length=20, max_length=8192)]
    nova_senha: Annotated[str, Field(min_length=8, max_length=25)]
    confirmar_senha: Annotated[str, Field(min_length=8, max_length=25)]

    @field_validator("nova_senha")
    @classmethod
    def validar_nova_senha(cls, valor: str) -> str:
        return nova_senha(valor)


class AtualizacaoPerfil(ModeloSeguro):
    nome: Annotated[str | None, Field(default=None, min_length=2, max_length=100)] = None

    @field_validator('nome')
    @classmethod
    def validar_nome(cls, valor):
        return nome_pessoa(valor) if valor is not None else None


class AtualizacaoSenha(ModeloSeguro):
    senha_atual: Annotated[str, Field(min_length=1, max_length=72)]
    nova_senha: Annotated[str, Field(min_length=8, max_length=25)]

    @field_validator("nova_senha")
    @classmethod
    def validar_nova_senha(cls, valor: str) -> str:
        return nova_senha(valor)


class SolicitacaoAnonimizacao(ModeloSeguro):
    senha: Annotated[str, Field(min_length=1, max_length=72)]
    confirmacao: Literal["ANONIMIZAR"]


def serializar_usuario(usuario: Usuario) -> dict:
    return {
        "uuid": usuario.uuid,
        "nome": usuario.nome,
        "email": usuario.email,
        "tipo_usuario": usuario.tipo_usuario.value,
        "is_2fa_enabled": usuario.is_2fa_enabled,
        "consentimento_lgpd": usuario.consentimento_lgpd,
    }


def _agora_sem_fuso() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _usuario_bloqueado(usuario: Usuario, agora: datetime | None = None) -> bool:
    limite = usuario.bloqueado_ate
    if not limite:
        return False
    if limite.tzinfo is not None:
        return limite > datetime.now(timezone.utc)
    return limite > (agora or _agora_sem_fuso())


def _registrar_falha_autenticacao(usuario: Usuario, agora: datetime | None = None) -> None:
    agora = agora or _agora_sem_fuso()
    if usuario.ultima_falha_login and usuario.ultima_falha_login <= agora - timedelta(minutes=8):
        usuario.tentativas_login_falhas = 0
    usuario.tentativas_login_falhas += 1
    usuario.ultima_falha_login = agora
    if usuario.tentativas_login_falhas >= TENTATIVAS_ANTES_DO_BLOQUEIO:
        usuario.bloqueado_ate = agora + timedelta(minutes=MINUTOS_DE_BLOQUEIO)
        usuario.tentativas_login_falhas = 0


def _salvar_cookie_de_sessao(response: Response, token: str, lembrar_conectado: bool = False, db: Session | None = None, *, apenas_acesso: bool = False) -> None:
    response.set_cookie(
        key="jurishome_access_token",
        value=token,
        max_age=30 * 60 if lembrar_conectado else None,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )
    if apenas_acesso:
        return
    if lembrar_conectado:
        if db is None:
            raise RuntimeError("Renovação de sessão exige banco de dados.")
        refresh = criar_refresh(db, _decodificar_token(token)["sid"])
        db.commit()
        salvar_refresh(response, refresh, 14 * 24 * 60 * 60)
    else:
        response.delete_cookie("jurishome_refresh_token", path="/")


def _verificar_totp(segredo: str, codigo: str) -> bool:
    try:
        import pyotp
    except ImportError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependências do 2FA ausentes no servidor. Na raiz do projeto, execute 'python -m pip install -r requirements.txt' e reinicie a aplicação.",
        ) from erro
    # Aceita até dois intervalos de diferença para tolerar pequenos desvios
    # entre o relógio do servidor local e o telefone do usuário.
    return pyotp.TOTP(segredo).verify(codigo, valid_window=JANELA_TOTP)


def gerar_qr_code(uri_autenticador: str) -> str:
    try:
        import qrcode
    except ImportError as erro:
        raise RuntimeError("Dependência para gerar o QR Code indisponível.") from erro

    imagem = qrcode.make(uri_autenticador)
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    dados = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{dados}"


def preparar_configuracao_2fa(usuario: Usuario, db: Session, *, commit: bool = True) -> dict:
    try:
        import pyotp

        if usuario.totp_secret and not usuario.is_2fa_enabled:
            # Enquanto a ativação estiver pendente, preserve o mesmo segredo.
            # Gerar outro valor a cada login invalida o QR já escaneado.
            segredo = decifrar_segredo_2fa(usuario.totp_secret)
        else:
            segredo = pyotp.random_base32()
            usuario.totp_secret = cifrar_segredo_2fa(segredo)
            usuario.is_2fa_enabled = False
            if commit:
                db.commit()
        uri_autenticador = pyotp.TOTP(segredo).provisioning_uri(name=usuario.email, issuer_name="JurisHome")
        qr_code = gerar_qr_code(uri_autenticador)
    except (ImportError, RuntimeError, ValueError) as erro:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependências do 2FA ausentes no servidor. Instale requirements.txt no mesmo ambiente Python do Uvicorn e reinicie a aplicação.",
        ) from erro

    return {
        "requer_configuracao_2fa": True,
        "configuracao_token": criar_token_configuracao_2fa(usuario),
        "segredo": segredo,
        "qr_code": qr_code,
        "mensagem": "Configure o aplicativo autenticador para concluir o cadastro.",
    }

class PedidoReset2FA(ModeloSeguro):
    email: Annotated[str, Field(max_length=150)]
    senha: Annotated[str, Field(min_length=1, max_length=72)]

    @field_validator('email')
    @classmethod
    def validar_email(cls, valor):
        return email_valido(valor)

@router.post("/solicitar-reset-2fa")
def solicitar_reset_2fa(dados: PedidoReset2FA, db: Session = Depends(get_db), request: Request = None):
    baldes = limites_auth.preparar(db, request, dados.email)
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).populate_existing().with_for_update().first()
    limites_auth.exigir_liberado(baldes, usuario)
    
    confere = verificar_senha(dados.senha, usuario.senha_hash if usuario and usuario.senha_hash else _DUMMY_PASSWORD_HASH)
    if not usuario or not usuario.senha_hash or not confere:
        limites_auth.falhar(baldes)
        if usuario:
            _registrar_falha_autenticacao(usuario)
        registrar_auditoria(db, acao='autenticacao_credenciais', recurso_tipo='sessao', usuario=usuario,
            resultado='falha', detalhes={'motivo':'credenciais_invalidas'}, commit=True)
        limites_auth.exigir_liberado(baldes, usuario)
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    
    if not usuario.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="Este usuário não possui 2FA ativo.")

    from model.models import FeedbackAtendimento
    import uuid
    
    pedido_existente = db.query(FeedbackAtendimento).filter(
        FeedbackAtendimento.usuario_id == str(usuario.uuid),
        FeedbackAtendimento.tipo == "Recuperacao 2FA",
        FeedbackAtendimento.status == "Recebido"
    ).first()

    if pedido_existente:
        return {"mensagem": "Você já possui uma solicitação em andamento. Aguarde o suporte."}

    protocolo_gerado = f"REQ-{str(uuid.uuid4())[:8].upper()}"
    novo_chamado = FeedbackAtendimento(
        id=str(uuid.uuid4()),
        protocolo=protocolo_gerado,
        usuario_id=str(usuario.uuid),
        usuario_nome=usuario.nome,
        usuario_email=usuario.email,
        tipo="Recuperacao 2FA",
        assunto="Perda de acesso ao Autenticador",
        mensagem="O usuário confirmou a senha e solicita o reset do token 2FA.",
        status="Recebido",
        prioridade="Alta"
    )
    
    db.add(novo_chamado)
    db.commit()
    
    return {"mensagem": "Solicitação enviada com sucesso! O suporte analisará o caso."}

@router.post("/auth/cadastro", status_code=status.HTTP_201_CREATED)
async def cadastrar_usuario(
    dados: CadastroUsuario,
    response: Response,
    db: Session = Depends(get_db),
):
    if not dados.consentimento_lgpd:
        registrar_auditoria(
            db,
            acao="cadastro",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "termo_nao_aceito", "versao_termos": TERMOS_VERSAO},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="É necessário aceitar o Termo de Aceite e declarar ciência da Política de Privacidade.",
        )
    # A verificação de duplicidade ocorre depois do mesmo trabalho de hash usado
    # no caminho de sucesso, reduzindo diferenças observáveis no tempo da resposta.
    senha_hash = hash_senha(dados.senha)
    if db.query(Usuario.uuid).filter(func.lower(Usuario.email) == dados.email).first():
        registrar_auditoria(
            db,
            acao="cadastro",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "email_ja_cadastrado"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível a finalização do cadastro.",
        )

    usuario = Usuario(
        nome=dados.nome_completo,
        especialidade_juridica=dados.interesse,
        email=dados.email,
        senha_hash=senha_hash,
        tipo_usuario=TipoUsuario.ESTUDANTE,
        consentimento_lgpd=True,
        data_consentimento=_agora_sem_fuso(),
        versao_termos=TERMOS_VERSAO,
    )
    db.add(usuario)
    try:
        db.flush()
        configuracao = preparar_configuracao_2fa(usuario, db, commit=False)
        registrar_auditoria(
            db,
            acao="cadastro",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="sucesso",
            usuario=usuario,
            detalhes={"versao_termos": TERMOS_VERSAO, "requer_2fa": True},
        )
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        registrar_auditoria(
            db,
            acao="cadastro",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "conflito_de_cadastro"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível a finalização do cadastro.",
        ) from erro
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return configuracao


# Hash fictício para aproximar o custo de e-mails existentes e inexistentes.
_DUMMY_PASSWORD_HASH = hash_senha('ComparacaoFicticia!123')


@router.get('/auth/limite')
def estado_limite(request: Request, db: Session = Depends(get_db)):
    return limites_auth.estado_origem(db, request)


@router.post('/auth/login')
def login(dados: Credenciais, response: Response, db: Session = Depends(get_db), request: Request = None):
    baldes = limites_auth.preparar(db, request, dados.email)
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).populate_existing().with_for_update().first()
    limites_auth.exigir_liberado(baldes, usuario)
    senha_confere = verificar_senha(dados.senha, usuario.senha_hash if usuario and usuario.senha_hash else _DUMMY_PASSWORD_HASH)
    if not usuario or not usuario.senha_hash or not senha_confere:
        limites_auth.falhar(baldes)
        if usuario:
            _registrar_falha_autenticacao(usuario)
        registrar_auditoria(db, acao='autenticacao_credenciais', recurso_tipo='sessao',
            recurso_id=usuario.uuid if usuario else None, resultado='falha', usuario=usuario,
            detalhes={'motivo':'credenciais_invalidas'})
        db.commit()
        limites_auth.exigir_liberado(baldes, usuario)
        raise HTTPException(401, 'E-mail ou senha inválidos.', headers={'WWW-Authenticate':'Bearer'})
    # Senha correta não limpa os erros anteriores: só o MFA completo faz isso.
    registrar_auditoria(db, acao='autenticacao_credenciais', recurso_tipo='sessao',
        recurso_id=usuario.uuid, resultado='sucesso', usuario=usuario, detalhes={'etapa_seguinte':'2fa'})
    db.commit()
    if not usuario.is_2fa_enabled or not usuario.totp_secret:
        return preparar_configuracao_2fa(usuario, db)
    return {'requer_2fa':True, 'desafio_token':criar_token_2fa_pendente(usuario)}


@router.post("/auth/2fa/validar")
def validar_2fa(dados: Codigo2FA, response: Response, db: Session = Depends(get_db), request: Request = None):
    try:
        usuario_uuid = decodificar_token_2fa_pendente(dados.desafio_token)
    except ValueError as erro:
        baldes = limites_auth.preparar(db, request)
        limites_auth.falhar(baldes)
        registrar_auditoria(
            db,
            acao="autenticacao_2fa",
            recurso_tipo="sessao",
            resultado="falha",
            detalhes={"motivo": "desafio_invalido_ou_expirado"},
            commit=True,
        )
        limites_auth.exigir_liberado(baldes)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    baldes = limites_auth.preparar(db, request, usuario.email if usuario else None)
    if usuario:
        usuario = db.query(Usuario).filter_by(uuid=usuario_uuid).populate_existing().with_for_update().one()
    limites_auth.exigir_liberado(baldes, usuario)
    if not usuario or not usuario.is_2fa_enabled or not usuario.totp_secret:
        registrar_auditoria(
            db,
            acao="autenticacao_2fa",
            recurso_tipo="sessao",
            recurso_id=usuario_uuid,
            resultado="falha",
            detalhes={"motivo": "configuracao_invalida"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Configuração de duas etapas inválida.")
    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
        limites_auth.falhar(baldes)
        registrar_auditoria(
            db,
            acao="autenticacao_2fa",
            recurso_tipo="sessao",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "codigo_invalido"},
            commit=True,
        )
        limites_auth.exigir_liberado(baldes, usuario)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de autenticação inválido. Confira se data e hora automáticas estão ativadas no celular.",
        )

    consumir_desafio(db, dados.desafio_token, usuario, "2fa_pendente")
    consumir_totp(db, usuario, segredo, dados.codigo, JANELA_TOTP)
    limites_auth.concluir(baldes)
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    token = criar_access_token(usuario, dados.lembrar_conectado)
    _salvar_cookie_de_sessao(response, token, dados.lembrar_conectado, db)
    registrar_auditoria(
        db,
        acao="autenticacao_2fa",
        recurso_tipo="sessao",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
        commit=True,
    )
    return {
        "autenticado": True,
        "usuario": serializar_usuario(usuario),
    }


@router.post("/auth/recuperacao/iniciar")
def iniciar_recuperacao_senha(dados: InicioRecuperacaoSenha):
    email_hash = hashlib.sha256(dados.email.encode("utf-8")).hexdigest()
    return {
        "desafio_token": criar_token_recuperacao_senha(email_hash),
        "mensagem": "Se a conta estiver cadastrada, confirme o código do aplicativo autenticador.",
    }


@router.post("/auth/recuperacao/validar")
def validar_recuperacao_senha(dados: ConfirmacaoRecuperacaoSenha, db: Session = Depends(get_db), request: Request = None):
    resposta_invalida = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível confirmar os dados. Confira o e-mail e o código do autenticador.",
    )
    try:
        hash_esperado = decodificar_token_recuperacao_senha(dados.desafio_token)
    except ValueError as erro:
        raise resposta_invalida from erro

    hash_informado = hashlib.sha256(dados.email.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(hash_esperado, hash_informado):
        raise resposta_invalida

    baldes = limites_auth.preparar(db, request, dados.email)
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).populate_existing().with_for_update().first()
    limites_auth.exigir_liberado(baldes, usuario)
    if (
        not usuario
        or not usuario.is_2fa_enabled
        or not usuario.totp_secret
        or _usuario_bloqueado(usuario)
    ):
        limites_auth.falhar(baldes)
        db.commit()
        limites_auth.exigir_liberado(baldes)
        raise resposta_invalida

    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro

    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
        limites_auth.falhar(baldes)
        registrar_auditoria(
            db,
            acao="recuperacao_senha",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "codigo_invalido"},
        )
        db.commit()
        limites_auth.exigir_liberado(baldes, usuario)
        raise resposta_invalida

    consumir_desafio(db, dados.desafio_token, usuario, "recuperacao_senha")
    consumir_totp(db, usuario, segredo, dados.codigo, JANELA_TOTP)
    limites_auth.concluir(baldes)
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    registrar_auditoria(
        db,
        acao="recuperacao_senha",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
    )
    db.commit()
    return {"token_redefinicao": criar_token_nova_senha(usuario)}


@router.post("/auth/recuperacao/alterar")
def alterar_senha_recuperada(dados: NovaSenhaRecuperacao, db: Session = Depends(get_db)):
    invalida = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A autorização para alterar a senha expirou. Inicie a recuperação novamente.",
    )
    if dados.nova_senha != dados.confirmar_senha:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="As senhas não conferem.")
    try:
        usuario_uuid, emitido_em = decodificar_token_nova_senha(dados.token_redefinicao)
    except ValueError as erro:
        raise invalida from erro

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if not usuario:
        raise invalida
    if usuario.token_validos_apos:
        limite = usuario.token_validos_apos
        if limite.tzinfo is None:
            limite = limite.replace(tzinfo=timezone.utc)
        if emitido_em <= limite.timestamp():
            raise invalida

    consumir_desafio(db, dados.token_redefinicao, usuario, "nova_senha")
    usuario.senha_hash = hash_senha(dados.nova_senha)
    usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
    registrar_auditoria(
        db,
        acao="senha_redefinida",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
    )
    db.commit()
    return {"mensagem": "Senha alterada com sucesso. Entre com a nova senha."}


@router.get("/usuarios/me")
def consultar_me(usuario: Usuario = Depends(get_current_user)):
    return serializar_usuario(usuario)


@router.put("/usuarios/me")
async def atualizar_me(
    dados: AtualizacaoPerfil,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dados_atualizados = dados.model_dump(exclude_unset=True)
    for campo in ("nome",):
        if campo in dados_atualizados:
            valor = getattr(dados, campo)
            setattr(usuario, campo, valor.strip() if isinstance(valor, str) else valor)

    registrar_auditoria(
        db,
        acao="perfil_alterado",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
        detalhes={"campos_alterados": sorted(dados_atualizados.keys())},
    )
    db.commit()
    db.refresh(usuario)
    return serializar_usuario(usuario)


@router.put("/usuarios/me/senha")
def atualizar_senha(
    dados: AtualizacaoSenha,
    response: Response,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Troca a senha e invalida as sessões emitidas antes da alteração."""
    if not usuario.senha_hash or not verificar_senha(dados.senha_atual, usuario.senha_hash):
        registrar_auditoria(
            db,
            acao="senha_alterada",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "senha_atual_incorreta"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A senha atual não confere.")
    if verificar_senha(dados.nova_senha, usuario.senha_hash):
        registrar_auditoria(
            db,
            acao="senha_alterada",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "senha_repetida"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da senha atual.",
        )

    usuario.senha_hash = hash_senha(dados.nova_senha)
    usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
    registrar_auditoria(
        db,
        acao="senha_alterada",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
    )
    db.commit()
    db.refresh(usuario)

    token = criar_access_token(usuario)
    _salvar_cookie_de_sessao(response, token)
    return {
        "mensagem": "Senha alterada com sucesso.",
        "autenticado": True,
    }


@router.delete("/usuarios/me/dados-pessoais")
def anonimizar_meus_dados(
    dados: SolicitacaoAnonimizacao,
    response: Response,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
    feedback_db: Session = Depends(get_feedback_db),
):

    if usuario.e_root_admin:
        registrar_auditoria(
            db,
            acao="dados_pessoais_anonimizados",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="bloqueado",
            usuario=usuario,
            detalhes={"motivo": "conta_root_requer_procedimento_administrativo"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A conta administradora principal exige um procedimento administrativo específico.",
        )

    if not usuario.senha_hash or not verificar_senha(dados.senha, usuario.senha_hash):
        registrar_auditoria(
            db,
            acao="dados_pessoais_anonimizados",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "senha_incorreta"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A senha atual não confere.")

    usuario_id = str(usuario.uuid)
    banco_feedback = db if feedback_db.get_bind() is db.get_bind() else feedback_db

    try:
        feedbacks_atendimento = anonimizar_feedbacks_atendimento(banco_feedback, usuario_id)
        feedbacks_legados = anonimizar_feedbacks_legados(db, usuario_id)
        db.query(JuridleQuestaoUso).filter_by(usuario_id=usuario_id).delete(synchronize_session=False)
        db.query(JuridleDia).filter_by(usuario_id=usuario_id).delete(synchronize_session=False)
        db.query(JuridleRodada).filter_by(usuario_id=usuario_id).delete(synchronize_session=False)
        db.query(ConteudoLeitura).filter_by(usuario_id=usuario_id).delete(synchronize_session=False)
        db.query(CategoriaAcesso).filter_by(usuario_id=usuario_id).delete(synchronize_session=False)

        if banco_feedback is not db:
            banco_feedback.commit()

        anonimizar_usuario(usuario)
        registrar_auditoria(
            db,
            acao="dados_pessoais_anonimizados",
            recurso_tipo="usuario",
            recurso_id=usuario_id,
            resultado="sucesso",
            usuario=usuario,
            detalhes={
                "escopo": ["conta", "credenciais", "feedbacks", "historico_de_estudo"],
                "feedbacks_atendimento": feedbacks_atendimento,
                "feedbacks_legados": feedbacks_legados,
                "registro_tecnico_preservado": True,
            },
        )
        db.commit()
    except Exception as erro:
        db.rollback()
        if banco_feedback is not db:
            banco_feedback.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível concluir a anonimização. Nenhuma nova tentativa foi iniciada.",
        ) from erro

    apagar_cookies(response)
    return {
        "mensagem": "Dados pessoais anonimizados e sessão encerrada.",
        "registro_preservado": {
            "usuario_id": usuario_id,
            "logs_auditoria": "preservados sem conteúdo sensível",
            "protocolos_feedback": "preservados sem identificação ou mensagens",
        },
    }


@router.post("/auth/2fa/ativar-cadastro")
def ativar_2fa_no_cadastro(dados: Codigo2FA, response: Response, db: Session = Depends(get_db), request: Request = None):
    try:
        usuario_uuid = decodificar_token_configuracao_2fa(dados.desafio_token)
    except ValueError as erro:
        baldes = limites_auth.preparar(db, request)
        limites_auth.falhar(baldes)
        registrar_auditoria(
            db,
            acao="ativacao_2fa",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "configuracao_invalida_ou_expirada"},
            commit=True,
        )
        limites_auth.exigir_liberado(baldes)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    baldes = limites_auth.preparar(db, request, usuario.email if usuario else None)
    if usuario:
        usuario = db.query(Usuario).filter_by(uuid=usuario_uuid).populate_existing().with_for_update().one()
    limites_auth.exigir_liberado(baldes, usuario)
    if not usuario or not usuario.totp_secret or usuario.is_2fa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Configuração de duas etapas inválida.")
    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
        limites_auth.falhar(baldes)
        registrar_auditoria(
            db,
            acao="ativacao_2fa",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "codigo_invalido"},
            commit=True,
        )
        limites_auth.exigir_liberado(baldes, usuario)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido. Confira o aplicativo e ative data e hora automáticas no celular.",
        )

    consumir_desafio(db, dados.desafio_token, usuario, "2fa_configuracao")
    consumir_totp(db, usuario, segredo, dados.codigo, JANELA_TOTP)
    usuario.is_2fa_enabled = True
    limites_auth.concluir(baldes)
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    registrar_auditoria(
        db,
        acao="ativacao_2fa",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
    )
    db.commit()
    token = criar_access_token(usuario, dados.lembrar_conectado)
    _salvar_cookie_de_sessao(response, token, dados.lembrar_conectado, db)
    return {
        "mensagem": "Autenticação em duas etapas ativada.",
        "autenticado": True,
        "usuario": serializar_usuario(usuario),
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    usuario: Usuario | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    from model.models import RefreshToken, SessaoAutenticada
    from auth.sessions import digest
    registro = db.get(RefreshToken, digest(request.cookies.get("jurishome_refresh_token", "")))
    if registro:
        sessao = db.get(SessaoAutenticada, registro.sessao_id)
        if usuario is None and sessao:
            usuario = db.get(Usuario, sessao.usuario_id)
        db.query(SessaoAutenticada).filter_by(id=registro.sessao_id).update({"revogada": True})
    if usuario:
        usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
    apagar_cookies(response)
    registrar_auditoria(
        db,
        acao="logout",
        recurso_tipo="sessao",
        recurso_id=usuario.uuid if usuario else None,
        resultado="sucesso",
        usuario=usuario,
        commit=True,
    )


@router.post("/auth/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    acesso, renovacao, validade = renovar_sessao(db, request.cookies.get("jurishome_refresh_token"))
    _salvar_cookie_de_sessao(response, acesso, lembrar_conectado=True, apenas_acesso=True)
    salvar_refresh(response, renovacao, validade)
    return {"autenticado": True}
