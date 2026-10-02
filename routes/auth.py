import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from io import BytesIO
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from auth.security import (
    cifrar_segredo_2fa,
    criar_access_token,
    criar_token_configuracao_2fa,
    criar_token_nova_senha,
    criar_token_recuperacao_senha,
    criar_token_2fa_pendente,
    decifrar_segredo_2fa,
    decodificar_token_configuracao_2fa,
    decodificar_token_nova_senha,
    decodificar_token_recuperacao_senha,
    decodificar_token_2fa_pendente,
    get_current_user,
    get_current_user_optional,
    hash_senha,
    verificar_senha,
)
from database import get_db
from feedback_database import get_feedback_db
from model.models import TipoUsuario, Usuario
from services.auditoria import registrar_auditoria
from services.direitos_titular import (
    anonimizar_feedbacks_atendimento,
    anonimizar_feedbacks_legados,
    anonimizar_usuario,
)
from services.lgpd import TERMOS_VERSAO


router = APIRouter(prefix="/api", tags=["Autenticação e usuários"])

TENTATIVAS_ANTES_DO_BLOQUEIO = 5
MINUTOS_DE_BLOQUEIO = 15
JANELA_TOTP = 2
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
API_IES_PUBLICA = (
    "https://gisserver.caubr.gov.br/server/rest/services/"
    "CEF_IES_PUBLICO_2022/FeatureServer/0/query"
)
logger = logging.getLogger(__name__)


class CadastroUsuario(BaseModel):
    nome: Annotated[str, Field(min_length=3, max_length=100)]
    email: Annotated[str, Field(max_length=150)]
    senha: Annotated[str, Field(min_length=8, max_length=72)]
    confirmar_senha: Annotated[str, Field(min_length=8, max_length=72)]
    consentimento_lgpd: bool

    @model_validator(mode="after")
    def validar_confirmacao_senha(self):
        if self.senha != self.confirmar_senha:
            raise ValueError("As senhas não conferem.")
        return self

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        email = valor.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("Informe um e-mail válido.")
        return email

    @field_validator("nome")
    @classmethod
    def limpar_texto(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor: str) -> str:
        if not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
            raise ValueError("A senha deve ter letras e números.")
        if len(valor.encode("utf-8")) > 72:
            raise ValueError("A senha não pode ultrapassar 72 bytes.")
        return valor


class Credenciais(BaseModel):
    email: Annotated[str, Field(max_length=150)]
    senha: Annotated[str, Field(min_length=1, max_length=72)]

    @field_validator("email")
    @classmethod
    def limpar_email(cls, valor: str) -> str:
        email = valor.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("Informe um e-mail válido.")
        return email


class Codigo2FA(BaseModel):
    desafio_token: Annotated[str, Field(min_length=20)]
    codigo: Annotated[str, Field(pattern=r"^\d{6}$")]
    lembrar_conectado: bool = False


class InicioRecuperacaoSenha(BaseModel):
    email: Annotated[str, Field(max_length=150)]

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        email = valor.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("Informe um e-mail válido.")
        return email


class ConfirmacaoRecuperacaoSenha(InicioRecuperacaoSenha):
    desafio_token: Annotated[str, Field(min_length=20)]
    codigo: Annotated[str, Field(pattern=r"^\d{6}$")]


class NovaSenhaRecuperacao(BaseModel):
    token_redefinicao: Annotated[str, Field(min_length=20)]
    nova_senha: Annotated[str, Field(min_length=8, max_length=25)]
    confirmar_senha: Annotated[str, Field(min_length=8, max_length=25)]

    @field_validator("nova_senha")
    @classmethod
    def validar_nova_senha(cls, valor: str) -> str:
        if not re.search(r"[A-Z]", valor) or not re.search(r"[^A-Za-z0-9]", valor):
            raise ValueError("Use de 8 a 25 caracteres, com uma letra maiúscula e um caractere especial.")
        if len(valor.encode("utf-8")) > 72:
            raise ValueError("A senha não pode ultrapassar 72 bytes.")
        return valor


class AtualizacaoPerfil(BaseModel):
    nome: Annotated[str | None, Field(default=None, min_length=3, max_length=100)] = None


