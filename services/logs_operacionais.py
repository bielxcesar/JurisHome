"""Logs operacionais estruturados com contexto técnico e sem dados do pedido."""

from datetime import datetime, timezone
from contextvars import ContextVar
import json
import logging
import os
from queue import Queue, Full
import re
import sys
import traceback
from pathlib import Path
from threading import Lock, Thread
from uuid import UUID, uuid4


_FORMATADOR = "_jurishome_json_formatter"
_ROTA_SEGURA = re.compile(r"^[A-Za-z0-9_./{}:-]{1,160}$")
_METODO_SEGURO = re.compile(r"^[A-Z]{1,12}$")
_COMPONENTE_SEGURO = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_CORRELACAO_REQUISICAO: ContextVar[str | None] = ContextVar("logs_operacionais_correlacao", default=None)
_FILA_PERSISTENCIA: Queue[dict[str, object]] = Queue(maxsize=1000)
_SESSAO_PERSISTENCIA = None
_MODELO_PERSISTENCIA = None
_TRABALHADOR_PERSISTENCIA: Thread | None = None
_BLOQUEIO_PERSISTENCIA = Lock()


class FormatadorJSONOperacional(logging.Formatter):
    """Emite um objeto JSON por linha para os logs de execução da Railway."""

    def format(self, registro: logging.LogRecord) -> str:
        evento = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": registro.levelname.lower(),
            "message": registro.getMessage(),
            "component": registro.name,
        }
        contexto = getattr(registro, "log_context", None)
        if isinstance(contexto, dict):
            evento.update(contexto)
        return json.dumps(evento, ensure_ascii=False, separators=(",", ":"))


def configurar_logs_operacionais() -> None:
    """Usa stdout, formato JSON e desliga o acesso Uvicorn que imprime URLs."""
    logger = logging.getLogger("jurishome")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, _FORMATADOR, False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(FormatadorJSONOperacional())
        setattr(handler, _FORMATADOR, True)
        logger.addHandler(handler)

    # O access logger padrão pode incluir o caminho literal e a query string.
    # A aplicação registra abaixo apenas a rota declarada no código.
    logging.getLogger("uvicorn.access").disabled = True


def configurar_persistencia_operacional(session_factory, modelo) -> None:
    """Ativa gravação assíncrona no banco para avisos e erros sanitizados."""
    global _SESSAO_PERSISTENCIA, _MODELO_PERSISTENCIA, _TRABALHADOR_PERSISTENCIA
    with _BLOQUEIO_PERSISTENCIA:
        _SESSAO_PERSISTENCIA = session_factory
        _MODELO_PERSISTENCIA = modelo
        if _TRABALHADOR_PERSISTENCIA is None or not _TRABALHADOR_PERSISTENCIA.is_alive():
            _TRABALHADOR_PERSISTENCIA = Thread(
                target=_trabalhador_persistencia,
                name="jurishome-operational-log-writer",
                daemon=True,
            )
            _TRABALHADOR_PERSISTENCIA.start()


def _gravar_evento_no_banco(evento: dict[str, object]) -> None:
    session_factory = _SESSAO_PERSISTENCIA
    modelo = _MODELO_PERSISTENCIA
    if not session_factory or modelo is None:
        return

    sessao = None
    try:
        sessao = session_factory()
        sessao.add(modelo(**evento))
        sessao.commit()
    except Exception:
        try:
            sessao.rollback()
        except Exception:
            pass
        # O evento original já foi enviado ao stdout. Não registrar a exceção
        # deste caminho para evitar recursão e exposição de dados do driver.
        try:
            sys.stderr.write("operational_log_persistence_failed; see application stdout logs\n")
        except Exception:
            pass
    finally:
        if sessao is not None:
            try:
                sessao.close()
            except Exception:
                pass


def _trabalhador_persistencia() -> None:
    while True:
        evento = _FILA_PERSISTENCIA.get()
        try:
            _gravar_evento_no_banco(evento)
        finally:
            _FILA_PERSISTENCIA.task_done()


def _enfileirar_persistencia(
    *, nivel: int, componente: str, evento: str, contexto: dict[str, object]
) -> None:
    if nivel < logging.WARNING or _MODELO_PERSISTENCIA is None:
        return
    try:
        seguro = {
            "criado_em": datetime.now(timezone.utc),
            "nivel": logging.getLevelName(nivel).lower(),
            "componente": componente[:80],
            "evento": evento[:60],
            "operacao": str(contexto.get("operation") or "")[:100] or None,
            "metodo": str(contexto.get("method") or "")[:12] or None,
            "rota": str(contexto.get("route") or "")[:160] or None,
            "status_http": contexto.get("http_status"),
            "duracao_ms": contexto.get("duration_ms"),
            "correlacao_id": _correlacao_valida(str(contexto.get("correlation_id") or "")),
            "implantacao_id": str(contexto.get("deployment_id") or "")[:80] or None,
            "tipo_excecao": str(contexto.get("exception_type") or "")[:100] or None,
            "quadros_json": json.dumps(contexto.get("stack") or [], ensure_ascii=False, separators=(",", ":")),
        }
        _FILA_PERSISTENCIA.put_nowait(seguro)
    except Full:
        # O stdout continua sendo a fonte de contingência mesmo se a fila lotar.
        try:
            sys.stderr.write("operational_log_queue_full; event retained in application stdout logs\n")
        except Exception:
            pass


