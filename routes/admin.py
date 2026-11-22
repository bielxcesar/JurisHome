from typing import Optional, Literal
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import Field, ConfigDict, field_validator, model_validator
from services.validacao import ModeloSeguro, email_valido, fonte_http, linha, nome_pessoa, nova_senha, texto_simples
from services.editorial import ConfiguracaoEditorial, montar_editorial, estilos_previa
from types import SimpleNamespace
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from services.auditoria import registrar_auditoria
from services import limites_operacoes
from services.privacidade import mascarar_email
from services.administradores import exigir_root, buscar_admin, revogar_sessoes, serializar_admin
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from feedback_database import get_feedback_db
from model.models import (
    AdministradorExcluido,
    Categoria,
    Conteudo,
    ConteudoEditorial,
    ConteudoLeitura,
    CuradoriaMateria,
    FeedbackAtendimento,
    LogAuditoria,
    StatusConteudo,
    TipoUsuario,
    Usuario,
    gerar_uuid,
)
from services.imagens import normalizar_imagem, normalizar_imagem_bytes, url_fonte_segura, url_imagem_segura, LIMITE_IMAGEM_BYTES
from services.categorias import (
    categoria_disponivel,
    categorias_disponiveis,
    combinar_tags,
    normalizar,
    tags_padrao,
)
from auth.sessions import garantir_transacao
from auth.security import get_current_user, hash_senha
import base64

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class CadastroAdministrador(ModeloSeguro):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    nome: str = Field(min_length=3, max_length=100)
    email: str = Field(max_length=150)
    senha: str = Field(min_length=8, max_length=25)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor):
        return nome_pessoa(valor)

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        return email_valido(valor)

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor):
        return nova_senha(valor)


class ManutencaoAdministrador(ModeloSeguro):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=3, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    versao: str = Field(min_length=10, max_length=50)
    nova_senha: Optional[str] = Field(default=None, min_length=8, max_length=25)
    encerrar_sessoes: bool = Field(default=False, strict=True)
    resetar_2fa: bool = Field(default=False, strict=True)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor):
        return CadastroAdministrador.validar_nome(valor)

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        return email_valido(valor) if valor is not None else None

    @field_validator("nova_senha")
    @classmethod
    def validar_senha(cls, valor):
        return nova_senha(valor) if valor is not None else None


class ExclusaoAdministrador(ModeloSeguro):
    model_config = ConfigDict(extra="forbid")
    nome_confirmacao: str = Field(min_length=3, max_length=100)


@router.get("/admin/administradores/{usuario_id}", response_class=HTMLResponse)
def pagina_manutencao_admin(usuario_id: str, request: Request, db: Session = Depends(get_db),
                           root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root)
    registrar_consulta_contato(db, alvo, root)
    return templates.TemplateResponse(request=request, name="admin-perfil.html", context={
        "tipo_usuario": root.tipo_usuario.value, "administrador": serializar_admin(db, alvo, incluir_email=True),
    })


@router.get("/api/admin/administradores/{usuario_id}")
def consultar_administrador(usuario_id: str, db: Session = Depends(get_db), root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root)
    registrar_consulta_contato(db, alvo, root)
    return serializar_admin(db, alvo, incluir_email=True)


@router.put("/api/admin/administradores/{usuario_id}")
def manter_administrador(usuario_id: str, dados: ManutencaoAdministrador,
                        db: Session = Depends(get_db), root: Usuario = Depends(exigir_root)):
    alvo = buscar_admin(db, usuario_id, root, bloquear=True)
    conta = salvar_manutencao_conta(db, alvo, dados, root)
    return {"mensagem": "Administrador atualizado com sucesso.", "administrador": conta}


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

class MateriaSchema(ModeloSeguro):
    @field_validator('titulo', 'sub_titulo', 'resumo_home', 'fonte_imagem', 'tags', check_fields=False)
    @classmethod
    def validar_linha(cls, valor, info):
        limites = {'titulo':180, 'sub_titulo':500, 'resumo_home':500, 'fonte_imagem':2000, 'tags':500}
        return linha(valor, limites[info.field_name]) if valor is not None else None

    @field_validator('fonte_original', check_fields=False)
    @classmethod
    def validar_fonte(cls, valor):
        return fonte_http(valor)


