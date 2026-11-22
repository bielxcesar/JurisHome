"""Avatares estáticos permitidos para os perfis do JurisHome."""

AVATARES_PERFIL = (
    {"id": "aurora", "nome": "Aurora", "url": "/static/images/avatares/aurora.svg"},
    {"id": "oceano", "nome": "Oceano", "url": "/static/images/avatares/oceano.svg"},
    {"id": "folha", "nome": "Folha", "url": "/static/images/avatares/folha.svg"},
    {"id": "ambar", "nome": "Âmbar", "url": "/static/images/avatares/ambar.svg"},
    {"id": "violeta", "nome": "Violeta", "url": "/static/images/avatares/violeta.svg"},
    {"id": "ceu", "nome": "Céu", "url": "/static/images/avatares/ceu.svg"},
)

AVATAR_POR_ID = {avatar["id"]: avatar for avatar in AVATARES_PERFIL}
AVATAR_POR_URL = {avatar["url"]: avatar for avatar in AVATARES_PERFIL}
