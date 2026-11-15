"""Normalização de texto para pesquisa e comparação."""

import unicodedata


def normalizar_para_busca(texto: str) -> str:
    """Uniformiza caixa, acentos e espaços para comparação textual."""
    decomposicao = unicodedata.normalize("NFD", texto.casefold())
    sem_acentos = "".join(
        caractere for caractere in decomposicao if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.split())
