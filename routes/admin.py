from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/home_admin", response_class=HTMLResponse)
def pagina_home_admin(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home_Admin.html"
    )

@router.get("/configuracao", response_class=HTMLResponse)
def pagina_configuracao(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="confAdm.html",
        context={
            "titulo_configuracao": "Configurações do administrador",
            "destino_voltar": "/home_admin",
            "destino_feedback": "/static/pages/admin-feedbacks.html?v=20260913-3",
            "rotulo_feedback": "Feedbacks e reclamações",
            "rotulo_sair": "Desconectar",
            "feedback_interno": False,
        },
    )
