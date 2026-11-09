"""Consulta controlada aos metadados públicos do DataJud/CNJ."""

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status


URL_BASE = "https://api-publica.datajud.cnj.jus.br"
FONTE_NOME = "Conselho Nacional de Justiça (CNJ) — Base Nacional de Dados do Poder Judiciário (DataJud)"
FONTE_URL = "https://datajud-wiki.cnj.jus.br/api-publica/"
TAMANHO_MAXIMO_RESPOSTA = 1_000_000

GRUPOS_TRIBUNAIS_DATAJUD = [
    {
        "nome": "Tribunais superiores",
        "itens": [
            {"nome": "Superior Tribunal de Justiça (STJ)", "alias": "stj"},
            {"nome": "Tribunal Superior do Trabalho (TST)", "alias": "tst"},
            {"nome": "Tribunal Superior Eleitoral (TSE)", "alias": "tse"},
            {"nome": "Superior Tribunal Militar (STM)", "alias": "stm"},
        ],
    },
    {
        "nome": "Justiça Federal",
        "itens": [
            {"nome": f"Tribunal Regional Federal da {numero}ª Região (TRF{numero})", "alias": f"trf{numero}"}
            for numero in range(1, 7)
        ],
    },
    {
        "nome": "Justiça Estadual",
        "itens": [
            {"nome": nome, "alias": alias}
            for nome, alias in [
                ("Tribunal de Justiça do Acre (TJAC)", "tjac"),
                ("Tribunal de Justiça de Alagoas (TJAL)", "tjal"),
                ("Tribunal de Justiça do Amazonas (TJAM)", "tjam"),
                ("Tribunal de Justiça do Amapá (TJAP)", "tjap"),
                ("Tribunal de Justiça da Bahia (TJBA)", "tjba"),
                ("Tribunal de Justiça do Ceará (TJCE)", "tjce"),
                ("Tribunal de Justiça do Distrito Federal e Territórios (TJDFT)", "tjdft"),
                ("Tribunal de Justiça do Espírito Santo (TJES)", "tjes"),
                ("Tribunal de Justiça de Goiás (TJGO)", "tjgo"),
                ("Tribunal de Justiça do Maranhão (TJMA)", "tjma"),
                ("Tribunal de Justiça de Minas Gerais (TJMG)", "tjmg"),
                ("Tribunal de Justiça de Mato Grosso do Sul (TJMS)", "tjms"),
                ("Tribunal de Justiça de Mato Grosso (TJMT)", "tjmt"),
                ("Tribunal de Justiça do Pará (TJPA)", "tjpa"),
                ("Tribunal de Justiça da Paraíba (TJPB)", "tjpb"),
                ("Tribunal de Justiça de Pernambuco (TJPE)", "tjpe"),
                ("Tribunal de Justiça do Piauí (TJPI)", "tjpi"),
                ("Tribunal de Justiça do Paraná (TJPR)", "tjpr"),
                ("Tribunal de Justiça do Rio de Janeiro (TJRJ)", "tjrj"),
                ("Tribunal de Justiça do Rio Grande do Norte (TJRN)", "tjrn"),
                ("Tribunal de Justiça de Rondônia (TJRO)", "tjro"),
                ("Tribunal de Justiça de Roraima (TJRR)", "tjrr"),
                ("Tribunal de Justiça do Rio Grande do Sul (TJRS)", "tjrs"),
                ("Tribunal de Justiça de Santa Catarina (TJSC)", "tjsc"),
                ("Tribunal de Justiça de Sergipe (TJSE)", "tjse"),
                ("Tribunal de Justiça de São Paulo (TJSP)", "tjsp"),
                ("Tribunal de Justiça do Tocantins (TJTO)", "tjto"),
            ]
        ],
    },
    {
        "nome": "Justiça do Trabalho",
        "itens": [
            {"nome": f"Tribunal Regional do Trabalho da {numero}ª Região (TRT{numero})", "alias": f"trt{numero}"}
            for numero in range(1, 25)
        ],
    },
    {
        "nome": "Justiça Eleitoral",
        "itens": [
            {"nome": f"{nome_oficial} (TRE-{sigla.upper()})", "alias": f"tre-{sigla}"}
            for nome_oficial, sigla in [
                ("Tribunal Regional Eleitoral do Acre", "ac"), ("Tribunal Regional Eleitoral de Alagoas", "al"),
                ("Tribunal Regional Eleitoral do Amazonas", "am"), ("Tribunal Regional Eleitoral do Amapá", "ap"),
                ("Tribunal Regional Eleitoral da Bahia", "ba"), ("Tribunal Regional Eleitoral do Ceará", "ce"),
                ("Tribunal Regional Eleitoral do Distrito Federal", "dft"), ("Tribunal Regional Eleitoral do Espírito Santo", "es"),
                ("Tribunal Regional Eleitoral de Goiás", "go"), ("Tribunal Regional Eleitoral do Maranhão", "ma"),
                ("Tribunal Regional Eleitoral de Minas Gerais", "mg"), ("Tribunal Regional Eleitoral do Mato Grosso do Sul", "ms"),
                ("Tribunal Regional Eleitoral do Mato Grosso", "mt"), ("Tribunal Regional Eleitoral do Pará", "pa"),
                ("Tribunal Regional Eleitoral da Paraíba", "pb"), ("Tribunal Regional Eleitoral de Pernambuco", "pe"),
                ("Tribunal Regional Eleitoral do Piauí", "pi"), ("Tribunal Regional Eleitoral do Paraná", "pr"),
                ("Tribunal Regional Eleitoral do Rio de Janeiro", "rj"), ("Tribunal Regional Eleitoral do Rio Grande do Norte", "rn"),
                ("Tribunal Regional Eleitoral de Rondônia", "ro"), ("Tribunal Regional Eleitoral de Roraima", "rr"),
                ("Tribunal Regional Eleitoral do Rio Grande do Sul", "rs"), ("Tribunal Regional Eleitoral de Santa Catarina", "sc"),
                ("Tribunal Regional Eleitoral de Sergipe", "se"), ("Tribunal Regional Eleitoral de São Paulo", "sp"),
                ("Tribunal Regional Eleitoral do Tocantins", "to"),
            ]
        ],
    },
    {
        "nome": "Justiça Militar",
        "itens": [
            {"nome": "Tribunal de Justiça Militar de Minas Gerais (TJMMG)", "alias": "tjmmg"},
            {"nome": "Tribunal de Justiça Militar do Rio Grande do Sul (TJMRS)", "alias": "tjmrs"},
            {"nome": "Tribunal de Justiça Militar de São Paulo (TJM-SP)", "alias": "tjmsp"},
        ],
    },
]

