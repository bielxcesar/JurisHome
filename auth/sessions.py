import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Response
from sqlalchemy.exc import IntegrityError

from auth.security import _decodificar_token, criar_access_token
from model.models import DesafioConsumido, CodigoTotpConsumido, RefreshToken, SessaoAutenticada, Usuario


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(valor):
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def negar():
    return HTTPException(status_code=401, detail="Autorização inválida, expirada ou já utilizada.")


def garantir_transacao(db):
    # sqlite3 em modo legado não abre BEGIN para SELECT/SAVEPOINT.
    # Sem isto, liberar o savepoint poderia persistir um consumo antes do commit externo.
    conexao = db.connection()
    if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
        conexao.exec_driver_sql("BEGIN IMMEDIATE")


def validar_revogacao(usuario, emitido_em):
    limite = usuario.token_validos_apos
    if limite:
        if limite.tzinfo is None:
            limite = limite.replace(tzinfo=timezone.utc)
        if emitido_em <= limite.timestamp():
            raise negar()


def consumir_desafio(db, token, usuario, tipo):
    garantir_transacao(db)
    usuario = db.query(Usuario).filter_by(uuid=usuario.uuid).populate_existing().with_for_update().one()
    payload = _decodificar_token(token)
    esperado = digest(usuario.email) if tipo == "recuperacao_senha" else str(usuario.uuid)
    if payload.get("tipo") != tipo or payload["sub"] != esperado or not payload.get("jti"):
        raise negar()
    validar_revogacao(usuario, payload["iat"])
    try:
        with db.begin_nested():
            db.add(DesafioConsumido(digest=digest(token), usuario_id=usuario.uuid,
                expira_em=datetime.fromtimestamp(payload["exp"], timezone.utc).replace(tzinfo=None)))
            db.flush()
    except IntegrityError as erro:
        raise negar() from erro


def consumir_totp(db, usuario, segredo, codigo, janela=2):
    garantir_transacao(db)
    import pyotp
    totp = pyotp.TOTP(segredo)
    intervalo_atual = int(datetime.now(timezone.utc).timestamp()) // totp.interval
    intervalo = next((i for i in range(intervalo_atual - janela, intervalo_atual + janela + 1)
        if hmac.compare_digest(totp.generate_otp(i), codigo)), None)
    if intervalo is None:
        raise negar()
    try:
        with db.begin_nested():
            db.add(CodigoTotpConsumido(usuario_id=usuario.uuid, segredo_digest=digest(segredo), intervalo=intervalo))
            db.flush()
    except IntegrityError as erro:
        raise negar() from erro


def criar_refresh(db, sessao_id):
    token = secrets.token_urlsafe(48)
    db.add(RefreshToken(digest=digest(token), sessao_id=sessao_id))
    db.flush()
    return token


def renovar_sessao(db, token):
    garantir_transacao(db)
    registro = db.get(RefreshToken, digest(token)) if token else None
    sessao = db.query(SessaoAutenticada).filter_by(id=registro.sessao_id).populate_existing().with_for_update().first() if registro else None
    if not sessao or sessao.revogada or sessao.expira_em <= agora():
        raise negar()
    # UPDATE condicional impede duas renovações com o mesmo token, inclusive entre processos.
    alterados = db.query(RefreshToken).filter_by(digest=registro.digest, usado=False).update({"usado": True})
    if alterados != 1:
        db.query(SessaoAutenticada).filter_by(id=sessao.id).update({"revogada": True})
        db.commit()
        raise negar()
    usuario = db.get(Usuario, sessao.usuario_id)
    if not usuario or not usuario.is_2fa_enabled or not usuario.totp_secret:
        db.rollback()
        raise negar()
    validar_revogacao(usuario, sessao.criada_em.replace(tzinfo=timezone.utc).timestamp())
    bloqueio = usuario.bloqueado_ate
    if bloqueio and bloqueio.replace(tzinfo=None) > agora():
        db.rollback()
        raise negar()
    novo_refresh = criar_refresh(db, sessao.id)
    acesso = criar_access_token(usuario, sessao_id=sessao.id)
    db.commit()
    return acesso, novo_refresh, max(0, int((sessao.expira_em - agora()).total_seconds()))


def salvar_refresh(response: Response, token, max_age):
    import os
    response.set_cookie("jurishome_refresh_token", token, max_age=max_age, httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="strict", path="/")


def apagar_cookies(response):
    response.delete_cookie("jurishome_access_token", path="/")
    response.delete_cookie("jurishome_refresh_token", path="/")