class MateriaUpdateSchema(MateriaSchema):
    versao: int = Field(strict=True, ge=0)
    titulo: Optional[str] = Field(default=None, max_length=180)
    sub_titulo: Optional[str] = Field(default=None, max_length=500)
    resumo_home: Optional[str] = Field(default=None, max_length=500)
    corpo_texto: Optional[str] = Field(default=None, min_length=1, max_length=50000)
    categoria_id: Optional[str] = Field(default=None, max_length=36)
    fonte_original: Optional[str] = Field(default=None, max_length=2000)
    fonte_imagem: Optional[str] = Field(default=None, max_length=2000)
    tags: Optional[str] = Field(default=None, max_length=500)


# MOLDES DE DADOS ATUALIZADOS (Compatível com novaMateriaEX.html)
class MateriaCreate(MateriaSchema):
    titulo: Optional[str] = Field(default=None, max_length=180)
    sub_titulo: Optional[str] = Field(default=None, max_length=500)
    resumo_home: Optional[str] = Field(default=None, max_length=500)
    corpo_texto: str = Field(min_length=1, max_length=50000)
    categoria_id: str = Field(min_length=1, max_length=36)
    
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
    
    fonte_original: Optional[str] = Field(default=None, max_length=2000)
    fonte_imagem: Optional[str] = Field(default=None, max_length=2000)
    tags: Optional[str] = Field(default=None, max_length=500)
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
def upload_imagem(
    arquivo: UploadFile = File(...),
    usuario_logado: Usuario = Depends(get_current_user)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    try:
        conteudo_arquivo = arquivo.file.read(LIMITE_IMAGEM_BYTES + 1)
        if len(conteudo_arquivo) > LIMITE_IMAGEM_BYTES:
            raise HTTPException(status_code=413, detail="A imagem deve ter no máximo 1 MB.")
        jpeg = normalizar_imagem_bytes(conteudo_arquivo)
        url_base64 = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        
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
    categorias = categorias_disponiveis(db)
    return templates.TemplateResponse(request=request, name="novaMateria.html", context={"categorias": categorias, "tags_por_categoria": {item.uuid: tags_padrao(item.nome) for item in categorias}})

@router.get("/nova-materia-ex", response_class=HTMLResponse)
def pagina_nova_materia_ex(request: Request):
    return templates.TemplateResponse(request=request, name="novaMateriaEX.html", context={"tipo_usuario": "administrador"})

@router.get("/configuracao", response_class=HTMLResponse)
def pagina_configuracao(request: Request, usuario_logado: Usuario = Depends(get_current_user)):
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
            "e_root_admin": bool(usuario_logado.e_root_admin),
        },
    )

@router.get("/admin/tabela-noticias", response_class=HTMLResponse)
def listar_tabela_noticias(request: Request, db: Session = Depends(get_db), usuario_logado: Usuario = Depends(get_current_user)):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    materias = db.query(Conteudo).order_by(Conteudo.criado_em.desc()).all()
    ids_materias = [materia.uuid for materia in materias]
    curadorias = (db.query(CuradoriaMateria).filter(CuradoriaMateria.conteudo_id.in_(ids_materias)).all()
                  if ids_materias else [])
    versoes_materias = {curadoria.conteudo_id: curadoria.versao for curadoria in curadorias}

    # Envia as informações do usuário atual para a template
    return templates.TemplateResponse(
        request=request,
        name="tabelaNoticias.html",
        context={"materias": materias, "versoes_materias": versoes_materias, "usuario": usuario_logado}
    )

@router.get("/admin-feedbacks", response_class=HTMLResponse)
def pagina_feedbacks_administrativos(request: Request):
    return templates.TemplateResponse(request=request, name="admin-feedbacks.html")


# ==============================================================================
# 3. ROTAS DE AÇÃO (Backend / API) - USUÁRIOS E 2FA
# ==============================================================================

