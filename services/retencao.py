from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from model.models import FeedbackAtendimento, LogAuditoria, Usuario
from services.auditoria import registrar_auditoria
from services.direitos_titular import anonimizar_feedback_atendimento


DIAS_FEEDBACK_APOS_ENCERRAMENTO = 180
DIAS_LOG_GERAL = 365
DIAS_LOG_INCIDENTE = 5 * 365
DIAS_ACEITE_APOS_ANONIMIZACAO = 5 * 365


def _sem_fuso(valor: datetime) -> datetime:
    return valor.astimezone(timezone.utc).replace(tzinfo=None) if valor.tzinfo else valor


def _log_ja_minimizado(log: LogAuditoria) -> bool:
    return log.usuario_id is None and log.recurso_id is None and log.detalhes_json == "{}"


def aplicar_retencao(
    db: Session,
    feedback_db: Session,
    *,
    agora: datetime | None = None,
    executar: bool = False,
) -> dict[str, int | bool]:

    referencia = _sem_fuso(agora or datetime.now(timezone.utc))
    limite_feedback = referencia - timedelta(days=DIAS_FEEDBACK_APOS_ENCERRAMENTO)
    limite_log = referencia - timedelta(days=DIAS_LOG_GERAL)
    limite_incidente = referencia - timedelta(days=DIAS_LOG_INCIDENTE)
    limite_aceite = referencia - timedelta(days=DIAS_ACEITE_APOS_ANONIMIZACAO)

    feedbacks = feedback_db.query(FeedbackAtendimento).filter(
        FeedbackAtendimento.status.in_(("Resolvido", "Arquivado")),
        FeedbackAtendimento.atualizado_em < limite_feedback,
        FeedbackAtendimento.usuario_email != "anonimizado@invalid.local",
    ).all()

    logs = db.query(LogAuditoria).all()
    logs_para_minimizar = []
    for log in logs:
        criado = _sem_fuso(log.criado_em)
        incidente = log.acao.startswith("incidente_")
        expirado = criado < (limite_incidente if incidente else limite_log)
        if expirado and not _log_ja_minimizado(log):
            logs_para_minimizar.append(log)

    aceites = db.query(Usuario).filter(
        Usuario.nome == "Usuário anonimizado",
        Usuario.token_validos_apos.is_not(None),
        Usuario.token_validos_apos < limite_aceite,
        Usuario.consentimento_lgpd.is_(True),
    ).all()

    resultado: dict[str, int | bool] = {
        "execucao_realizada": executar,
        "feedbacks_para_anonimizar": len(feedbacks),
        "logs_para_minimizar": len(logs_para_minimizar),
        "aceites_para_descartar": len(aceites),
    }
    if not executar:
        return resultado

    for feedback in feedbacks:
        anonimizar_feedback_atendimento(feedback)
    feedback_db.commit()

    for log in logs_para_minimizar:
        log.usuario_id = None
        log.recurso_id = None
        log.detalhes_json = "{}"
    for usuario in aceites:
        usuario.consentimento_lgpd = False
        usuario.data_consentimento = None
        usuario.versao_termos = None

    registrar_auditoria(
        db,
        acao="retencao_aplicada",
        recurso_tipo="governanca_dados",
        resultado="sucesso",
        detalhes={
            "feedbacks_anonimizados": len(feedbacks),
            "logs_minimizados": len(logs_para_minimizar),
            "aceites_descartados": len(aceites),
        },
    )
    db.commit()
    return resultado
