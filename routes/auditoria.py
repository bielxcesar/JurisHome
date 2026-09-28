from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
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
):
    consulta = db.query(LogAuditoria)
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

    registros = (
        consulta.order_by(LogAuditoria.criado_em.desc(), LogAuditoria.id.desc())
        .limit(limite)
        .all()
    )
    acoes = [linha[0] for linha in db.query(LogAuditoria.acao).distinct().order_by(LogAuditoria.acao).all()]
    return {
        "itens": [serializar_log(registro) for registro in registros],
        "totalExibido": len(registros),
        "limite": limite,
        "acoesDisponiveis": acoes,
    }
