"""Busca local de termos jurídicos."""

import json
from pathlib import Path

from services.texto import normalizar_para_busca as normalizar


_arquivo = Path(__file__).resolve().parents[1] / "data" / "glossario.json"
_catalogo = json.loads(_arquivo.read_text(encoding="utf-8"))
_fontes = _catalogo["fontes"]
_CAMPOS_BUSCA = ("termo", "definicao", "exemplo", "area")
# O catálogo é fixo durante a execução. Prepare o texto de busca uma vez.
_termos_indexados = sorted(
    (
        (
            normalizar(termo["termo"]),
            normalizar(" ".join(termo[campo] for campo in _CAMPOS_BUSCA)),
            termo,
        )
        for termo in _catalogo["termos"]
    ),
    key=lambda registro: registro[0],
)
_letras_disponiveis = sorted({nome[0].upper() for nome, _, _ in _termos_indexados})


def consultar_glossario(q: str = "", letra: str = "") -> dict:
    palavras = normalizar(q).split()
    inicial = normalizar(letra)
    itens = []
    for nome, texto, termo in _termos_indexados:
        if inicial and not nome.startswith(inicial):
            continue
        if not all(palavra in texto for palavra in palavras):
            continue
        itens.append({**termo, "fonte": _fontes[termo["fonte_id"]]})
    return {
        "itens": itens,
        "total": len(itens),
        "total_catalogo": len(_termos_indexados),
        "letras_disponiveis": _letras_disponiveis.copy(),
        "q": q.strip(),
        "letra": inicial.upper(),
        "revisado_em": _catalogo["revisado_em"],
    }