class AtualizacaoSenha(BaseModel):
    senha_atual: Annotated[str, Field(min_length=1, max_length=72)]
    nova_senha: Annotated[str, Field(min_length=8, max_length=72)]

    @field_validator("nova_senha")
    @classmethod
    def validar_nova_senha(cls, valor: str) -> str:
        if not re.search(r"[A-Za-z]", valor) or not re.search(r"\d", valor):
            raise ValueError("A nova senha deve ter letras e números.")
        if len(valor.encode("utf-8")) > 72:
            raise ValueError("A nova senha não pode ultrapassar 72 bytes.")
        return valor


class SolicitacaoAnonimizacao(BaseModel):
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
    usuario.tentativas_login_falhas += 1
    usuario.ultima_falha_login = agora
    if usuario.tentativas_login_falhas >= TENTATIVAS_ANTES_DO_BLOQUEIO:
        usuario.bloqueado_ate = agora + timedelta(minutes=MINUTOS_DE_BLOQUEIO)
        usuario.tentativas_login_falhas = 0


def _salvar_cookie_de_sessao(response: Response, token: str, lembrar_conectado: bool = False) -> None:
    response.set_cookie(
        key="jurishome_access_token",
        value=token,
        max_age=14 * 24 * 60 * 60 if lembrar_conectado else 30 * 60,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )


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


def preparar_configuracao_2fa(usuario: Usuario, db: Session) -> dict:
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


def _serializar_resultado_emec(codigo_emec: int, dados: dict) -> dict | None:
    #Converte o formato do pacote ``emec-api`` para a resposta pública.
    nome = str(dados.get("nome_da_ies") or dados.get("nome") or "").strip()
    if not nome:
        return None
    campus = dados.get("campus") or []
    return {
        "codigo_emec": codigo_emec,
        "nome": nome,
        "sigla": dados.get("sigla"),
        "situacao": dados.get("situacao"),
        "campus": [
            {"codigo": item.get("code"), "cidade": item.get("city"), "uf": item.get("uf")}
            for item in campus[:20]
        ],
        "fonte": "e-MEC / Ministério da Educação",
    }


