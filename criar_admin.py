"""Cria o primeiro administrador do JurisHome de forma explícita e segura.

Defina JURISHOME_ADMIN_EMAIL e JURISHOME_ADMIN_SENHA antes de executar.
Nenhuma credencial padrão é gravada no código.
"""

import os
import getpass
import re
import sys

from auth.security import hash_senha
from database import Base, SessionLocal, engine
from model.models import TipoUsuario, Usuario  # registra os modelos no metadata


def obrigatorio(nome: str, prompt: str, oculto: bool = False) -> str:
    valor = os.getenv(nome, "").strip()
    if not valor:
        valor = (getpass.getpass(prompt) if oculto else input(prompt)).strip()
    if not valor:
        raise ValueError(f"Informe {nome} para continuar.")
    return valor


def main() -> int:
    try:
        email = obrigatorio("JURISHOME_ADMIN_EMAIL", "E-mail do administrador: ").lower()
        senha = obrigatorio("JURISHOME_ADMIN_SENHA", "Senha do administrador: ", oculto=True)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Informe um e-mail válido para o administrador.")
        nome = os.getenv("JURISHOME_ADMIN_NOME", "Administrador JurisHome").strip()
        if len(nome) < 3:
            raise ValueError("JURISHOME_ADMIN_NOME deve ter ao menos 3 caracteres.")
        if len(senha) < 8:
            raise ValueError("JURISHOME_ADMIN_SENHA deve ter ao menos 8 caracteres.")
    except (EOFError, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.email == email).first()
        if existente and existente.tipo_usuario != TipoUsuario.ADMINISTRADOR:
            print("Erro: o e-mail informado já pertence a um estudante.", file=sys.stderr)
            return 1
        if existente and existente.senha_hash:
            print("Já existe um administrador com senha configurada para este e-mail.")
            return 0

        if existente:
            existente.nome = nome
            existente.senha_hash = hash_senha(senha)
            existente.e_root_admin = True
        else:
            db.add(
                Usuario(
                    nome=nome,
                    email=email,
                    senha_hash=hash_senha(senha),
                    tipo_usuario=TipoUsuario.ADMINISTRADOR,
                    e_root_admin=True,
                    consentimento_lgpd=True,
                )
            )
        db.commit()
        print("Administrador configurado com sucesso.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
