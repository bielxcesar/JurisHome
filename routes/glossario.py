from string import ascii_uppercase
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.glossario import consultar_glossario

router = APIRouter(tags=["Glossário"])
templates = Jinja2Templates(directory="templates")

Busca = Annotated[str, Query(max_length=120, description="Termo ou palavra da definição")]
Letra = Annotated[str, Query(pattern="^[A-Za-z]?$", description="Inicial de A a Z")]


@router.get("/api/glossario")
def listar_glossario(q: Busca = "", letra: Letra = ""):
    return consultar_glossario(q, letra)


@router.get("/glossario", response_class=HTMLResponse)
def pagina_glossario(
    request: Request,
    q: Busca = "",
    letra: Letra = "",
    origem: str = Query(default="", max_length=10, pattern=r"^(usuario)?$"),
):
    resultado = consultar_glossario(q, letra)
    origem_usuario = origem == "usuario"

    def url_glossario(**parametros: str) -> str:
        if origem_usuario:
            parametros["origem"] = "usuario"
        consulta = urlencode(parametros)
        return "/glossario" + (f"?{consulta}" if consulta else "")

    links_letras = [
        {
            "letra": inicial,
            "url": url_glossario(q=resultado["q"], letra=inicial),
            "disponivel": inicial in resultado["letras_disponiveis"],
        }
        for inicial in ascii_uppercase
    ]
    return templates.TemplateResponse(
        request=request,
        name="glossario.html",
        context={
            **resultado,
            "links_letras": links_letras,
            "url_todas": url_glossario(q=resultado["q"]),
            "url_glossario": url_glossario(),
            "url_limpar": url_glossario(),
            "url_inicio": "/static/pages/home-usuario.html" if origem_usuario else "/home_admin",
            "origem": "usuario" if origem_usuario else "",
        },
    )
