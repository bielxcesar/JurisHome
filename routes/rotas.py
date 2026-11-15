"""Rotas HTML de entrada, navegação e documentos do JurisHome."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth.security import get_current_user, get_current_user_optional
from database import get_db
from model.models import TipoUsuario, Usuario
from services.categorias import CATALOGO
from services.glossario import consultar_glossario
from services.lgpd import revisao_vigente, versao_legal

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, usuario: Usuario | None = Depends(get_current_user_optional)):
    if usuario and request.cookies.get("jurishome_refresh_token"):
        destino = "/home_admin" if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR else "/home_usuario"
        return RedirectResponse(destino, status_code=303, headers={"Cache-Control": "no-store"})
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/cadastro", response_class=HTMLResponse)
def pagina_cadastro(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="cadastro.html",
        context={"areas_interesse": list(CATALOGO), "versao_documentos": versao_legal(revisao_vigente(db))},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/2fatores", response_class=HTMLResponse)
def pagina_2fatores(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="2fatores.html"
    )


@router.get("/renovar-sessao", response_class=HTMLResponse)
def pagina_renovar_sessao(request: Request, destino: str = "/home_usuario"):
    permitidos = {"/home_usuario", "/home_admin", "/perfil", "/pesquisa", "/categorias", "/exibir-mais", "/configuracoes-usuario", "/configuracao", "/admin-feedbacks", "/admin/auditoria", "/feedback", "/juridle", "/juridle/ampliar", "/curiosidades", "/conhecimento", "/admin/tabela-noticias"}
    destino_dinamico = any(destino.startswith(prefixo) and destino.removeprefix(prefixo).replace("-", "").isalnum()
                           for prefixo in ("/materia/", "/admin/administradores/"))
    if destino not in permitidos and not destino_dinamico:
        destino = "/home_usuario"
    return templates.TemplateResponse(request=request, name="renovar_sessao.html", context={"destino": destino})


@router.get("/recuperar-senha", response_class=HTMLResponse)
def pagina_recuperar_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha.html")


@router.get("/problemas-acesso", response_class=HTMLResponse)
def pagina_problemas_acesso(request: Request):
    return templates.TemplateResponse(request=request, name="problemas_acesso.html", headers={"Cache-Control": "no-store"})


@router.get("/recuperar-senha/confirmar", response_class=HTMLResponse)
def pagina_confirmar_recuperacao(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_codigo.html")


@router.get("/recuperar-senha/nova", response_class=HTMLResponse)
def pagina_nova_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_nova.html")


@router.get("/home_usuario", response_class=HTMLResponse)
@router.get("/home_Usuario.html", response_class=HTMLResponse)
@router.get("/templates/home_Usuario.html", response_class=HTMLResponse)
async def get_home_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR:
        raise HTTPException(404, "Página não encontrada.")
    return templates.TemplateResponse(
        request=request,
        name="home_Usuario.html"
    )


@router.get("/configuracoes-usuario", response_class=HTMLResponse)
@router.get("/templates/confUsuario.html", response_class=HTMLResponse)
def pagina_configuracoes_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR:
        raise HTTPException(404, "Página não encontrada.")
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


@router.get("/feedback", response_class=HTMLResponse)
def pagina_feedback(request: Request, usuario: Usuario = Depends(get_current_user)):
    if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR:
        raise HTTPException(404, "Página não encontrada.")
    return templates.TemplateResponse(request=request, name="feedback-suporte.html")


@router.get("/conhecimento", response_class=HTMLResponse)
def pagina_conhecimento(request: Request, usuario: Usuario = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="conhecimento.html", context={
        "tipo_usuario": usuario.tipo_usuario.value,
    })


@router.get("/curiosidades", response_class=HTMLResponse)
def pagina_curiosidades(request: Request, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    selecionados = {"acordao", "habeas-corpus", "jurisprudencia", "onus-da-prova", "conciliacao", "mediacao"}
    itens = [item for item in consultar_glossario(db=db)["itens"] if item["id"] in selecionados]
    return templates.TemplateResponse(request=request, name="curiosidades.html", context={
        "tipo_usuario": usuario.tipo_usuario.value, "itens": itens,
    })


@router.get("/juridle", response_class=HTMLResponse)
def pagina_juridle(request: Request, usuario: Usuario = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="juridle.html", context={
        "tipo_usuario": usuario.tipo_usuario.value,
    })

