import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from database import get_db
from model.models import Usuario, TipoUsuario
from services.auditoria import definir_ator_auditoria
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JurisHome_senha")
if not SECRET_KEY:

    raise RuntimeError(
        "A variável de ambiente 'JurisHome_senha' não está definida. "
        "Defina-a antes de iniciar a aplicação."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ACCESS_TOKEN_REMEMBER_DAYS = 14

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_senha(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")
    if len(senha_bytes) > 72:
        raise ValueError("A senha não pode ultrapassar 72 bytes.")
    return bcrypt.hashpw(senha_bytes, bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    senha_bytes = senha.encode("utf-8")
    if len(senha_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(senha_bytes, senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def criar_access_token(usuario: Usuario, lembrar_conectado: bool = False) -> str:
    agora = datetime.now(timezone.utc)
    validade = (
        timedelta(days=ACCESS_TOKEN_REMEMBER_DAYS)
        if lembrar_conectado
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(usuario.uuid),
        "tipo": "acesso",
        "iat": agora,
        "exp": agora + validade,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def criar_token_2fa_pendente(usuario: Usuario) -> str:
    """Cria um token curto que só pode ser usado na confirmação do 2FA."""
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.uuid),
            "tipo": "2fa_pendente",
            "iat": agora,
            "exp": agora + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def criar_token_configuracao_2fa(usuario: Usuario) -> str:
    """Cria um token curto para concluir a ativação obrigatória do 2FA."""
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.uuid),
            "tipo": "2fa_configuracao",
            "iat": agora,
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
            "iat": agora,
            "exp": agora + timedelta(minutes=10),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decodificar_token_recuperacao_senha(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
            "iat": agora,
            "exp": agora + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decodificar_token_nova_senha(token: str) -> tuple[str, int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError as erro:
        raise ValueError("Autorização para redefinir senha inválida ou expirada.") from erro

    usuario_uuid = payload.get("sub")
    emitido_em = payload.get("iat")
    if payload.get("tipo") != "nova_senha" or not usuario_uuid or emitido_em is None:
        raise ValueError("Autorização para redefinir senha inválida ou expirada.")
    return str(usuario_uuid), int(emitido_em)


def decodificar_token_2fa_pendente(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError as erro:
        raise ValueError("Desafio de duas etapas inválido ou expirado.") from erro

    if payload.get("tipo") != "2fa_pendente" or not payload.get("sub"):
        raise ValueError("Desafio de duas etapas inválido ou expirado.")
    return str(payload["sub"])


def decodificar_token_configuracao_2fa(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError as erro:
        raise ValueError("Configuração de duas etapas inválida ou expirada.") from erro

    if payload.get("tipo") != "2fa_configuracao" or not payload.get("sub"):
        raise ValueError("Configuração de duas etapas inválida ou expirada.")
    return str(payload["sub"])


def cifrar_segredo_2fa(segredo: str) -> str:
    """Protege o segredo TOTP antes de persistir no banco."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as erro:
        raise RuntimeError("Dependência de criptografia indisponível.") from erro

    chave = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
    return Fernet(chave).encrypt(segredo.encode("utf-8")).decode("utf-8")


def decifrar_segredo_2fa(segredo_cifrado: str) -> str:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError as erro:
        raise RuntimeError("Dependência de criptografia indisponível.") from erro

    chave = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
    try:
        return Fernet(chave).decrypt(segredo_cifrado.encode("utf-8")).decode("utf-8")
    except InvalidToken as erro:
        raise ValueError("Não foi possível ler a configuração de duas etapas.") from erro


def get_current_user(
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        raise credenciais_invalidas

    usuario_uuid = payload.get("sub")
    emitido_em = payload.get("iat")
    if payload.get("tipo") != "acesso" or usuario_uuid is None or emitido_em is None:
        raise credenciais_invalidas

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if usuario is None or not usuario.is_2fa_enabled or not usuario.totp_secret:
        raise credenciais_invalidas

    agora_utc = datetime.now(timezone.utc)
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
        if iat_dt < token_validos_apos:
            raise credenciais_invalidas

    definir_ator_auditoria(usuario)
    return usuario


def get_current_user_optional(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario | None:
    """Retorna o usuário quando a sessão é válida, sem tornar a rota obrigatória."""

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
