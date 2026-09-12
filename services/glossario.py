"""Glossário editorial local: não depende de login nem de serviços externos."""

import json
import unicodedata
from pathlib import Path


def normalizar(texto: str) -> str:
    """Permite pesquisar, por exemplo, 'ACORDAO' e 'acórdão' igualmente."""
    texto = unicodedata.normalize("NFD", texto.casefold())
    return " ".join(
        "".join(c for c in texto if not unicodedata.combining(c)).split()
    )


_arquivo = Path(__file__).resolve().parents[1] / "data" / "glossario.json"
_catalogo = json.loads(_arquivo.read_text(encoding="utf-8"))
_termos = sorted(_catalogo["termos"], key=lambda item: normalizar(item["termo"]))
_fontes = _catalogo["fontes"]


def consultar_glossario(q: str = "", letra: str = "") -> dict:
    palavras = normalizar(q).split()
    inicial = normalizar(letra)
    itens = []
    for termo in _termos:
        if inicial and not normalizar(termo["termo"]).startswith(inicial):
            continue
        texto = normalizar(" ".join(
            termo[campo] for campo in ("termo", "definicao", "exemplo", "area")
        ))
        if not all(palavra in texto for palavra in palavras):
            continue
        itens.append({**termo, "fonte": _fontes[termo["fonte_id"]]})
    return {
        "itens": itens,
        "total": len(itens),
        "total_catalogo": len(_termos),
        "letras_disponiveis": sorted({normalizar(t["termo"])[0].upper() for t in _termos}),
        "q": q.strip(),
        "letra": inicial.upper(),
        "revisado_em": _catalogo["revisado_em"],
    }
