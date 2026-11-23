import base64
import hashlib
import os
import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session, object_session

from database import get_db
from model.models import Usuario, TipoUsuario, SessaoAutenticada, PresencaSessao
from services.auditoria import definir_ator_auditoria
from services.lgpd import aceite_pendente
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JurisHome_senha")
if not SECRET_KEY:

    raise RuntimeError(
        "A variável de ambiente 'JurisHome_senha' não está definida. "
        "Defina-a com uma chave secreta segura para a aplicação."
    )

if len(SECRET_KEY.encode("utf-8")) < 32 or SECRET_KEY == "__GERAR_CHAVE_LOCAL__":
    raise RuntimeError("JurisHome_senha deve ser uma chave aleatória com pelo menos 32 bytes.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
PRESENCA_SESSAO_SEGUNDOS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
SESSAO_PERSISTENTE_MINUTOS = 15

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _decodificar_token(token: str) -> dict:
    """Exige o contrato comum a todos os tokens, além da assinatura."""
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"require": ["sub", "tipo", "iat", "exp"]},
        )
        if not isinstance(payload["sub"], str) or not payload["sub"].strip():
            raise ValueError("Identificador inválido")
        for campo in ("iat", "exp"):
            valor = payload[campo]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
                raise ValueError("Data inválida")
            datetime.fromtimestamp(valor, tz=timezone.utc)
        if payload["exp"] <= payload["iat"]:
            raise ValueError("Validade inválida")
        return payload
    except (ValueError, TypeError, OverflowError, OSError) as erro:
        raise jwt.InvalidTokenError("Token inválido.") from erro


