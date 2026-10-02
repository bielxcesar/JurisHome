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
        # Administrador e estudante usam a mesma tela, com rótulos e
        # permissões apropriados para cada perfil.
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


@router.get("/admin-feedbacks", response_class=HTMLResponse)
def pagina_feedbacks_administrativos(request: Request):
    return templates.TemplateResponse(request=request, name="admin-feedbacks.html")
