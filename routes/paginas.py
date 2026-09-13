from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from model.models import Conteudo

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    conteudos = db.query(Conteudo).all()
    
    context = {
        "noticia_principal": conteudos[0] if len(conteudos) > 0 else None,
        "noticia_top": conteudos[1] if len(conteudos) > 1 else None,
        "noticia_bottom": conteudos[2] if len(conteudos) > 2 else None,
    }
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context=context
    )


@router.get("/home_admin", response_class=HTMLResponse)
@router.get("/home_Admin.html", response_class=HTMLResponse)
async def get_home_admin(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="home_Admin.html"
    )


@router.get("/2fatores", response_class=HTMLResponse)
def pagina_2fatores(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="2fatores.html"
    )


@router.get("/configuracao", response_class=HTMLResponse)
@router.get("/configuracoes-usuario", response_class=HTMLResponse)
@router.get("/templates/confUsuario.html", response_class=HTMLResponse) 
def pagina_configuracoes_usuario(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="confUsuario.html", 
        context={
            "titulo_configuracao": "Configurações do usuário",
            "destino_voltar": "/home_usuario", 
            "destino_feedback": "/admin-feedbacks",
            "rotulo_feedback": "Feedback e suporte",
            "rotulo_sair": "Sair",
            "feedback_interno": True,
        },
    )


@router.get("/admin-feedbacks", response_class=HTMLResponse)
@router.get("/templates/admin-feedbacks.html", response_class=HTMLResponse)
def pagina_feedbacks(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin-feedbacks.html"
    )

@router.get("/home_usuario", response_class=HTMLResponse)
@router.get("/home_Usuario.html", response_class=HTMLResponse)
@router.get("/templates/home_Usuario.html", response_class=HTMLResponse)
async def get_home_usuario(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="home_Usuario.html"
    )

@router.get("/materia/{conteudo_id}", response_class=HTMLResponse)
def pagina_materia(conteudo_id: str, request: Request, db: Session = Depends(get_db)):
    conteudo = db.query(Conteudo).filter(Conteudo.uuid == conteudo_id).first()
    
    if not conteudo:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    
    tags_lista = [tag.strip() for tag in conteudo.tags.split(",")] if conteudo.tags else []

    return templates.TemplateResponse(
        request=request,
        name="materia.html",
        context={
            "materia": conteudo,
            "tags": tags_lista
        }
    )