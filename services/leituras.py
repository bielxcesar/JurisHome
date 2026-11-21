"""Retenção dos registros individuais usados na dashboard e em Em alta."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from database import SessionLocal
from model.models import CategoriaAcesso, ConteudoLeitura, fuso_br
from services.logs_operacionais import registrar_falha_operacional

DIAS_RETENCAO_LEITURA = 90


def limite_leituras(hoje: date | None = None) -> str:
    referencia = hoje or datetime.now(fuso_br).date()
    return (referencia - timedelta(days=DIAS_RETENCAO_LEITURA - 1)).isoformat()


def limpar_leituras_antigas(db: Session, hoje: date | None = None) -> int:
    """Remove antes do limite inclusivo; a transação pertence ao chamador."""
    return db.query(ConteudoLeitura).filter(
        ConteudoLeitura.dia < limite_leituras(hoje)
    ).delete(synchronize_session=False)


def limpar_metricas_periodicamente() -> None:
    with SessionLocal() as db:
        limpar_leituras_antigas(db)
        # Ambas as métricas têm janela de 90 dias.
        db.query(CategoriaAcesso).filter(
            CategoriaAcesso.dia < limite_leituras()
        ).delete(synchronize_session=False)
        db.commit()


async def _rotina_metricas() -> None:
    while True:
        try:
            await run_in_threadpool(limpar_metricas_periodicamente)
        except Exception as erro:
            # Não inclui a mensagem da exceção, que pode conter valores da consulta.
            registrar_falha_operacional(
                componente="retencao.metricas",
                operacao="limpeza_diaria",
                erro=erro,
            )
            await asyncio.sleep(3600)
        else:
            await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def ciclo_retencao_metricas(app):
    tarefa = asyncio.create_task(_rotina_metricas())
    try:
        yield
    finally:
        tarefa.cancel()
        try:
            await tarefa
        except asyncio.CancelledError:
            pass
