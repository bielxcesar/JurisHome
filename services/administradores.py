"""Manutenção de contas administrativas, exclusiva do administrador principal."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth.security import get_current_user
from auth.sessions import garantir_transacao
from model.models import AdministradorExcluido, Conteudo, SessaoAutenticada, TipoUsuario, Usuario
from services.imagens import url_imagem_segura


def exigir_root(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR or not usuario.e_root_admin:
        raise HTTPException(403, 'Somente o administrador principal pode gerenciar outros administradores.')
    return usuario


def buscar_admin(db: Session, usuario_id: str, root: Usuario, bloquear=False) -> Usuario:
    if bloquear:
        garantir_transacao(db)
    consulta = db.query(Usuario).filter(Usuario.uuid == usuario_id, Usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR)
    if bloquear:
        consulta = consulta.with_for_update()
    alvo = consulta.first()
    if alvo is None or db.get(AdministradorExcluido, usuario_id):
        raise HTTPException(404, 'Administrador não encontrado.')
    if alvo.e_root_admin or alvo.uuid == root.uuid:
        raise HTTPException(403, 'A conta principal é protegida. Use Meu perfil para suas próprias informações.')
    return alvo


def revogar_sessoes(db: Session, alvo: Usuario):
    alvo.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(SessaoAutenticada).filter_by(usuario_id=alvo.uuid).update({'revogada': True}, synchronize_session=False)


def serializar_admin(db: Session, alvo: Usuario):
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        'uuid': alvo.uuid, 'nome': alvo.nome, 'email': alvo.email,
        'foto': url_imagem_segura(alvo.foto_perfil),
        'criadoEm': alvo.criado_em.isoformat() if alvo.criado_em else None,
        'versao': alvo.atualizado_em.isoformat(),
        'is_2fa_enabled': alvo.is_2fa_enabled,
        'sessoesAtivas': db.query(SessaoAutenticada).filter(
            SessaoAutenticada.usuario_id == alvo.uuid, SessaoAutenticada.revogada.is_(False),
            SessaoAutenticada.expira_em > agora,
        ).count(),
        'totalMaterias': db.query(Conteudo).filter_by(autor_id=alvo.uuid).count(),
    }
