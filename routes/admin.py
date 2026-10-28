from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from model.models import Categoria, Conteudo, LogAuditoria, StatusConteudo, gerar_uuid, Usuario, TipoUsuario, TipoFonte, FeedbackAtendimento
from services.imagens import normalizar_imagem, LIMITE_IMAGEM_BYTES
from services.categorias import tags_padrao, combinar_tags, normalizar
from auth.security import get_current_user, hash_senha
import base64

router = APIRouter()
templates = Jinja2Templates(directory="templates")

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
    corpo_texto: str
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

    @field_validator("imagem_miniatura", "miniatura", "imagem_principal", "imagem_corpo", "corpo_1", "imagem_extra_2", "corpo_2", "imagem_extra_3", "corpo_3")
    @classmethod
    def validar_imagem(cls, valor):
        return normalizar_imagem(valor)

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

    query = db.query(Usuario)
    
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