def consultar_ies_api_publica(codigo_emec: int) -> dict | None:
    #Consulta uma fonte pública externa por código e-MEC.

    """
    É uma redundância de rede, não um catálogo do projeto. A consulta solicita
    apenas os campos necessários para não coletar dados de coordenadores ou
    outros dados pessoais disponíveis na camada pública.
    """
    parametros = urlencode(
        {
            "where": f"ies_cdg_mec_ies={codigo_emec}",
            "outFields": "ies_cdg_mec_ies,ies_nome,ies_sigla,ies_campus,ies_municipio,ies_uf,curso_situacao",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    try:
        with urlopen(f"{API_IES_PUBLICA}?{parametros}", timeout=10) as resposta:  # nosec B310
            dados = json.loads(resposta.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None

    recursos = dados.get("features")
    if not isinstance(recursos, list) or not recursos:
        return None

    primeiro = recursos[0].get("attributes", {})
    nome = str(primeiro.get("ies_nome") or "").strip()
    if not nome:
        return None

    campus_unicos = []
    vistos = set()
    for recurso in recursos:
        atributos = recurso.get("attributes", {})
        chave = (
            str(atributos.get("ies_campus") or "").strip(),
            str(atributos.get("ies_municipio") or "").strip(),
            str(atributos.get("ies_uf") or "").strip(),
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        campus_unicos.append(
            {
                "codigo": None,
                "nome": chave[0] or None,
                "cidade": chave[1] or None,
                "uf": chave[2] or None,
            }
        )

    return {
        "codigo_emec": codigo_emec,
        "nome": nome,
        "sigla": primeiro.get("ies_sigla"),
        "situacao": primeiro.get("curso_situacao"),
        "campus": campus_unicos[:20],
        "fonte": "API pública de IES do CAU/BR, consultada pelo código e-MEC",
    }


def consultar_instituicao_emec(codigo_emec: int) -> dict:
    #Consulta uma instituição pelo código oficial da IES no e-MEC.

    """
    A consulta é feita exclusivamente em serviços externos. O ``emec-api`` é
    a fonte principal; a API pública de IES é consultada somente se o portal
    e-MEC não devolver dados. Não há catálogo local ou resposta simulada.
    """
    try:
        from emec_api.api.client import Institution
    except ImportError as erro:
        dados_publicos = consultar_ies_api_publica(codigo_emec)
        if dados_publicos:
            return dados_publicos
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A consulta e-MEC está indisponível. Instale as dependências do projeto ou tente novamente mais tarde.",
        ) from erro

    dados_emec = None
    try:
        instituicao = Institution(codigo_emec)
        instituicao.parse()
        dados_emec = _serializar_resultado_emec(codigo_emec, instituicao.get_full_json())
    except Exception as erro:
        # O portal e-MEC pode bloquear leituras automatizadas. A tentativa
        # seguinte permanece externa e usa somente o código informado.
        logger.warning(
            "A fonte principal e-MEC falhou (%s); tentando a fonte pública de contingência.",
            type(erro).__name__,
        )
    if dados_emec:
        return dados_emec

    dados_publicos = consultar_ies_api_publica(codigo_emec)
    if dados_publicos:
        return dados_publicos

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="As fontes externas de instituições não responderam à consulta. Tente novamente mais tarde.",
    )


async def obter_instituicao_emec(codigo_emec: int) -> dict:
    # O pacote e-MEC é síncrono e usa asyncio internamente; a thread evita
    # bloquear a API do JurisHome durante a consulta externa.
    return await asyncio.to_thread(consultar_instituicao_emec, codigo_emec)


@router.get("/universidades/emec/{codigo_emec}")
async def consultar_universidade(codigo_emec: Annotated[int, Field(ge=1)]):
    #Retorna dados oficiais de uma IES a partir do código e-MEC.
    return await obter_instituicao_emec(codigo_emec)


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
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        registrar_auditoria(
            db,
            acao="cadastro",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "email_ja_cadastrado"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este e-mail já está cadastrado. Entre para continuar a configuração da conta.",
        )

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        tipo_usuario=TipoUsuario.ESTUDANTE,
        consentimento_lgpd=True,
        data_consentimento=_agora_sem_fuso(),
        versao_termos=TERMOS_VERSAO,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    configuracao = preparar_configuracao_2fa(usuario, db)
    registrar_auditoria(
        db,
        acao="cadastro",
        recurso_tipo="usuario",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
        detalhes={"versao_termos": TERMOS_VERSAO, "requer_2fa": True},
        commit=True,
    )
    return configuracao


@router.post("/auth/login")
def login(dados: Credenciais, response: Response, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    agora = _agora_sem_fuso()
    mensagem_invalida = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="E-mail ou senha inválidos.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not usuario:
        registrar_auditoria(
            db,
            acao="autenticacao_credenciais",
            recurso_tipo="sessao",
            resultado="falha",
            detalhes={"motivo": "credenciais_invalidas"},
            commit=True,
        )
        raise mensagem_invalida
    if _usuario_bloqueado(usuario, agora):
        registrar_auditoria(
            db,
            acao="autenticacao_credenciais",
            recurso_tipo="sessao",
            recurso_id=usuario.uuid,
            resultado="bloqueado",
            usuario=usuario,
            detalhes={"motivo": "conta_bloqueada"},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Conta temporariamente bloqueada. Tente novamente mais tarde.",
        )
    if not usuario.senha_hash or not verificar_senha(dados.senha, usuario.senha_hash):
        _registrar_falha_autenticacao(usuario, agora)
        registrar_auditoria(
            db,
            acao="autenticacao_credenciais",
            recurso_tipo="sessao",
            recurso_id=usuario.uuid,
            resultado="falha",
            usuario=usuario,
            detalhes={"motivo": "credenciais_invalidas"},
        )
        db.commit()
        raise mensagem_invalida

    registrar_auditoria(
        db,
        acao="autenticacao_credenciais",
        recurso_tipo="sessao",
        recurso_id=usuario.uuid,
        resultado="sucesso",
        usuario=usuario,
        detalhes={"etapa_seguinte": "2fa"},
    )
    db.commit()

    if not usuario.is_2fa_enabled or not usuario.totp_secret:
        return preparar_configuracao_2fa(usuario, db)
    if usuario.is_2fa_enabled:
        return {"requer_2fa": True, "desafio_token": criar_token_2fa_pendente(usuario)}


@router.post("/auth/2fa/validar")
def validar_2fa(dados: Codigo2FA, response: Response, db: Session = Depends(get_db)):
    try:
        usuario_uuid = decodificar_token_2fa_pendente(dados.desafio_token)
    except ValueError as erro:
        registrar_auditoria(
            db,
            acao="autenticacao_2fa",
            recurso_tipo="sessao",
            resultado="falha",
            detalhes={"motivo": "desafio_invalido_ou_expirado"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
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
    if _usuario_bloqueado(usuario):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Conta temporariamente bloqueada após tentativas inválidas. Aguarde 15 minutos.",
        )
    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de autenticação inválido. Confira se data e hora automáticas estão ativadas no celular.",
        )

    token = criar_access_token(usuario, dados.lembrar_conectado)
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    _salvar_cookie_de_sessao(response, token, dados.lembrar_conectado)
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
        "access_token": token,
        "token_type": "bearer",  # nosec
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
def validar_recuperacao_senha(dados: ConfirmacaoRecuperacaoSenha, db: Session = Depends(get_db)):
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

    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if (
        not usuario
        or not usuario.is_2fa_enabled
        or not usuario.totp_secret
        or _usuario_bloqueado(usuario)
    ):
        raise resposta_invalida

    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro

    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
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
        raise resposta_invalida

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
        if emitido_em <= int(limite.timestamp()):
            raise invalida

    usuario.senha_hash = hash_senha(dados.nova_senha)
    usuario.token_validos_apos = datetime.fromtimestamp(int(time.time()), tz=timezone.utc).replace(tzinfo=None)
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
    # O JWT armazena iat em segundos. A mesma precisão evita invalidar o novo
    # token ao comparar com o instante em que as sessões anteriores expiram.
    usuario.token_validos_apos = datetime.fromtimestamp(int(time.time()), tz=timezone.utc).replace(tzinfo=None)
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
        "access_token": token,
        "token_type": "bearer",  # nosec
    }


@router.delete("/usuarios/me/dados-pessoais")
def anonimizar_meus_dados(
    dados: SolicitacaoAnonimizacao,
    response: Response,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
    feedback_db: Session = Depends(get_feedback_db),
):
    """Anonimiza dados pessoais sem apagar protocolos ou logs de auditoria."""

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

        # Quando o módulo de feedback usa outro banco, os textos pessoais são
        # descartados primeiro. Em seguida a conta e o log são confirmados no
        # banco principal.
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
                "escopo": ["conta", "credenciais", "feedbacks"],
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

    response.delete_cookie(key="jurishome_access_token", path="/")
    return {
        "mensagem": "Dados pessoais anonimizados e sessão encerrada.",
        "registro_preservado": {
            "usuario_id": usuario_id,
            "logs_auditoria": "preservados sem conteúdo sensível",
            "protocolos_feedback": "preservados sem identificação ou mensagens",
        },
    }


@router.post("/auth/2fa/ativar-cadastro")
def ativar_2fa_no_cadastro(dados: Codigo2FA, response: Response, db: Session = Depends(get_db)):
    """Ativa o TOTP obrigatório e libera o primeiro acesso à conta."""
    try:
        usuario_uuid = decodificar_token_configuracao_2fa(dados.desafio_token)
    except ValueError as erro:
        registrar_auditoria(
            db,
            acao="ativacao_2fa",
            recurso_tipo="usuario",
            resultado="falha",
            detalhes={"motivo": "configuracao_invalida_ou_expirada"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(erro)) from erro

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if not usuario or not usuario.totp_secret or usuario.is_2fa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Configuração de duas etapas inválida.")
    if _usuario_bloqueado(usuario):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Conta temporariamente bloqueada após tentativas inválidas. Aguarde 15 minutos.",
        )
    try:
        segredo = decifrar_segredo_2fa(usuario.totp_secret)
    except (RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    if not _verificar_totp(segredo, dados.codigo):
        _registrar_falha_autenticacao(usuario)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido. Confira o aplicativo e ative data e hora automáticas no celular.",
        )

    usuario.is_2fa_enabled = True
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
    _salvar_cookie_de_sessao(response, token, dados.lembrar_conectado)
    return {
        "mensagem": "Autenticação em duas etapas ativada.",
        "access_token": token,
        "token_type": "bearer",  
        "usuario": serializar_usuario(usuario),
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    usuario: Usuario | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    response.delete_cookie(key="jurishome_access_token", path="/")
    registrar_auditoria(
        db,
        acao="logout",
        recurso_tipo="sessao",
        recurso_id=usuario.uuid if usuario else None,
        resultado="sucesso",
        usuario=usuario,
        commit=True,
    )
