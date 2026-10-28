from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from database import get_db
from model.models import LogAuditoria
from services.auditoria import serializar_log


admin_router = APIRouter(tags=["auditoria-admin"])
templates = Jinja2Templates(directory="templates")


@admin_router.get("/admin/auditoria", response_class=HTMLResponse)
def pagina_auditoria(request: Request):
    return templates.TemplateResponse(request=request, name="auditoria.html")


@admin_router.get("/api/admin/auditoria")
def listar_logs_auditoria(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    acao: Annotated[str | None, Query(max_length=80)] = None,
    resultado: Annotated[str | None, Query(max_length=20)] = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 100,
    db: Session = Depends(get_db),
    deslocamento: Annotated[int, Query(ge=0)] = 0,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    ate_id: Annotated[int | None, Query(ge=1)] = None,
):
    def utc(valor):
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise HTTPException(status_code=422, detail="Informe datas com fuso horário.")
        return valor.astimezone(timezone.utc).replace(tzinfo=None)
    inicio, fim = utc(inicio), utc(fim)
    if inicio and fim and inicio >= fim:
        raise HTTPException(status_code=422, detail="O início deve ser anterior ao fim do período.")
    snapshot = ate_id or db.query(func.max(LogAuditoria.id)).scalar()
    consulta = db.query(LogAuditoria)
    if snapshot:
        consulta = consulta.filter(LogAuditoria.id <= snapshot)
    if inicio:
        consulta = consulta.filter(LogAuditoria.criado_em >= inicio)
    if fim:
        consulta = consulta.filter(LogAuditoria.criado_em < fim)
    if busca:
        termo = f"%{busca.strip()}%"
        consulta = consulta.filter(
            or_(
                LogAuditoria.correlacao_id.ilike(termo),
                LogAuditoria.usuario_id.ilike(termo),
                LogAuditoria.recurso_id.ilike(termo),
                LogAuditoria.recurso_tipo.ilike(termo),
            )
        )
    if acao:
        consulta = consulta.filter(LogAuditoria.acao == acao)
    if resultado:
        consulta = consulta.filter(LogAuditoria.resultado == resultado)

    total = consulta.count()
    registros = (
        consulta.order_by(LogAuditoria.criado_em.desc(), LogAuditoria.id.desc())
        .offset(deslocamento)
        .limit(limite)
        .all()
    )
    acoes = [linha[0] for linha in db.query(LogAuditoria.acao).distinct().order_by(LogAuditoria.acao).all()]
    return {
        "itens": [serializar_log(registro) for registro in registros],
        "totalExibido": len(registros),
        "limite": limite,
        "total": total,
        "deslocamento": deslocamento,
        "ateId": snapshot,
        "temProxima": deslocamento + len(registros) < total,
        "acoesDisponiveis": acoes,
    }
