from services.validacao import TextoBusca, padrao_busca
from string import ascii_uppercase
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from auth.security import get_current_user_optional
from model.models import Usuario
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.glossario import consultar_glossario

router = APIRouter(tags=["Glossário"])
templates = Jinja2Templates(directory="templates")

Busca = Annotated[TextoBusca, Query(max_length=80, description="Termo ou palavra da definição")]
Pagina = Annotated[int, Query(ge=1, description="Página de seis termos")]

Letra = Annotated[str, Query(pattern="^[A-Za-z]?$", description="Inicial de A a Z")]


def paginar(q, letra, pagina):
    resultado = consultar_glossario(q, letra)
    total_paginas = max(1, (resultado['total'] + 5) // 6)
    pagina = min(pagina, total_paginas)
    inicio = (pagina - 1) * 6
    return {**resultado, 'itens': resultado['itens'][inicio:inicio+6], 'pagina': pagina,
        'total_paginas': total_paginas, 'por_pagina': 6,
        'primeiro': inicio + 1 if resultado['total'] else 0, 'ultimo': min(inicio+6, resultado['total'])}


@router.get("/api/glossario")
def listar_glossario(q: Busca = "", letra: Letra = "", pagina: Pagina = 1):
    return paginar(q, letra, pagina)


@router.get("/glossario", response_class=HTMLResponse)
def pagina_glossario(
    request: Request,
    q: Busca = "",
    letra: Letra = "",
    origem: str = Query(default="", max_length=10, pattern=r"^(usuario)?$"),
    usuario: Usuario | None = Depends(get_current_user_optional),
    pagina: Pagina = 1,
):
    resultado = paginar(q, letra, pagina)
    pagina = resultado["pagina"]
    tipo_usuario = usuario.tipo_usuario.value if usuario else "usuario"
    origem_usuario = tipo_usuario != "administrador"

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
    def link_pagina(numero):
        return url_glossario(q=resultado['q'], letra=resultado['letra'], pagina=str(numero)) + '#titulo-resultados'

    numeros = sorted({1, resultado['total_paginas'], *range(max(1, pagina-1), min(resultado['total_paginas'], pagina+1)+1)})
    paginas = []
    anterior = 0
    for numero in numeros:
        if anterior and numero - anterior > 1:
            paginas.append({'numero': None})
        paginas.append({'numero': numero, 'url': link_pagina(numero)})
        anterior = numero
    return templates.TemplateResponse(
        request=request,
        name="glossario.html",
        context={
            **resultado,
            "tipo_usuario": tipo_usuario,
            "paginas": paginas,
            "pagina_anterior": link_pagina(pagina-1) if pagina > 1 else None,
            "pagina_proxima": link_pagina(pagina+1) if pagina < resultado["total_paginas"] else None,
            "links_letras": links_letras,
            "url_todas": url_glossario(q=resultado["q"]),
            "url_glossario": url_glossario(),
            "url_limpar": url_glossario(),
            "url_inicio": "/home_usuario" if origem_usuario else "/home_admin",
            "origem": "usuario" if origem_usuario else "",
        },
    )
