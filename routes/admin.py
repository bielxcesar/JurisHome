from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from services.editorial import ConfiguracaoEditorial, montar_editorial, estilos_previa
from model.models import ConteudoEditorial
from types import SimpleNamespace
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from services.auditoria import registrar_auditoria
from services.administradores import exigir_root, buscar_admin, revogar_sessoes, serializar_admin
from model.models import AdministradorExcluido
from routes.auth import CadastroUsuario, Credenciais
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from model.models import Categoria, Conteudo, LogAuditoria, StatusConteudo, gerar_uuid, Usuario, TipoUsuario, TipoFonte, FeedbackAtendimento, ConteudoLeitura
from services.imagens import normalizar_imagem, LIMITE_IMAGEM_BYTES
from services.categorias import tags_padrao, combinar_tags, normalizar
from auth.security import get_current_user, hash_senha
import base64

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class CadastroAdministrador(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    nome: str = Field(min_length=3, max_length=100)
    email: str = Field(max_length=150)
    senha: str = Field(min_length=8, max_length=72)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor):
        valor = valor.strip()
        if len(valor) < 3:
            raise ValueError("Informe um nome com pelo menos 3 caracteres.")
        return valor

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        return Credenciais.limpar_email(valor)

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor):
        return CadastroUsuario.validar_senha(valor)


class ManutencaoAdministrador(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=3, max_length=100)
    email: str = Field(max_length=150)
    versao: str = Field(min_length=10, max_length=50)
    nova_senha: Optional[str] = Field(default=None, min_length=8, max_length=72)
    encerrar_sessoes: bool = Field(default=False, strict=True)
    resetar_2fa: bool = Field(default=False, strict=True)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor):
        return CadastroAdministrador.validar_nome(valor)

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        return Credenciais.limpar_email(valor)

    @field_validator("nova_senha")
    @classmethod
    def validar_senha(cls, valor):
        return CadastroUsuario.validar_senha(valor) if valor is not None else None


