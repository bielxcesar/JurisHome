"""Remoção de dados diretos; resíduos técnicos continuam pseudonimizados."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_

from sqlalchemy.orm import Session

from model.models import (CodigoTotpConsumido, DesafioConsumido, Feedback, FeedbackAtendimento,
                          LogAuditoria, PresencaSessao, RefreshToken, SessaoAutenticada, Usuario)


TEXTO_ANONIMIZADO = "Conteúdo removido após solicitação do titular."


def _agora_sem_fuso() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def anonimizar_feedbacks_atendimento(db: Session, usuario_id: str) -> int:

    registros = db.query(FeedbackAtendimento).filter_by(usuario_id=usuario_id).all()
    for feedback in registros:
        anonimizar_feedback_atendimento(feedback)
    return len(registros)


def anonimizar_feedback_atendimento(feedback: FeedbackAtendimento) -> None:

    feedback.usuario_id = "titular-removido"
    feedback.usuario_nome = "Usuário anonimizado"
    feedback.usuario_email = "anonimizado@invalid.local"
    feedback.assunto = "Assunto anonimizado"
    feedback.mensagem = TEXTO_ANONIMIZADO
    feedback.avaliacao = None
    feedback.respostas_json = "[]"
    feedback.observacoes_json = "[]"
    feedback.historico_json = "[]"
    feedback.novo = False
    feedback.atualizado_em = datetime.now(timezone.utc)


def anonimizar_feedbacks_legados(db: Session, usuario_id: str) -> int:

    registros = db.query(Feedback).filter_by(usuario_id=usuario_id).all()
    for feedback in registros:
        feedback.mensagem = TEXTO_ANONIMIZADO
        feedback.usuario_id = None
    return len(registros)


def anonimizar_usuario(usuario: Usuario) -> None:

    usuario.nome = "Usuário anonimizado"
    usuario.email = f"anonimizado-{uuid4().hex}@invalid.local"
    usuario.senha_hash = None
    usuario.foto_perfil = None
    usuario.universidade = None
    usuario.especialidade_juridica = None
    usuario.totp_secret = None
    usuario.is_2fa_enabled = False
    usuario.tentativas_login_falhas = 0
    usuario.ultima_falha_login = None
    usuario.bloqueado_ate = None
    usuario.token_validos_apos = _agora_sem_fuso()


def remover_vinculos_desnecessarios(db: Session, usuario: Usuario) -> None:
    """Conta e provas de aceite remanescentes são pseudonimizadas, não anônimas."""
    sessoes = db.query(SessaoAutenticada.id).filter_by(usuario_id=usuario.uuid)
    db.query(RefreshToken).filter(RefreshToken.sessao_id.in_(sessoes)).delete(synchronize_session=False)
    db.query(PresencaSessao).filter(PresencaSessao.sessao_id.in_(sessoes)).delete(synchronize_session=False)
    db.query(SessaoAutenticada).filter_by(usuario_id=usuario.uuid).delete(synchronize_session=False)
    db.query(DesafioConsumido).filter_by(usuario_id=usuario.uuid).delete(synchronize_session=False)
    db.query(CodigoTotpConsumido).filter_by(usuario_id=usuario.uuid).delete(synchronize_session=False)
    logs = db.query(LogAuditoria).filter(or_(LogAuditoria.usuario_id == usuario.uuid,
                                             LogAuditoria.recurso_id == usuario.uuid)).all()
    for log in logs:
        log.usuario_id = None
        log.recurso_id = None
        log.detalhes_json = "{}"
        log.correlacao_id = str(uuid4())


def remover_foto_local(caminho: str | None) -> None:
    if not caminho or not caminho.startswith("/static/uploads/"):
        return
    raiz = (Path(__file__).resolve().parents[1] / "static/uploads").resolve()
    arquivo = (raiz / caminho.removeprefix("/static/uploads/")).resolve()
    if arquivo.parent == raiz and arquivo.is_file():
        arquivo.unlink()
