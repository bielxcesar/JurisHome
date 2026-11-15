"""Catálogo persistido no banco; o arquivo SQL é usado somente na migração inicial."""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from database import SessionLocal
from model.models import GlossarioCatalogo, GlossarioTermo
from services.texto import normalizar_para_busca as normalizar


def instalar_catalogo_inicial(engine):
    """Importa o catálogo uma única vez, inclusive com múltiplas instâncias."""
    arquivo = Path(__file__).resolve().parents[1] / 'data' / 'glossario_inicial.sql'
    with engine.begin() as conexao:
        resultado = conexao.execute(text(
            'INSERT INTO migracoes_dados (nome, aplicada_em) VALUES (:nome, :agora) '
            'ON CONFLICT (nome) DO NOTHING'
        ), {'nome': 'glossario_inicial_v1', 'agora': datetime.now(timezone.utc).replace(tzinfo=None)})
        if resultado.rowcount:
            for comando in arquivo.read_text(encoding='utf-8').splitlines():
                if comando.strip():
                    conexao.exec_driver_sql(comando)


def consultar_glossario(q: str = '', letra: str = '', db=None) -> dict:
    if db is None:
        with SessionLocal() as sessao:
            return consultar_glossario(q, letra, sessao)
    registros = db.query(GlossarioTermo).options(joinedload(GlossarioTermo.fonte)).all()
    catalogo = db.get(GlossarioCatalogo, 1)
    termos = sorted(registros, key=lambda item: normalizar(item.termo))
    palavras, inicial = normalizar(q).split(), normalizar(letra)
    itens = []
    for item in termos:
        nome = normalizar(item.termo)
        texto = normalizar(' '.join((item.termo, item.definicao, item.exemplo, item.area)))
        if inicial and not nome.startswith(inicial):
            continue
        if not all(palavra in texto for palavra in palavras):
            continue
        itens.append({campo: getattr(item, campo) for campo in ('id', 'termo', 'area', 'definicao', 'exemplo', 'referencia', 'fonte_id')} | {
            'fonte': {'nome': item.fonte.nome, 'url': item.fonte.url}
        })
    return {'itens': itens, 'total': len(itens), 'total_catalogo': len(termos),
            'letras_disponiveis': sorted({normalizar(item.termo)[0].upper() for item in termos if normalizar(item.termo)}),
            'q': q.strip(), 'letra': inicial.upper(), 'revisado_em': catalogo.revisado_em if catalogo else ''}