class ExclusaoAdministrador(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome_confirmacao: str = Field(min_length=3, max_length=100)


@router.get("/admin/administradores/{usuario_id}", response_class=HTMLResponse)
def pagina_manutencao_admin(usuario_id: str, request: Request, db: Session = Depends(get_db),
                           root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root)
    return templates.TemplateResponse(request=request, name="admin-perfil.html", context={
        "tipo_usuario": root.tipo_usuario.value, "administrador": serializar_admin(db, alvo),
    })


@router.get("/api/admin/administradores/{usuario_id}")
def consultar_administrador(usuario_id: str, db: Session = Depends(get_db), root: Usuario = Depends(exigir_root)):
    return serializar_admin(db, buscar_admin(db, usuario_id, root))


@router.put("/api/admin/administradores/{usuario_id}")
def manter_administrador(usuario_id: str, dados: ManutencaoAdministrador,
                        db: Session = Depends(get_db), root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root, bloquear=True)
    if dados.versao != alvo.atualizado_em.isoformat():
        raise HTTPException(409, "Esta conta mudou desde que a página foi aberta. Recarregue antes de salvar.")
    duplicado = db.query(Usuario.uuid).filter(func.lower(Usuario.email) == dados.email, Usuario.uuid != alvo.uuid).first()
    if duplicado:
        raise HTTPException(409, "Este e-mail já está cadastrado.")
    revogar = dados.encerrar_sessoes or dados.resetar_2fa or dados.nova_senha is not None or dados.email != alvo.email
    alvo.nome, alvo.email = dados.nome, dados.email
    if dados.nova_senha is not None:
        alvo.senha_hash = hash_senha(dados.nova_senha)
    if dados.resetar_2fa:
        alvo.totp_secret = None
        alvo.is_2fa_enabled = False
    if revogar:
        revogar_sessoes(db, alvo)
    registrar_auditoria(db, acao="administrador_atualizado", recurso_tipo="usuario", recurso_id=alvo.uuid,
                        resultado="sucesso", usuario=root,
                        detalhes={"sessoes_revogadas": revogar, "reset_2fa": dados.resetar_2fa,
                                  "senha_redefinida": dados.nova_senha is not None})
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(409, "Não foi possível salvar. Confira se o e-mail já foi usado.") from erro
    db.refresh(alvo)
    return {"mensagem": "Administrador atualizado com sucesso.", "administrador": serializar_admin(db, alvo)}


@router.delete("/api/admin/administradores/{usuario_id}")
def excluir_administrador(usuario_id: str, dados: ExclusaoAdministrador,
                         db: Session = Depends(get_db), root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root, bloquear=True)
    if dados.nome_confirmacao.strip() != alvo.nome:
        raise HTTPException(422, "Digite o nome completo exatamente como aparece na confirmação.")
    revogar_sessoes(db, alvo)
    alvo.nome = "Administrador removido"
    alvo.email = f"removido-{alvo.uuid}@invalid.local"
    alvo.senha_hash = None
    alvo.totp_secret = None
    alvo.is_2fa_enabled = False
    alvo.foto_perfil = None
    alvo.universidade = None
    alvo.especialidade_juridica = None
    db.add(AdministradorExcluido(usuario_id=alvo.uuid, excluido_por=root.uuid,
                               excluido_em=datetime.now(timezone.utc).replace(tzinfo=None)))
    registrar_auditoria(db, acao="administrador_excluido", recurso_tipo="usuario", recurso_id=alvo.uuid,
                        resultado="sucesso", usuario=root, detalhes={"vinculos_editoriais_preservados": True})
    db.commit()
    return {"mensagem": "Administrador excluído. O acesso foi encerrado; matérias e histórico foram preservados."}


@router.post("/api/admin/criar-admin", status_code=201)
def criar_administrador(dados: CadastroAdministrador, db: Session = Depends(get_db),
                        usuario: Usuario = Depends(get_current_user)):
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR or not usuario.e_root_admin:
        raise HTTPException(status_code=403, detail="Apenas o administrador principal pode cadastrar administradores.")
    if db.query(Usuario.uuid).filter(func.lower(Usuario.email) == dados.email).first():
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    novo = Usuario(nome=dados.nome, email=dados.email, senha_hash=hash_senha(dados.senha),
                   tipo_usuario=TipoUsuario.ADMINISTRADOR, e_root_admin=False, is_2fa_enabled=False)
    db.add(novo)
    try:
        db.flush()
        registrar_auditoria(db, acao="administrador_cadastrado", recurso_tipo="usuario",
                            recurso_id=novo.uuid, resultado="sucesso", usuario=usuario)
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.") from erro
    return {"mensagem": "Administrador cadastrado. O primeiro acesso exige a configuração do 2FA.", "uuid": novo.uuid}

class MateriaUpdateSchema(BaseModel):
    titulo: Optional[str] = None
    sub_titulo: Optional[str] = None
    resumo_home: Optional[str] = None
    corpo_texto: Optional[str] = None
    categoria_id: Optional[str] = None
    fonte_original: Optional[str] = None
    fonte_imagem: Optional[str] = None
    tags: Optional[str] = None

# MOLDES DE DADOS ATUALIZADOS (Compatível com novaMateriaEX.html)
class MateriaCreate(BaseModel):
    titulo: Optional[str] = None
    sub_titulo: Optional[str] = None
    resumo_home: Optional[str] = None
    corpo_texto: str = Field(min_length=1, max_length=50000)
    categoria_id: str
    tipo_fonte: TipoFonte
    
    # Capa (Aceita ambos os nomes)
    imagem_miniatura: Optional[str] = None
    miniatura: Optional[str] = None
    imagem_principal: Optional[str] = None
    
    # Imagens do corpo (Aceita ambos os nomes)
    imagem_corpo: Optional[str] = None
    corpo_1: Optional[str] = None
    
    imagem_extra_2: Optional[str] = None
    corpo_2: Optional[str] = None
    
    imagem_extra_3: Optional[str] = None
    corpo_3: Optional[str] = None
    
    fonte_original: Optional[str] = None
    fonte_imagem: Optional[str] = None
    tags: Optional[str] = None
    editorial: ConfiguracaoEditorial | None = None
    aceite_editorial: bool = Field(default=False, strict=True)
    versao_termos: str | None = None

    @model_validator(mode="after")
    def validar_creditos_editoriais(self):
        if self.editorial:
            capa = self.imagem_miniatura or self.miniatura or self.imagem_principal
            if capa and not (self.fonte_imagem or '').strip():
                raise ValueError("Informe o crédito da imagem de capa.")
            for i, imagem in enumerate((self.imagem_corpo or self.corpo_1, self.imagem_extra_2 or self.corpo_2, self.imagem_extra_3 or self.corpo_3)):
                if imagem and (i >= len(self.editorial.imagens) or not self.editorial.imagens[i].fonte.strip()):
                    raise ValueError(f"Informe o crédito da imagem interna {i+1}.")
        return self

    @field_validator("imagem_miniatura", "miniatura", "imagem_principal", "imagem_corpo", "corpo_1", "imagem_extra_2", "corpo_2", "imagem_extra_3", "corpo_3")
    @classmethod
    def validar_imagem(cls, valor):
        return normalizar_imagem(valor)


@router.post("/api/admin/materias/preview", response_class=HTMLResponse)
def preview_editorial(dados: MateriaCreate, request: Request, usuario: Usuario = Depends(get_current_user)):
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(403, "Acesso restrito.")
    materia = SimpleNamespace(titulo=dados.titulo or "Sem título", corpo_texto=dados.corpo_texto,
        fonte_imagem=dados.fonte_imagem, imagem_corpo=dados.imagem_corpo or dados.corpo_1,
        imagem_extra_2=dados.imagem_extra_2 or dados.corpo_2, imagem_extra_3=dados.imagem_extra_3 or dados.corpo_3)
    return templates.TemplateResponse(request=request, name="materia-preview-editor.html", context={
        **montar_editorial(materia, dados.editorial), "titulo": materia.titulo, "subtitulo": dados.sub_titulo,
        "preview_css": estilos_previa(),
        "capa_materia": dados.imagem_miniatura or dados.miniatura or dados.imagem_principal,
    })

@router.post("/upload-imagem")
async def upload_imagem(
    arquivo: UploadFile = File(...),
    usuario_logado: Usuario = Depends(get_current_user)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    try:
        conteudo_arquivo = await arquivo.read(LIMITE_IMAGEM_BYTES + 1)
        if len(conteudo_arquivo) > LIMITE_IMAGEM_BYTES:
            raise HTTPException(status_code=413, detail="A imagem deve ter no máximo 1 MB.")
        base64_encoded = base64.b64encode(conteudo_arquivo).decode("utf-8")
        url_base64 = normalizar_imagem(f"data:image/jpeg;base64,{base64_encoded}")
        
        return {"url": url_base64}
        
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro

# ==============================================================================
# 2. ROTAS DE PÁGINAS VISUAIS (Frontend)
# ==============================================================================
@router.get("/home_admin", response_class=HTMLResponse)
def pagina_home_admin(request: Request):
    return templates.TemplateResponse(request=request, name="home_Admin.html")

@router.get("/nova-materia", response_class=HTMLResponse)
def pagina_nova_materia(request: Request, db: Session = Depends(get_db)):
    categorias = db.query(Categoria).order_by(Categoria.nome).all()
    return templates.TemplateResponse(request=request, name="novaMateria.html", context={"categorias": categorias, "tags_por_categoria": {item.uuid: tags_padrao(item.nome) for item in categorias}})

@router.get("/nova-materia-ex", response_class=HTMLResponse)
def pagina_nova_materia_ex(request: Request):
    return templates.TemplateResponse(request=request, name="novaMateriaEX.html")

@router.get("/configuracao", response_class=HTMLResponse)
def pagina_configuracao(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="confUsuario.html",
        context={
            "titulo_configuracao": "Configurações do administrador",
            "destino_voltar": "/home_admin",
            "destino_feedback": "/admin-feedbacks",
            "rotulo_feedback": "Feedbacks e reclamações",
            "rotulo_sair": "Desconectar",
            "feedback_interno": False,
            "mostrar_auditoria": True,
            "mostrar_exclusao_dados": False,
        },
    )

@router.get("/admin/tabela-noticias", response_class=HTMLResponse)
def listar_tabela_noticias(request: Request, db: Session = Depends(get_db), usuario_logado: Usuario = Depends(get_current_user)):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    materias = db.query(Conteudo).order_by(Conteudo.criado_em.desc()).all()
    
    # Envia as informações do usuário atual para a template
    return templates.TemplateResponse(
        request=request,
        name="tabelaNoticias.html",
        context={"materias": materias, "usuario": usuario_logado}
    )

@router.get("/admin-feedbacks", response_class=HTMLResponse)
def pagina_feedbacks_administrativos(request: Request):
    return templates.TemplateResponse(request=request, name="admin-feedbacks.html")


# ==============================================================================
# 3. ROTAS DE AÇÃO (Backend / API) - USUÁRIOS E 2FA
# ==============================================================================

@router.get("/api/admin/usuarios", response_class=JSONResponse)
def listar_usuarios_filtro(
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(get_current_user)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    query = db.query(Usuario).outerjoin(AdministradorExcluido, AdministradorExcluido.usuario_id == Usuario.uuid).filter(
        AdministradorExcluido.usuario_id.is_(None),
    )
    
    if tipo == "admins":
        query = query.filter(Usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR)
    elif tipo == "leitores":
        query = query.filter(Usuario.tipo_usuario == TipoUsuario.ESTUDANTE)

    usuarios = query.all()
    
    chamados_abertos = db.query(FeedbackAtendimento.usuario_id).filter(
        FeedbackAtendimento.tipo == "Recuperacao 2FA",
        FeedbackAtendimento.status == "Recebido"
    ).all()
    lista_chamados = [c[0] for c in chamados_abertos]
    
    return [
        {
            "uuid": str(u.uuid),
            "nome": u.nome,
            "email": u.email,
            "tipo": u.tipo_usuario.value,
            "is_2fa_enabled": u.is_2fa_enabled,
            "e_root_admin": u.e_root_admin, # IMPORTANTE: Informa se é o chefe supremo
            "solicitou_ajuda": str(u.uuid) in lista_chamados
        } for u in usuarios
    ]


@router.post("/api/admin/resetar-2fa/{usuario_uuid}")
def resetar_2fa(
    usuario_uuid: str,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(get_current_user)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
        
    if usuario_logado.e_root_admin:
        raise HTTPException(
            status_code=403,
            detail="O Administrador Root possui apenas permissão de visualização. Apenas gerentes de suporte podem alterar."
        )

    usuario_alvo = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if not usuario_alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if usuario_alvo.e_root_admin:
        raise HTTPException(
            status_code=403, 
            detail="Ação proibida! A conta do Administrador Principal (Root) não pode ser modificada por suporte."
        )

    usuario_alvo.totp_secret = None
    usuario_alvo.is_2fa_enabled = False
    usuario_alvo.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
    
    chamado = db.query(FeedbackAtendimento).filter(
        FeedbackAtendimento.usuario_id == usuario_uuid,
        FeedbackAtendimento.tipo == "Recuperacao 2FA",
        FeedbackAtendimento.status == "Recebido"
    ).first()
    
    if chamado:
        chamado.status = "Resolvido"
        chamado.observacoes_json = '["2FA resetado pelo suporte."]'

    novo_log = LogAuditoria(
        usuario_id=usuario_logado.uuid,
        usuario_tipo="administrador",
        acao="reset_2fa",
        recurso_tipo="Usuario",
        recurso_id=usuario_alvo.uuid,
        resultado="sucesso",
        correlacao_id=gerar_uuid()
    )
    db.add(novo_log)
    
    db.commit()
    return {"mensagem": f"O 2FA de {usuario_alvo.nome} foi desativado com sucesso."}

# ==============================================================================
# 3. ROTAS DE AÇÃO (Backend / API) - MATÉRIAS
# ==============================================================================

@router.delete("/deletar-materia/{id_da_materia}")
def deletar_materia(
    id_da_materia: str,
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not usuario_logado.e_root_admin and usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    materia = db.query(Conteudo).filter(Conteudo.uuid == id_da_materia).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada.")

    db.query(ConteudoLeitura).filter_by(conteudo_id=materia.uuid).delete(synchronize_session=False)
    db.delete(materia)
    db.commit()
    return {"mensagem": "Matéria descartada com sucesso."}


@router.post("/criar-materia")
def criar_materia(
    dados_tela: MateriaCreate,
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar conteúdo.")

    if not dados_tela.aceite_editorial or dados_tela.versao_termos != "2026-10-30":
        raise HTTPException(422, "Leia e aceite as regras editoriais vigentes antes de enviar a matéria.")

    categoria = db.get(Categoria, dados_tela.categoria_id)
    if categoria is None:
        raise HTTPException(status_code=422, detail="Selecione uma categoria válida.")

    resumo_gerado = dados_tela.resumo_home
    if not resumo_gerado:
        resumo_gerado = dados_tela.corpo_texto[:150] + "..." if len(dados_tela.corpo_texto) > 150 else dados_tela.corpo_texto

    img_mini = dados_tela.imagem_miniatura or dados_tela.miniatura or dados_tela.imagem_principal
    img_c1 = dados_tela.imagem_corpo or dados_tela.corpo_1
    img_c2 = dados_tela.imagem_extra_2 or dados_tela.corpo_2
    img_c3 = dados_tela.imagem_extra_3 or dados_tela.corpo_3

    nova_materia = Conteudo(
        titulo=dados_tela.titulo or "Sem Título",
        sub_titulo=dados_tela.sub_titulo,
        resumo_home=resumo_gerado,
        corpo_texto=dados_tela.corpo_texto,
        categoria_id=dados_tela.categoria_id,
        tipo_fonte=dados_tela.tipo_fonte,
        imagem_miniatura=img_mini,
        imagem_corpo=img_c1,
        imagem_extra_2=img_c2,
        imagem_extra_3=img_c3,
        fonte_original=dados_tela.fonte_original,
        fonte_imagem=dados_tela.fonte_imagem,
        tags=", ".join(combinar_tags(categoria.nome, dados_tela.tags)),
        autor_id=usuario_logado.uuid,
        status=StatusConteudo.EM_ANALISE
    )
    
    db.add(nova_materia)
    if dados_tela.editorial:
        nova_materia.editorial = ConteudoEditorial(titulo_home=dados_tela.editorial.titulo_home,
            configuracao_json=dados_tela.editorial.model_dump_json())
    db.flush()
    registrar_auditoria(db, acao="aceite_editorial", recurso_tipo="conteudo", recurso_id=nova_materia.uuid,
        usuario=usuario_logado, resultado="sucesso", detalhes={"versao_termos": dados_tela.versao_termos})
    db.commit()
    return {"mensagem": "Matéria enviada com sucesso e aguardando aprovação!"}

@router.put("/editar-materia/{uuid}")
def editar_materia(uuid: str, dados: MateriaUpdateSchema, db: Session = Depends(get_db)):
    materia = db.query(Conteudo).filter(Conteudo.uuid == uuid).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada.")

    alteracoes = dados.model_dump(exclude_unset=True)
    categoria = db.get(Categoria, alteracoes.get("categoria_id", materia.categoria_id))
    if categoria is None:
        raise HTTPException(status_code=422, detail="Selecione uma categoria válida.")
    extras = alteracoes.get("tags", materia.tags)
    if "categoria_id" in alteracoes and "tags" not in alteracoes:
        antigas = {normalizar(tag) for tag in tags_padrao(materia.categoria.nome if materia.categoria else "")}
        extras = ", ".join(tag for tag in (materia.tags or "").split(",") if normalizar(tag.strip()) not in antigas)
    alteracoes["tags"] = ", ".join(combinar_tags(categoria.nome, extras))
    for key, value in alteracoes.items():
        setattr(materia, key, value)

    db.commit()
    return {"mensagem": "Matéria atualizada com sucesso!"}

@router.put("/aprovar-materia/{id_da_materia}")
def aprovar_materia(
    id_da_materia: str,
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not usuario_logado.e_root_admin:
        raise HTTPException(status_code=403, detail="Apenas o Administrador Principal pode aprovar matérias.")

    materia = db.query(Conteudo).filter(Conteudo.uuid == id_da_materia).first()

    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada.")

    materia.status = StatusConteudo.APROVADO
    
    novo_log = LogAuditoria(
        usuario_id=usuario_logado.uuid,
        usuario_tipo="administrador_root",
        acao="aprovacao_materia",
        recurso_tipo="Conteudo",
        recurso_id=materia.uuid,
        resultado="sucesso",
        correlacao_id=gerar_uuid()
    )
    db.add(novo_log)
    
    db.commit()
    return {"mensagem": "A matéria foi aprovada e agora está visível para os estudantes!"}
