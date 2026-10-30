"""Cria o primeiro administrador como root e os seguintes como suporte.

Defina JURISHOME_ADMIN_EMAIL, JURISHOME_ADMIN_SENHA e JURISHOME_ADMIN_NOME 
antes de executar, ou informe os dados interativamente no terminal.
"""

import os
import getpass
import re
import sys

from auth.security import hash_senha
from database import Base, SessionLocal, engine
from model.models import TipoUsuario, Usuario  # registra os modelos no metadata
from auth.sessions import garantir_transacao
from services.root_unico import garantir_root_unico
from sqlalchemy.exc import IntegrityError


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
        
        # Agora exige o nome interativamente se a variável de ambiente não estiver preenchida
        nome = obrigatorio("JURISHOME_ADMIN_NOME", "Nome do administrador (publicador): ")
        
        if len(nome) < 3:
            raise ValueError("O nome deve ter ao menos 3 caracteres.")
        if len(senha) < 8:
            raise ValueError("A senha deve ter ao menos 8 caracteres.")
        if len(senha.encode('utf-8')) > 72 or not re.search(r'[A-Za-z]', senha) or not re.search(r'\d', senha):
            raise ValueError("A senha deve ter letras e números e no máximo 72 bytes.")
            
    except (EOFError, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        garantir_root_unico(engine)
        garantir_transacao(db)
        root = db.query(Usuario).filter(Usuario.e_root_admin != False).first()
        if root:
            if root.email.lower() == email:
                print("O administrador principal já está configurado. Nenhum dado foi alterado.")
                return 0
        primeiro_root = root is None
        existente = db.query(Usuario).filter(Usuario.email == email).first()
        if existente and existente.tipo_usuario != TipoUsuario.ADMINISTRADOR:
            print("Erro: o e-mail informado já pertence a um estudante.", file=sys.stderr)
            return 1
        if existente and existente.senha_hash:
            print("Erro: este e-mail já pertence a uma conta configurada. O script não promove contas de suporte automaticamente.", file=sys.stderr)
            return 1

        if existente:
            existente.nome = nome
            existente.senha_hash = hash_senha(senha)
            existente.e_root_admin = primeiro_root
        else:
            db.add(
                Usuario(
                    nome=nome,
                    email=email,
                    senha_hash=hash_senha(senha),
                    tipo_usuario=TipoUsuario.ADMINISTRADOR,
                    e_root_admin=primeiro_root,
                    consentimento_lgpd=True,
                )
            )
        db.commit()
        perfil = "principal (root)" if primeiro_root else "de suporte (sem privilégios root)"
        print(f"Administrador {perfil} '{nome}' criado. O primeiro acesso exige a configuração do 2FA.")
        return 0
    except (IntegrityError, RuntimeError) as erro:
        db.rollback()
        print("Erro: não foi possível cadastrar a conta. Verifique e-mail duplicado ou criação simultânea e tente novamente; a regra de root único foi preservada.", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