def _rota_da_requisicao(request) -> str:
    rota = request.scope.get("route")
    caminho = getattr(rota, "path", None)
    if isinstance(caminho, str) and _ROTA_SEGURA.fullmatch(caminho):
        return caminho
    return "<unmatched>"


def _quadros_seguros(erro: BaseException | None) -> list[dict[str, str | int]]:
    if erro is None or erro.__traceback__ is None:
        return []
    return [
        {"file": Path(quadro.filename).name[:100], "function": quadro.name[:100], "line": quadro.lineno}
        for quadro in traceback.extract_tb(erro.__traceback__)[-8:]
    ]


def _correlacao_valida(valor: str | None) -> str:
    try:
        return str(UUID(str(valor)))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


def definir_correlacao_operacional(valor: str):
    """Propaga o identificador da requisição para logs gerados em seus serviços."""
    return _CORRELACAO_REQUISICAO.set(_correlacao_valida(valor))


def restaurar_correlacao_operacional(token) -> None:
    _CORRELACAO_REQUISICAO.reset(token)


def _implantacao() -> str | None:
    # Este identificador não é segredo; só é incluído quando a Railway o fornece.
    valor = os.getenv("RAILWAY_DEPLOYMENT_ID", "")
    return valor[:80] if valor and _COMPONENTE_SEGURO.fullmatch(valor) else None


def registrar_log_requisicao(
    request,
    *,
    status: int,
    duracao_ms: float,
    correlacao_id: str | None = None,
    erro: BaseException | None = None,
) -> None:
    """Registra método, rota-modelo, status e duração; nunca lê query ou corpo."""
    metodo = str(getattr(request, "method", "OTHER")).upper()
    if not _METODO_SEGURO.fullmatch(metodo):
        metodo = "OTHER"

    contexto: dict[str, object] = {
        "method": metodo,
        "route": _rota_da_requisicao(request),
        "http_status": int(status),
        "duration_ms": round(max(0.0, float(duracao_ms)), 2),
        "correlation_id": _correlacao_valida(
            correlacao_id or getattr(getattr(request, "state", None), "correlacao_id", None)
        ),
    }
    deployment = _implantacao()
    if deployment:
        contexto["deployment_id"] = deployment
    if erro is not None:
        contexto["exception_type"] = type(erro).__name__[:100]
        quadros = _quadros_seguros(erro)
        if quadros:
            contexto["stack"] = quadros

    if status >= 500:
        nivel = logging.ERROR
    elif status >= 400 or duracao_ms >= 2500:
        nivel = logging.WARNING
    else:
        nivel = logging.INFO
    logging.getLogger("jurishome.http").log(
        nivel, "http_request", extra={"log_context": contexto}
    )
    _enfileirar_persistencia(
        nivel=nivel, componente="jurishome.http", evento="http_request", contexto=contexto
    )


async def processar_requisicao_com_log(request, call_next):
    """Registra a requisição e converte falhas inesperadas em resposta segura.

    A exceção não é repassada ao servidor ASGI: alguns servidores imprimem o
    traceback e a mensagem original, que podem conter valores sensíveis.
    """
    from services.erros import resposta_erro
    from time import perf_counter

    inicio = perf_counter()
    try:
        resposta = await call_next(request)
    except Exception as erro:
        registrar_log_requisicao(
            request,
            status=500,
            duracao_ms=(perf_counter() - inicio) * 1000,
            correlacao_id=getattr(getattr(request, "state", None), "correlacao_id", None),
            erro=erro,
        )
        resposta = resposta_erro(request, 500)
        correlacao_id = getattr(getattr(request, "state", None), "correlacao_id", None)
        if correlacao_id:
            resposta.headers["X-Correlation-ID"] = correlacao_id
        return resposta

    registrar_log_requisicao(
        request,
        status=resposta.status_code,
        duracao_ms=(perf_counter() - inicio) * 1000,
        correlacao_id=resposta.headers.get("X-Correlation-ID"),
    )
    return resposta


def registrar_falha_operacional(
    *, componente: str, operacao: str, erro: BaseException,
    correlacao_id: str | None = None,
) -> None:
    """Registra tipo e localização do erro sem guardar sua mensagem ou valores."""
    if not _COMPONENTE_SEGURO.fullmatch(componente):
        componente = "operacao"
    if not _COMPONENTE_SEGURO.fullmatch(operacao):
        operacao = "indefinida"
    if correlacao_id is None:
        # A rotina pode rodar dentro de uma requisição ou em background.
        correlacao_id = _CORRELACAO_REQUISICAO.get()
    contexto: dict[str, object] = {
        "operation": operacao,
        "exception_type": type(erro).__name__[:100],
        "correlation_id": _correlacao_valida(correlacao_id),
    }
    deployment = _implantacao()
    if deployment:
        contexto["deployment_id"] = deployment
    quadros = _quadros_seguros(erro)
    if quadros:
        contexto["stack"] = quadros
    nome_logger = f"jurishome.{componente}"
    logging.getLogger(nome_logger).error(
        "operation_failed", extra={"log_context": contexto}
    )
    _enfileirar_persistencia(
        nivel=logging.ERROR,
        componente=nome_logger,
        evento="operation_failed",
        contexto=contexto,
    )
