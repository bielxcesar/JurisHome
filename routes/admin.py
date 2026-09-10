from fastapi import APIRouter
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/home_admin", response_class=HTMLResponse)
def pagina_home_admin(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="Home_admin.html"
    )

@router.get("/configuracao", response_class=HTMLResponse)
def pagina_configuracao(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="confAdm.html"
    )