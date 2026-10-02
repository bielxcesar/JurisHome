import json
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from model.models import LogAuditoria


_correlacao_id: ContextVar[str | None] = ContextVar("auditoria_correlacao_id", default=None)
_ator_id: ContextVar[str | None] = ContextVar("auditoria_ator_id", default=None)
_ator_tipo: ContextVar[str] = ContextVar("auditoria_ator_tipo", default="anonimo")

_CHAVES_PROIBIDAS = (
    "senha",
    "token",
    "segredo",
    "cookie",
    "email",
    "nome",
    "mensagem",
    "conteudo",
    "documento",
)


def iniciar_contexto_auditoria() -> tuple[tuple[Any, Any, Any], str]:
    correlacao = str(uuid.uuid4())
    tokens = (
        _correlacao_id.set(correlacao),
        _ator_id.set(None),
        _ator_tipo.set("anonimo"),
    )
    return tokens, correlacao


def finalizar_contexto_auditoria(tokens: tuple[Any, Any, Any]) -> None:
    _correlacao_id.reset(tokens[0])
    _ator_id.reset(tokens[1])
    _ator_tipo.reset(tokens[2])


def definir_ator_auditoria(usuario: Any) -> None:
    if usuario is None:
        return
    _ator_id.set(str(getattr(usuario, "uuid", "")) or None)
    tipo = getattr(usuario, "tipo_usuario", "usuario")
    _ator_tipo.set(str(getattr(tipo, "value", tipo)))


def _detalhes_seguros(detalhes: dict[str, Any] | None) -> dict[str, Any]:
    if not detalhes:
        return {}

    seguros: dict[str, Any] = {}
    for chave, valor in detalhes.items():
        chave_normalizada = str(chave).lower()
        if any(proibida in chave_normalizada for proibida in _CHAVES_PROIBIDAS):
            continue
        if isinstance(valor, (str, int, float, bool)) or valor is None:
            seguros[str(chave)] = str(valor)[:250] if isinstance(valor, str) else valor
        elif isinstance(valor, (list, tuple)):
            seguros[str(chave)] = [str(item)[:100] for item in valor[:20]]
    return seguros


def registrar_auditoria(
    db: Session,
    *,
    acao: str,
    recurso_tipo: str,
    resultado: str,
    recurso_id: str | None = None,
    usuario: Any = None,
    detalhes: dict[str, Any] | None = None,
    commit: bool = False,
) -> LogAuditoria:

    usuario_id = _ator_id.get()
    usuario_tipo = _ator_tipo.get()
    if usuario is not None:
        usuario_id = str(getattr(usuario, "uuid", "")) or None
        tipo = getattr(usuario, "tipo_usuario", "usuario")
        usuario_tipo = str(getattr(tipo, "value", tipo))

    registro = LogAuditoria(
        usuario_id=usuario_id,
        usuario_tipo=usuario_tipo,
        acao=acao[:80],
        recurso_tipo=recurso_tipo[:80],
        recurso_id=str(recurso_id)[:100] if recurso_id is not None else None,
        resultado=resultado[:20],
        correlacao_id=_correlacao_id.get() or str(uuid.uuid4()),
        detalhes_json=json.dumps(_detalhes_seguros(detalhes), ensure_ascii=False),
        criado_em=datetime.now(timezone.utc),
    )
    db.add(registro)
    if commit:
        db.commit()
        db.refresh(registro)
    return registro


def serializar_log(registro: LogAuditoria) -> dict[str, Any]:
    try:
        detalhes = json.loads(registro.detalhes_json or "{}")
    except (TypeError, json.JSONDecodeError):
        detalhes = {}
    criado_em = registro.criado_em
    if criado_em.tzinfo is None:
        criado_em = criado_em.replace(tzinfo=timezone.utc)
    return {
        "id": registro.id,
        "usuarioId": registro.usuario_id,
        "usuarioTipo": registro.usuario_tipo,
        "acao": registro.acao,
        "recursoTipo": registro.recurso_tipo,
        "recursoId": registro.recurso_id,
        "resultado": registro.resultado,
        "correlacaoId": registro.correlacao_id,
        "detalhes": detalhes,
        "criadoEm": criado_em.isoformat(),
    }
