from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from auth.security import get_current_user
from model.models import Conteudo, Usuario
from services.lgpd import POLITICA_PRIVACIDADE_VERSAO, TERMOS_VERSAO

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/2fatores", response_class=HTMLResponse)
def pagina_2fatores(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="2fatores.html"
    )


@router.get("/recuperar-senha", response_class=HTMLResponse)
def pagina_recuperar_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha.html")


@router.get("/recuperar-senha/confirmar", response_class=HTMLResponse)
def pagina_confirmar_recuperacao(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_codigo.html")


@router.get("/recuperar-senha/nova", response_class=HTMLResponse)
def pagina_nova_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_nova.html")


@router.get("/termos-de-aceite", response_class=HTMLResponse)
def pagina_termos_de_aceite(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="termos.html",
        context={"versao_termos": TERMOS_VERSAO},
    )


@router.get("/politica-de-privacidade", response_class=HTMLResponse)
def pagina_politica_de_privacidade(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="politica_privacidade.html",
        context={"versao_politica": POLITICA_PRIVACIDADE_VERSAO},
    )


@router.get("/configuracoes-usuario", response_class=HTMLResponse)
@router.get("/templates/confUsuario.html", response_class=HTMLResponse) 
def pagina_configuracoes_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="confUsuario.html", 
        context={
            "titulo_configuracao": "Troca de senha",
            "destino_voltar": "/home_usuario",
            "destino_feedback": "/configuracoes-usuario#feedback",
            "rotulo_feedback": "Feedback e suporte",
            "rotulo_sair": "Sair",
            "feedback_interno": True,
            "mostrar_auditoria": False,
            "mostrar_exclusao_dados": True,
        },
    )


@router.get("/home_usuario", response_class=HTMLResponse)
@router.get("/home_Usuario.html", response_class=HTMLResponse)
@router.get("/templates/home_Usuario.html", response_class=HTMLResponse)
async def get_home_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request, 
        name="home_Usuario.html"
    )


@router.get("/pesquisa", response_class=HTMLResponse)
def pagina_pesquisa(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="pesquisa.html",
        context={"tipo_usuario": usuario.tipo_usuario.value},
    )


@router.get("/exibir-mais", response_class=HTMLResponse)
def pagina_exibir_mais(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="listagem_conteudos.html",
        context={"tipo_usuario": usuario.tipo_usuario.value, "visao": "recentes"},
    )


@router.get("/categorias", response_class=HTMLResponse)
def pagina_categorias(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="listagem_conteudos.html",
        context={"tipo_usuario": usuario.tipo_usuario.value, "visao": "categorias"},
    )

@router.get("/materia/{conteudo_id}", response_class=HTMLResponse)
def pagina_materia(
    conteudo_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    conteudo = db.query(Conteudo).filter(Conteudo.uuid == conteudo_id).first()
    
    if not conteudo:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    
    tags_lista = [tag.strip() for tag in conteudo.tags.split(",")] if conteudo.tags else []

    return templates.TemplateResponse(
        request=request,
        name="materia.html",
        context={
            "materia": conteudo,
            "tags": tags_lista,
            "tipo_usuario": usuario.tipo_usuario.value,
        }
    )


@router.get("/cadastro", response_class=HTMLResponse)
def pagina_cadastro(request: Request):
    return templates.TemplateResponse(request=request, name="cadastro.html")