TRIBUNAIS_DATAJUD = {
    item["alias"]: item["nome"]
    for grupo in GRUPOS_TRIBUNAIS_DATAJUD
    for item in grupo["itens"]
}


def normalizar_numero_processo(valor: str) -> str:
    texto = str(valor or "").strip()
    if not re.fullmatch(r"[0-9.\- ]{20,30}", texto):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe um número CNJ com 20 algarismos.",
        )
    numero = re.sub(r"\D", "", texto)
    if len(numero) != 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe um número CNJ com 20 algarismos.",
        )
    return numero


def _texto(valor, limite: int = 300) -> str:
    if not isinstance(valor, (str, int, float)):
        return ""
    return str(valor).strip()[:limite]


def _nome_metadado(valor) -> str:
    if isinstance(valor, dict):
        return _texto(valor.get("nome") or valor.get("descricao"))
    return _texto(valor)


def _resumo_processo(fonte: dict, numero: str, alias: str) -> dict:
    orgao = fonte.get("orgaoJulgador")
    movimentos = fonte.get("movimentos")
    assuntos = fonte.get("assuntos")
    return {
        "numero_processo": _texto(fonte.get("numeroProcesso")) or numero,
        "tribunal": _texto(fonte.get("tribunal")) or TRIBUNAIS_DATAJUD[alias],
        "grau": _texto(fonte.get("grau")),
        "data_ajuizamento": _texto(fonte.get("dataAjuizamento")),
        "classe": _nome_metadado(fonte.get("classe")),
        "orgao_julgador": _nome_metadado(orgao),
        "assuntos": [
            nome for nome in (_nome_metadado(item) for item in (assuntos or [])[:10]) if nome
        ] if isinstance(assuntos, list) else [],
        "movimentos": [
            {
                "nome": _nome_metadado(item),
                "data": _texto(item.get("dataHora")) if isinstance(item, dict) else "",
            }
            for item in (movimentos or [])[:8]
            if _nome_metadado(item)
        ] if isinstance(movimentos, list) else [],
    }


def consultar_processo_publico(numero_processo: str, tribunal: str, api_key: str | None = None) -> dict:
    numero = normalizar_numero_processo(numero_processo)
    alias = str(tribunal or "").strip().lower()
    if alias not in TRIBUNAIS_DATAJUD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Selecione um tribunal válido.",
        )

    chave = (api_key if api_key is not None else os.getenv("DATAJUD_API_KEY", "")).strip()
    if not chave:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A consulta ao DataJud não está configurada. Confira a chave pública no arquivo .env.",
        )

    payload = {
        "size": 1,
        "_source": ["numeroProcesso", "tribunal", "grau", "dataAjuizamento", "classe", "assuntos", "orgaoJulgador", "movimentos"],
        "query": {"match": {"numeroProcesso": numero}},
    }
    requisicao = Request(
        f"{URL_BASE}/api_publica_{alias}/_search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"APIKey {chave}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(requisicao, timeout=12) as resposta:  # nosec B310 - URL usa host fixo e alias permitido.
            bruto = resposta.read(TAMANHO_MAXIMO_RESPOSTA + 1)
        if len(bruto) > TAMANHO_MAXIMO_RESPOSTA:
            raise ValueError("Resposta externa acima do limite")
        dados = json.loads(bruto.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O serviço DataJud está indisponível no momento. Tente novamente mais tarde.",
        ) from erro

    bloco_hits = dados.get("hits") if isinstance(dados, dict) else None
    hits = bloco_hits.get("hits", []) if isinstance(bloco_hits, dict) else []
    total_bruto = bloco_hits.get("total", 0) if isinstance(bloco_hits, dict) else 0
    total = total_bruto.get("value", 0) if isinstance(total_bruto, dict) else total_bruto
    primeiro = hits[0].get("_source") if hits and isinstance(hits[0], dict) else None
    processo = _resumo_processo(primeiro, numero, alias) if isinstance(primeiro, dict) else None

    return {
        "encontrado": processo is not None,
        "total": total if isinstance(total, int) and total >= 0 else 0,
        "processo": processo,
        "fonte": FONTE_NOME,
        "fonte_url": FONTE_URL,
    }
