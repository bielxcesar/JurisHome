from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import cloudinary
import os


from database import get_db
from model.models import Conteudo, LogAuditoria, StatusConteudo, gerar_uuid, Usuario, TipoUsuario, TipoFonte
from auth.security import get_current_user
import base64

router = APIRouter()
templates = Jinja2Templates(directory="templates")
if os.getenv("CLOUDINARY_URL"):
    cloudinary.config(
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key = os.getenv("CLOUDINARY_API_KEY"),
        api_secret = os.getenv("CLOUDINARY_API_SECRET")
    )

class MateriaUpdateSchema(BaseModel):
    titulo: Optional[str] = None

# MOLDES DE DADOS
class MateriaCreate(BaseModel):
    titulo: Optional[str] = None
    sub_titulo: Optional[str] = None
    resumo_home: str
    corpo_texto: str
    categoria_id: str
    tipo_fonte: TipoFonte
    imagem_miniatura: Optional[str] = None
    imagem_corpo: Optional[str] = None
    imagem_extra_2: Optional[str] = None
    imagem_extra_3: Optional[str] = None
    fonte_original: str
    fonte_imagem: Optional[str] = None
    tags: Optional[str] = None

@router.post("/upload-imagem")
async def upload_imagem(
    arquivo: UploadFile = File(...),
    usuario_logado: Usuario = Depends(get_current_user)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    
    try:
        # Lê os bytes da imagem enviada pelo formulário
        conteudo_arquivo = await arquivo.read()
        
        # Converte o arquivo para Base64 (formato seguro para aceitar direto no HTML e no Banco)
        extensao = arquivo.filename.split(".")[-1] if "." in arquivo.filename else "png"
        base64_encoded = base64.b64encode(conteudo_arquivo).decode("utf-8")
        url_base64 = f"data:image/{extensao};base64,{base64_encoded}"
        
        return {"url": url_base64}
        
    except Exception as e:
        print(f"Erro no processamento da imagem: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar imagem: {str(e)}")
# ==============================================================================
# 2. ROTAS DE PÁGINAS VISUAIS (Frontend)
# ==============================================================================
@router.get("/home_admin", response_class=HTMLResponse)
def pagina_home_admin(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home_Admin.html"
    )
@router.get("/nova-materia", response_class=HTMLResponse)
def pagina_nova_materia(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="novaMateria.html"
    )
@router.get("/nova-materia-ex", response_class=HTMLResponse)
def pagina_nova_materia_ex(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="novaMateriaEX.html"
    )
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
    
    # Busca todas as matérias cadastradas no banco
    materias = db.query(Conteudo).order_by(Conteudo.criado_em.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="tabelaNoticias.html",
        context={"materias": materias, "usuario": usuario_logado}
    )
@router.get("/admin-feedbacks", response_class=HTMLResponse)
def pagina_feedbacks_administrativos(request: Request):
    return templates.TemplateResponse(request=request, name="admin-feedbacks.html")
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

# ==============================================================================
# 3. ROTAS DE AÇÃO (Backend / API)
# Recebem dados, validam regras de negócio e salvam no banco
# ==============================================================================
@router.post("/criar-materia")
@router.post("/criar-materia")
def criar_materia(
    dados_tela: MateriaCreate,
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if usuario_logado.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(status_code=403, detail="Apenas administradores podem criar conteúdo.")

    nova_materia = Conteudo(
        titulo=dados_tela.titulo,
        sub_titulo=dados_tela.sub_titulo,
        resumo_home=dados_tela.resumo_home,
        corpo_texto=dados_tela.corpo_texto,
        categoria_id=dados_tela.categoria_id,
        tipo_fonte=dados_tela.tipo_fonte,
        imagem_miniatura=dados_tela.imagem_miniatura,
        imagem_corpo=dados_tela.imagem_corpo,
        imagem_extra_2=dados_tela.imagem_extra_2,
        imagem_extra_3=dados_tela.imagem_extra_3,
        fonte_original=dados_tela.fonte_original,
        fonte_imagem=dados_tela.fonte_imagem,
        tags=dados_tela.tags,
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

    # Atualiza os campos da matéria com os dados recebidos
    for key, value in dados.dict(exclude_unset=True).items():
        setattr(materia, key, value)

    db.commit()
    return {"mensagem": "Matéria atualizada com sucesso!"}

@router.put("/aprovar-materia/{id_da_materia}")
def aprovar_materia(
    id_da_materia: str,
    usuario_logado: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Regra de segurança: Só o Root Admin pode aprovar matérias
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