@router.get("/api/admin/usuarios", response_class=JSONResponse)
def listar_usuarios_filtro(
    tipo: Optional[Literal["admins", "leitores", "administrador", "estudante"]] = None,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(get_current_user),
    feedback_db: Session = Depends(get_feedback_db),
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
    
    chamados_abertos = feedback_db.query(FeedbackAtendimento.usuario_id).filter(
        FeedbackAtendimento.tipo == "Recuperacao 2FA",
        FeedbackAtendimento.status.in_(["Recebido", "Em análise", "Respondido"]),
        FeedbackAtendimento.arquivado.is_(False),
    ).all()
    lista_chamados = [c[0] for c in chamados_abertos]
    
    return [
        {
            "uuid": str(u.uuid),
            "nome": u.nome,
            "email": mascarar_email(u.email),
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
    usuario_logado: Usuario = Depends(get_current_user),
    feedback_db: Session = Depends(get_feedback_db),
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
    
    chamados = db if feedback_db.get_bind() is db.get_bind() else feedback_db
    resolver_recuperacoes_2fa(chamados, usuario_uuid)

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
    if chamados is not db:
        chamados.commit()
    return {"mensagem": f"O 2FA de {usuario_alvo.nome} foi desativado com sucesso."}

# ==============================================================================
# 3. ROTAS DE AÇÃO (Backend / API) - MATÉRIAS
# ==============================================================================

@router.delete("/deletar-materia/{id_da_materia}")
def deletar_materia(
    id_da_materia: str,
    versao: int = Query(..., ge=0),
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not usuario_logado.e_root_admin and usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    materia = db.query(Conteudo).filter(Conteudo.uuid == id_da_materia).with_for_update().first()
    if not materia:
        raise HTTPException(status_code=404, detail="Matéria não encontrada.")
    curadoria = db.query(CuradoriaMateria).filter_by(conteudo_id=materia.uuid).with_for_update().first()
    versao_atual = curadoria.versao if curadoria else 0
    if versao != versao_atual:
        raise HTTPException(409, "A matéria foi alterada em outra sessão. Atualize a tabela antes de excluir.")

    db.query(ConteudoLeitura).filter_by(conteudo_id=materia.uuid).delete(synchronize_session=False)
    db.query(CuradoriaMateria).filter_by(conteudo_id=materia.uuid).delete(synchronize_session=False)
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
    if categoria is None or not categoria_disponivel(categoria.nome):
        raise HTTPException(status_code=422, detail="Selecione uma categoria válida.")

    limite_materia = limites_operacoes.verificar_materia(db, usuario_logado.uuid)

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
    limites_operacoes.concluir(limite_materia, 15)
    if dados_tela.editorial:
        nova_materia.editorial = ConteudoEditorial(titulo_home=dados_tela.editorial.titulo_home,
            configuracao_json=dados_tela.editorial.model_dump_json())
    db.flush()
    registrar_auditoria(db, acao="aceite_editorial", recurso_tipo="conteudo", recurso_id=nova_materia.uuid,
        usuario=usuario_logado, resultado="sucesso", detalhes={"versao_termos": dados_tela.versao_termos})
    db.commit()
    return {"mensagem": "Matéria enviada com sucesso e aguardando aprovação!"}

@router.put("/editar-materia/{uuid}")
def editar_materia(uuid: str, dados: MateriaUpdateSchema, db: Session = Depends(get_db),
                   usuario: Usuario = Depends(get_current_user)):
    materia, curadoria = materia_para_curadoria(db, uuid, usuario)
    if dados.versao != curadoria.versao:
        raise HTTPException(409, "A matéria foi alterada em outra sessão. Atualize antes de salvar.")

    alteracoes = dados.model_dump(exclude_unset=True, exclude={"versao"})
    categoria = db.get(Categoria, alteracoes.get("categoria_id", materia.categoria_id))
    if categoria is None or ("categoria_id" in alteracoes and not categoria_disponivel(categoria.nome)):
        raise HTTPException(status_code=422, detail="Selecione uma categoria válida.")
    extras = alteracoes.get("tags", materia.tags)
    if "categoria_id" in alteracoes and "tags" not in alteracoes:
        antigas = {normalizar(tag) for tag in tags_padrao(materia.categoria.nome if materia.categoria else "")}
        extras = ", ".join(tag for tag in (materia.tags or "").split(",") if normalizar(tag.strip()) not in antigas)
    alteracoes["tags"] = ", ".join(combinar_tags(categoria.nome, extras))
    for key, value in alteracoes.items():
        setattr(materia, key, value)
    materia.status = StatusConteudo.EM_ANALISE
    curadoria.versao += 1
    db.commit()
    return {"mensagem": "Matéria atualizada e enviada para análise.", "versao": curadoria.versao}

@router.put("/aprovar-materia/{id_da_materia}")
def aprovar_materia_legada(
    id_da_materia: str, usuario: Usuario = Depends(exigir_root),
):
    raise HTTPException(409, "Abra Revisar matéria para conferir o conteúdo completo e aprovar a versão atual.")


class ReenvioMateria(MateriaCreate):
    versao: int = Field(strict=True, ge=0)


class DecisaoMateria(ModeloSeguro):
    versao: int = Field(strict=True, ge=0)
    decisao: Literal["aprovar", "devolver"]
    orientacoes: str = Field(default="", max_length=4000)

    @field_validator("orientacoes")
    @classmethod
    def validar_orientacoes(cls, valor):
        return texto_simples(valor)


def materia_para_curadoria(db, identificador, usuario):
    materia = db.query(Conteudo).filter_by(uuid=identificador).with_for_update().first()
    if materia is None:
        raise HTTPException(404, "Matéria não encontrada.")
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR or (
        not usuario.e_root_admin and materia.autor_id != usuario.uuid
    ):
        raise HTTPException(404, "Matéria não encontrada.")
    curadoria = db.get(CuradoriaMateria, materia.uuid)
    if curadoria is None:
        curadoria = CuradoriaMateria(conteudo_id=materia.uuid, versao=0, orientacoes="")
        db.add(curadoria)
        db.flush()
    return materia, curadoria


@router.get("/admin/materias/{identificador}/revisao", response_class=HTMLResponse)
def pagina_revisao_materia(
    identificador: str, request: Request,
    db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user),
):
    materia, curadoria = materia_para_curadoria(db, identificador, usuario)
    db.commit()
    return templates.TemplateResponse(
        request=request, name="materia-curadoria.html",
        headers={"Cache-Control": "no-store"},
        context={
            "materia": materia, "curadoria": curadoria, "usuario": usuario,
            **montar_editorial(materia),
            "capa_materia": url_imagem_segura(materia.imagem_miniatura),
            "fonte_original": url_fonte_segura(materia.fonte_original),
        },
    )


@router.get("/api/admin/materias/{identificador}/edicao")
def dados_edicao_materia(
    identificador: str, db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    materia, curadoria = materia_para_curadoria(db, identificador, usuario)
    configuracao = None
    if materia.editorial:
        configuracao = ConfiguracaoEditorial.model_validate_json(materia.editorial.configuracao_json)
    db.commit()
    return {
        **{campo: getattr(materia, campo) for campo in (
            "titulo", "sub_titulo", "resumo_home", "corpo_texto", "categoria_id",
            "fonte_original", "fonte_imagem", "imagem_miniatura", "imagem_corpo",
            "imagem_extra_2", "imagem_extra_3", "tags",
        )},
        "versao": curadoria.versao, "orientacoes": curadoria.orientacoes,
        "editorial": configuracao.model_dump() if configuracao else {"formatado": False},
    }


@router.put("/api/admin/materias/{identificador}/reenviar")
def reenviar_materia(
    identificador: str, dados: ReenvioMateria, db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    materia, curadoria = materia_para_curadoria(db, identificador, usuario)
    if curadoria.versao != dados.versao:
        raise HTTPException(409, "A matéria mudou. Reabra o editor para conferir a versão atual.")
    if not dados.aceite_editorial or dados.versao_termos != "2026-10-30":
        raise HTTPException(422, "Confirme as regras editoriais antes de reenviar.")
    categoria = db.get(Categoria, dados.categoria_id)
    if not categoria or not categoria_disponivel(categoria.nome):
        raise HTTPException(422, "Selecione uma categoria válida.")
    for campo in ("titulo", "sub_titulo", "resumo_home", "corpo_texto", "categoria_id", "fonte_original", "fonte_imagem"):
        setattr(materia, campo, getattr(dados, campo))
    materia.titulo = materia.titulo or "Sem título"
    materia.resumo_home = materia.resumo_home or dados.corpo_texto[:150]
    materia.imagem_miniatura = dados.imagem_miniatura or dados.miniatura or dados.imagem_principal
    materia.imagem_corpo = dados.imagem_corpo or dados.corpo_1
    materia.imagem_extra_2 = dados.imagem_extra_2 or dados.corpo_2
    materia.imagem_extra_3 = dados.imagem_extra_3 or dados.corpo_3
    materia.tags = ", ".join(combinar_tags(categoria.nome, dados.tags))
    if dados.editorial:
        if materia.editorial is None:
            materia.editorial = ConteudoEditorial()
        materia.editorial.titulo_home = dados.editorial.titulo_home
        materia.editorial.configuracao_json = dados.editorial.model_dump_json()
    materia.status = StatusConteudo.EM_ANALISE
    curadoria.versao += 1
    registrar_auditoria(db, acao="materia_reenviada", recurso_tipo="conteudo",
        recurso_id=materia.uuid, usuario=usuario, resultado="sucesso",
        detalhes={"versao": curadoria.versao})
    db.commit()
    return {"mensagem": "Correções enviadas para nova análise."}


@router.post("/api/admin/materias/{identificador}/curadoria")
def decidir_materia(
    identificador: str, dados: DecisaoMateria, db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_root),
):
    materia, curadoria = materia_para_curadoria(db, identificador, usuario)
    if dados.versao != curadoria.versao or materia.status != StatusConteudo.EM_ANALISE:
        raise HTTPException(409, "A matéria mudou ou já foi revisada. Atualize a página.")
    if dados.decisao == "devolver" and len(dados.orientacoes) < 10:
        raise HTTPException(422, "Explique as correções necessárias com pelo menos dez caracteres.")
    materia.status = StatusConteudo.APROVADO if dados.decisao == "aprovar" else StatusConteudo.REJEITADO
    curadoria.orientacoes = dados.orientacoes
    curadoria.revisada_em = datetime.now(timezone.utc).replace(tzinfo=None)
    curadoria.versao += 1
    registrar_auditoria(db, acao="materia_" + dados.decisao, recurso_tipo="conteudo",
        recurso_id=materia.uuid, usuario=usuario, resultado="sucesso",
        detalhes={"versao": curadoria.versao})
    db.commit()
    return {"mensagem": "Matéria aprovada." if dados.decisao == "aprovar" else "Matéria devolvida ao autor."}


def registrar_consulta_contato(db: Session, alvo: Usuario, administrador: Usuario) -> None:
    registrar_auditoria(db, acao="dados_usuario_consultados", recurso_tipo="usuario",
                        recurso_id=alvo.uuid, resultado="sucesso", usuario=administrador,
                        detalhes={"escopo": "perfil_contato"}, commit=True)


@router.get("/admin/usuarios/{usuario_id}", response_class=HTMLResponse)
def consultar_perfil_usuario(usuario_id: str, request: Request, db: Session = Depends(get_db),
                             administrador: Usuario = Depends(get_current_user)):
    if administrador.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(403, "Acesso negado.")
    alvo = db.get(Usuario, usuario_id)
    if alvo is None or db.get(AdministradorExcluido, usuario_id):
        raise HTTPException(404, "Usuário não encontrado.")
    registrar_consulta_contato(db, alvo, administrador)
    conta = serializar_admin(db, alvo, incluir_email=True)
    if alvo.tipo_usuario == TipoUsuario.ESTUDANTE:
        return templates.TemplateResponse(request=request, name="admin-perfil.html",
            context={"tipo_usuario": administrador.tipo_usuario.value, "administrador": conta,
                     "rotulo_perfil": "Leitor", "titulo_perfil": "Perfil do leitor",
                     "descricao_perfil": "Atualize informações e gerencie a segurança desta conta de leitor.",
                     "endpoint_edicao": "/api/admin/leitores/" + str(alvo.uuid)},
            headers={"Cache-Control": "no-store"})
    conta["perfil"] = ("Administrador principal" if alvo.e_root_admin else "Administrador de suporte") if alvo.tipo_usuario == TipoUsuario.ADMINISTRADOR else "Leitor"
    return templates.TemplateResponse(request=request, name="usuario-perfil.html",
        context={"tipo_usuario": administrador.tipo_usuario.value, "conta": conta},
        headers={"Cache-Control": "no-store"})


def salvar_manutencao_conta(db, alvo, dados, responsavel):
    if dados.versao != alvo.atualizado_em.isoformat():
        raise HTTPException(409, "Esta conta mudou desde que a página foi aberta. Recarregue antes de salvar.")
    novo_email = dados.email if dados.email is not None else alvo.email
    duplicado = db.query(Usuario.uuid).filter(func.lower(Usuario.email) == novo_email, Usuario.uuid != alvo.uuid).first()
    if duplicado:
        raise HTTPException(409, "Este e-mail já está cadastrado.")
    revogar = dados.encerrar_sessoes or dados.resetar_2fa or dados.nova_senha is not None or novo_email != alvo.email
    alvo.nome, alvo.email = dados.nome, novo_email
    if dados.nova_senha is not None:
        alvo.senha_hash = hash_senha(dados.nova_senha)
    if dados.resetar_2fa:
        alvo.totp_secret = None
        alvo.is_2fa_enabled = False
    if revogar:
        revogar_sessoes(db, alvo)
    registrar_auditoria(db, acao="administrador_atualizado" if alvo.tipo_usuario == TipoUsuario.ADMINISTRADOR else "leitor_atualizado", recurso_tipo="usuario", recurso_id=alvo.uuid,
                        resultado="sucesso", usuario=responsavel,
                        detalhes={"sessoes_revogadas": revogar, "reset_2fa": dados.resetar_2fa,
                                  "senha_redefinida": dados.nova_senha is not None})
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(409, "Não foi possível salvar. Confira se o e-mail já foi usado.") from erro
    db.refresh(alvo)
    return serializar_admin(db, alvo, incluir_email=True)



@router.put("/api/admin/leitores/{usuario_id}")
def manter_leitor(usuario_id: str, dados: ManutencaoAdministrador, db: Session = Depends(get_db),
                  administrador: Usuario = Depends(get_current_user),
                  feedback_db: Session = Depends(get_feedback_db)):
    if administrador.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(403, "Acesso negado.")
    garantir_transacao(db)
    alvo = db.query(Usuario).filter_by(uuid=usuario_id, tipo_usuario=TipoUsuario.ESTUDANTE).populate_existing().with_for_update().first()
    if alvo is None or alvo.e_root_admin:
        raise HTTPException(404, "Leitor não encontrado.")
    chamados = db if feedback_db.get_bind() is db.get_bind() else feedback_db
    if dados.resetar_2fa:
        resolver_recuperacoes_2fa(chamados, usuario_id)
    conta = salvar_manutencao_conta(db, alvo, dados, administrador)
    if dados.resetar_2fa and chamados is not db:
        chamados.commit()
    return {"mensagem": "Usuário atualizado com sucesso.", "conta": conta}


def resolver_recuperacoes_2fa(chamados: Session, usuario_uuid: str) -> None:
    pendentes = chamados.query(FeedbackAtendimento).filter(
        FeedbackAtendimento.usuario_id == usuario_uuid,
        FeedbackAtendimento.tipo == "Recuperacao 2FA",
        FeedbackAtendimento.status.in_(["Recebido", "Em análise", "Respondido"]),
        FeedbackAtendimento.arquivado.is_(False),
    ).all()
    
    for chamado in pendentes:
        chamado.status = "Resolvido"
        chamado.observacoes_json = '["2FA resetado pelo suporte."]'

