import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from model.models import Feedback, FeedbackAtendimento, Usuario


TEXTO_ANONIMIZADO = "Conteúdo removido após solicitação do titular."


def _agora_sem_fuso() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _historico_sem_conteudo_pessoal(valor: str | None) -> str:

    try:
        itens = json.loads(valor or "[]")
    except (TypeError, json.JSONDecodeError):
        itens = []

    historico_minimo = []
    if isinstance(itens, list):
        for item in itens:
            if not isinstance(item, dict):
                continue
            historico_minimo.append(
                {
                    "id": item.get("id"),
                    "tipo": item.get("tipo"),
                    "criadoEm": item.get("criadoEm"),
                    "visibilidade": item.get("visibilidade"),
                    "autor": "Registro anonimizado",
                    "descricao": TEXTO_ANONIMIZADO,
                }
            )
    return json.dumps(historico_minimo, ensure_ascii=False)


def anonimizar_feedbacks_atendimento(db: Session, usuario_id: str) -> int:

    registros = db.query(FeedbackAtendimento).filter_by(usuario_id=usuario_id).all()
    for feedback in registros:
        anonimizar_feedback_atendimento(feedback)
    return len(registros)


def anonimizar_feedback_atendimento(feedback: FeedbackAtendimento) -> None:

    feedback.usuario_nome = "Usuário anonimizado"
    feedback.usuario_email = "anonimizado@invalid.local"
    feedback.assunto = "Assunto anonimizado"
    feedback.mensagem = TEXTO_ANONIMIZADO
    feedback.avaliacao = None
    feedback.respostas_json = "[]"
    feedback.observacoes_json = "[]"
    feedback.historico_json = _historico_sem_conteudo_pessoal(feedback.historico_json)
    feedback.novo = False
    feedback.atualizado_em = datetime.now(timezone.utc)


def anonimizar_feedbacks_legados(db: Session, usuario_id: str) -> int:

    registros = db.query(Feedback).filter_by(usuario_id=usuario_id).all()
    for feedback in registros:
        feedback.mensagem = TEXTO_ANONIMIZADO
    return len(registros)


def anonimizar_usuario(usuario: Usuario) -> None:

    usuario.nome = "Usuário anonimizado"
    usuario.email = f"anonimizado-{usuario.uuid}@invalid.local"
    usuario.senha_hash = None
    usuario.universidade = None
    usuario.especialidade_juridica = None
    usuario.totp_secret = None
    usuario.is_2fa_enabled = False
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    usuario.token_validos_apos = _agora_sem_fuso()