def hash_senha(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")
    if len(senha_bytes) > 72:
        raise ValueError("A senha não pode ultrapassar 72 bytes.")
    return bcrypt.hashpw(senha_bytes, bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    if not isinstance(senha, str) or not isinstance(senha_hash, str):
        return False
    senha_bytes = senha.encode("utf-8")
    if len(senha_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(senha_bytes, senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def prazo_sessao(sessao: SessaoAutenticada) -> datetime:
    return sessao.expira_em


def criar_access_token(
    usuario: Usuario,
    lembrar_conectado: bool = False,
    *,
    sessao: SessaoAutenticada | None = None,
) -> str:
    agora = datetime.now(timezone.utc)
    validade = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    if sessao is None:
        minutos = ACCESS_TOKEN_EXPIRE_MINUTES
        db = object_session(usuario)
        if db is None:
            raise ValueError("A emissão de sessão exige usuário persistido.")
        # O bloqueio da conta serializa logins simultâneos no PostgreSQL.
        db.query(Usuario).filter_by(uuid=usuario.uuid).with_for_update().one()
        db.query(SessaoAutenticada).filter_by(
            usuario_id=usuario.uuid, revogada=False,
        ).update({"revogada": True}, synchronize_session=False)
        sessao = SessaoAutenticada(
            id=str(uuid.uuid4()), usuario_id=usuario.uuid,
            criada_em=agora.replace(tzinfo=None),
            expira_em=(agora + timedelta(minutes=minutos)).replace(tzinfo=None),
        )
        db.add(sessao)
        db.flush()
        db.add(PresencaSessao(sessao_id=sessao.id, confirmada_em=agora.replace(tzinfo=None)))
        db.commit()
    expira_em = min(agora + validade, prazo_sessao(sessao).replace(tzinfo=timezone.utc))
    payload = {
        "sub": str(usuario.uuid),
        "tipo": "acesso",
        "sid": sessao.id,
        "iat": agora.timestamp(),
        "exp": expira_em,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def criar_token_2fa_pendente(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.uuid),
            "tipo": "2fa_pendente",
            "iat": agora.timestamp(),
            "jti": secrets.token_urlsafe(32),
            "exp": agora + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def criar_token_configuracao_2fa(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.uuid),
            "tipo": "2fa_configuracao",
            "iat": agora.timestamp(),
            "jti": secrets.token_urlsafe(32),
            "exp": agora + timedelta(minutes=10),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def criar_token_recuperacao_senha(email_hash: str) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": email_hash,
            "tipo": "recuperacao_senha",
            "iat": agora.timestamp(),
            "jti": secrets.token_urlsafe(32),
            "exp": agora + timedelta(minutes=10),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decodificar_token_recuperacao_senha(token: str) -> str:
    try:
        payload = _decodificar_token(token)
    except PyJWTError as erro:
        raise ValueError("Desafio de recuperação inválido ou expirado.") from erro

    if payload.get("tipo") != "recuperacao_senha" or not payload.get("sub"):
        raise ValueError("Desafio de recuperação inválido ou expirado.")
    return str(payload["sub"])


def criar_token_nova_senha(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.uuid),
            "tipo": "nova_senha",
            "iat": agora.timestamp(),
            "jti": secrets.token_urlsafe(32),
            "exp": agora + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decodificar_token_nova_senha(token: str) -> tuple[str, float]:
    try:
        payload = _decodificar_token(token)
    except PyJWTError as erro:
        raise ValueError("Autorização para redefinir senha inválida ou expirada.") from erro

    usuario_uuid = payload.get("sub")
    emitido_em = payload.get("iat")
    if payload.get("tipo") != "nova_senha" or not usuario_uuid or emitido_em is None:
        raise ValueError("Autorização para redefinir senha inválida ou expirada.")
    return str(usuario_uuid), float(emitido_em)


def decodificar_token_2fa_pendente(token: str) -> str:
    try:
        payload = _decodificar_token(token)
    except PyJWTError as erro:
        raise ValueError("Desafio de duas etapas inválido ou expirado.") from erro

    if payload.get("tipo") != "2fa_pendente" or not payload.get("sub"):
        raise ValueError("Desafio de duas etapas inválido ou expirado.")
    return str(payload["sub"])


def decodificar_token_configuracao_2fa(token: str) -> str:
    try:
        payload = _decodificar_token(token)
    except PyJWTError as erro:
        raise ValueError("Configuração de duas etapas inválida ou expirada.") from erro

    if payload.get("tipo") != "2fa_configuracao" or not payload.get("sub"):
        raise ValueError("Configuração de duas etapas inválida ou expirada.")
    return str(payload["sub"])


def _carregar_fernet():
    try:
        from cryptography import fernet
    except ImportError as erro:
        raise RuntimeError("Dependência de criptografia indisponível.") from erro
    return fernet


def cifrar_segredo_2fa(segredo: str) -> str:
    return _chaves_2fa()[0].encrypt(segredo.encode("utf-8")).decode("utf-8")


def _chaves_2fa():
    Fernet = _carregar_fernet().Fernet
    chave = os.getenv("TOTP_ENCRYPTION_KEY")
    if not chave:
        raise RuntimeError("Configure TOTP_ENCRYPTION_KEY com uma chave Fernet independente.")
    anteriores = [item.strip() for item in os.getenv("TOTP_PREVIOUS_KEYS", "").split(",") if item.strip()]
    try:
        chaves = [Fernet(item.encode("ascii")) for item in [chave, *anteriores]]
        legada = os.getenv("TOTP_LEGACY_JWT_KEY")
        if legada:
            chaves.append(Fernet(base64.urlsafe_b64encode(hashlib.sha256(legada.encode("utf-8")).digest())))
        return chaves
    except (ValueError, UnicodeError) as erro:
        raise RuntimeError("Configuração de chaves TOTP inválida.") from erro


def decifrar_segredo_2fa(segredo_cifrado: str) -> str:
    fernet = _carregar_fernet()
    try:
        return fernet.MultiFernet(_chaves_2fa()).decrypt(segredo_cifrado.encode("utf-8")).decode("utf-8")
    except (fernet.InvalidToken, ValueError, UnicodeError) as erro:
        raise ValueError("Não foi possível ler a configuração de duas etapas.") from erro


def get_current_user_sem_aceite(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token or request.cookies.get("jurishome_access_token")
    if not token:
        raise credenciais_invalidas

    try:
        payload = _decodificar_token(token)
    except PyJWTError:
        raise credenciais_invalidas

    usuario_uuid = payload.get("sub")
    emitido_em = payload.get("iat")
    if payload.get("tipo") != "acesso" or usuario_uuid is None or emitido_em is None:
        raise credenciais_invalidas

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if usuario is None or not usuario.is_2fa_enabled or not usuario.totp_secret:
        raise credenciais_invalidas

    if usuario.e_root_admin:
        roots = db.query(Usuario.uuid).filter(Usuario.e_root_admin != False).limit(2).all()
        if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR or len(roots) != 1 or roots[0].uuid != usuario.uuid:
            raise HTTPException(status_code=403, detail="Configuração de administrador principal inconsistente. Acesso root bloqueado até correção.")

    agora_utc = datetime.now(timezone.utc)
    sessao = db.get(SessaoAutenticada, payload.get("sid")) if isinstance(payload.get("sid"), str) else None
    if sessao and sessao.usuario_id == usuario.uuid and sessao_substituida(db, sessao):
        raise erro_novo_acesso()
    if (not sessao or sessao.usuario_id != usuario.uuid or sessao.revogada
            or prazo_sessao(sessao) <= agora_utc.replace(tzinfo=None)):
        raise credenciais_invalidas
    presenca = db.get(PresencaSessao, sessao.id)
    if presenca is None or presenca.confirmada_em + timedelta(seconds=PRESENCA_SESSAO_SEGUNDOS) <= agora_utc.replace(tzinfo=None):
        raise credenciais_invalidas
    bloqueado_ate = usuario.bloqueado_ate
    if bloqueado_ate and bloqueado_ate.tzinfo is None:
        bloqueado_ate = bloqueado_ate.replace(tzinfo=timezone.utc)
    if bloqueado_ate and bloqueado_ate > agora_utc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta temporariamente bloqueada.",
        )

    # Se o usuário trocou a senha ou foi deslogado à força depois que esse
    # token foi emitido, o token antigo não vale mais.
    if usuario.token_validos_apos:
        iat_dt = datetime.fromtimestamp(emitido_em, tz=timezone.utc)
        token_validos_apos = usuario.token_validos_apos
        if token_validos_apos.tzinfo is None:
            token_validos_apos = token_validos_apos.replace(tzinfo=timezone.utc)
        if iat_dt < token_validos_apos or sessao.criada_em.replace(tzinfo=timezone.utc) <= token_validos_apos:
            raise credenciais_invalidas

    definir_ator_auditoria(usuario)
    request.state.tipo_usuario = usuario.tipo_usuario.value
    return usuario


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario = get_current_user_sem_aceite(request, token, db)
    if aceite_pendente(db, usuario):
        raise HTTPException(428, "Leia e confirme os documentos legais atualizados para continuar.")
    return usuario


def get_current_user_optional(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario | None:

    try:
        return get_current_user(request=request, token=token, db=db)
    except HTTPException:
        return None


def get_current_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario


def sessao_substituida(db: Session, sessao: SessaoAutenticada) -> bool:
    if not sessao.revogada:
        return False
    usuario = db.get(Usuario, sessao.usuario_id)
    # Troca de senha e intervenção administrativa não são apresentadas como novo login.
    if not usuario or (usuario.token_validos_apos and sessao.criada_em <= usuario.token_validos_apos.replace(tzinfo=None)):
        return False
    return db.query(SessaoAutenticada.id).filter(
        SessaoAutenticada.usuario_id == sessao.usuario_id,
        SessaoAutenticada.id != sessao.id,
        SessaoAutenticada.criada_em >= sessao.criada_em,
        SessaoAutenticada.revogada.is_(False),
        SessaoAutenticada.expira_em > datetime.now(timezone.utc).replace(tzinfo=None),
    ).first() is not None


def erro_novo_acesso() -> HTTPException:
    return HTTPException(401, "Sua sessão foi encerrada porque houve um novo acesso à sua conta. Entre novamente para continuar.",
                         headers={"WWW-Authenticate": "Bearer", "X-Session-Reason": "novo_acesso"})
