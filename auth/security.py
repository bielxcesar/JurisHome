import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from model.models import Usuario, TipoUsuario
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def criar_access_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.uuid),
        "iat": agora,
        "exp": agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        raise credenciais_invalidas

    usuario_uuid = payload.get("sub")
    emitido_em = payload.get("iat")
    if usuario_uuid is None or emitido_em is None:
        raise credenciais_invalidas

    usuario = db.query(Usuario).filter(Usuario.uuid == usuario_uuid).first()
    if usuario is None:
        raise credenciais_invalidas

    if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta temporariamente bloqueada.",
        )

    # Se o usuário trocou a senha ou foi deslogado à força depois que esse
    # token foi emitido, o token antigo não vale mais.
    if usuario.token_validos_apos:
        iat_dt = datetime.fromtimestamp(emitido_em, tz=timezone.utc)
        if iat_dt < usuario.token_validos_apos:
            raise credenciais_invalidas

    return usuario


def get_current_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return usuario