"""Consulta legislação federal na API pública de Dados Abertos do Senado."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status


URL_BASE = "https://legis.senado.leg.br/dadosabertos"
FONTE_NOME = "Dados Abertos do Senado Federal"
FONTE_URL = "https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html"
TAMANHO_MAXIMO_RESPOSTA = 1_000_000
TIPOS_PERMITIDOS = {"LEI", "LCP", "DEL"}


def _consultar_json(url: str) -> dict:
    requisicao = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JurisHome/1.0 (https://github.com/bielxcesar/JurisHome)",
        },
        method="GET",
    )
    try:
        with urlopen(requisicao, timeout=12) as resposta:  # nosec B310 - host fixo do Senado.
            bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA + 1)
        if len(bruto) > TAMANHO_MAXIMO_RESPOSTA:
            raise ValueError("Resposta externa acima do limite")
        dados = json.loads(bruto.decode("utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("Resposta externa inválida")
        return dados
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A consulta de legislação está indisponível no momento. Tente novamente mais tarde.",
        ) from erro


def _lista_documentos(dados: dict, chave: str) -> list[dict]:
    raiz = dados.get(chave)
    documentos = raiz.get("documentos") if isinstance(raiz, dict) else None
    lista = documentos.get("documento") if isinstance(documentos, dict) else None
    if isinstance(lista, dict):
        return [lista]
    if isinstance(lista, list):
        return [item for item in lista if isinstance(item, dict)]
    return []


def buscar_legislacao(tipo: str, numero: str, ano: int) -> dict:
    """Busca uma lei pelo tipo, número e ano; não armazena os resultados."""
    tipo = str(tipo or "").strip().upper()
    numero = str(numero or "").strip()
    if tipo not in TIPOS_PERMITIDOS or not re.fullmatch(r"\d{1,8}", numero) or not 1800 <= int(ano) <= 2100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe o tipo, número e ano da norma em um formato válido.",
        )

    parametros = urlencode({"tipo": tipo, "numero": numero, "ano": str(ano)})
    url_busca = f"{URL_BASE}/legislacao/lista.json?{parametros}"
    dados = _consultar_json(url_busca)
    documentos = _lista_documentos(dados, "ListaDocumento")
    if not documentos:
        return {
            "encontrado": False,
            "tipo": tipo,
            "numero": numero,
            "ano": ano,
            "fonte": FONTE_NOME,
            "fonte_url": FONTE_URL,
        }

    documento = documentos[0]
    codigo = str(documento.get("id") or "")
    identificacao = {}
    if re.fullmatch(r"\d{1,12}", codigo):
        try:
            detalhe = _consultar_json(f"{URL_BASE}/legislacao/{codigo}.json")
            itens_detalhe = _lista_documentos(detalhe, "DetalheDocumento")
            if itens_detalhe:
                identificacao = itens_detalhe[0].get("identificacao") or {}
                if not isinstance(identificacao, dict):
                    identificacao = {}
        except HTTPException:
            # A ementa da busca continua útil mesmo se a consulta de link direto falhar.
            pass

    return {
        "encontrado": True,
        "norma": {
            "nome": identificacao.get("normaNome") or documento.get("normaNome") or documento.get("descricao") or "Norma consultada",
            "tipo": identificacao.get("tipo") or documento.get("tipo") or tipo,
            "numero": identificacao.get("numero") or documento.get("numero") or numero,
            "ano": identificacao.get("dataassinatura", "")[-4:] or documento.get("anoassinatura") or str(ano),
            "ementa": documento.get("ementa") or identificacao.get("ementa") or "Ementa não informada pela fonte.",
            "data_assinatura": identificacao.get("dataassinatura") or documento.get("dataassinatura") or "",
            "apelido": identificacao.get("apelido") or documento.get("apelido") or "",
            "url_documento": identificacao.get("urlDocumento") or "",
        },
        "fonte": FONTE_NOME,
        "fonte_url": FONTE_URL,
    }
