"""Migra segredos TOTP para chave independente, sem imprimir credenciais.

Execute com o servidor parado: python migrar_seguranca.py --apply
Para rotação futura: python migrar_seguranca.py --apply --rotate
"""
import argparse
import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet
from dotenv import dotenv_values
from sqlalchemy.orm import Session


def recifrar(db, chaves, destino):
    from model.models import Usuario
    # Valida todos antes de alterar qualquer registro.
    usuarios = db.query(Usuario).filter(Usuario.totp_secret.isnot(None)).all()
    novos = [(usuario, destino.encrypt(chaves.decrypt(usuario.totp_secret.encode("ascii"))).decode("ascii")) for usuario in usuarios]
    for usuario, cifrado in novos:
        usuario.totp_secret = cifrado
    db.flush()
    return len(novos)


def escrever_env(caminho, valores):
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    chaves = set(valores)
    linhas = [linha for linha in linhas if linha.split("=", 1)[0].strip() not in chaves]
    linhas.extend(f"{chave}={valor}" for chave, valor in valores.items() if valor)
    temporario = caminho.with_name(".env.auth.tmp")
    temporario.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplica a migração; sem esta opção apenas verifica.")
    parser.add_argument("--rotate", action="store_true", help="Gera nova chave TOTP independente.")
    args = parser.parse_args()
    caminho = Path(__file__).resolve().parent / ".env"
    if not caminho.is_file():
        raise RuntimeError("É necessário um .env local para esta migração.")
    from database import engine, Base
    from model.models import Usuario
    dados = {**dotenv_values(caminho), **os.environ}
    chave_atual = dados.get("TOTP_ENCRYPTION_KEY")
    nova = Fernet.generate_key().decode("ascii") if args.rotate or not chave_atual else chave_atual
    anteriores = [item.strip() for item in dados.get("TOTP_PREVIOUS_KEYS", "").split(",") if item.strip()]
    if args.rotate and chave_atual:
        anteriores.insert(0, chave_atual)
    legada = dados.get("TOTP_LEGACY_JWT_KEY") or dados.get("JurisHome_senha")
    if not legada:
        raise RuntimeError("Chave legada não disponível para verificar a migração.")
    chaves = MultiFernet([Fernet(item.encode("ascii")) for item in [nova, *anteriores]] +
        [Fernet(base64.urlsafe_b64encode(hashlib.sha256(legada.encode("utf-8")).digest()))])
    with Session(engine) as db:
        quantidade = recifrar(db, chaves, Fernet(nova.encode("ascii")))
        if not args.apply:
            db.rollback()
            print(f"Verificação concluída: {quantidade} configurações legíveis. Nenhuma alteração aplicada.")
            return
        backup = caminho.with_name(".env.auth-backup-" + __import__("uuid").uuid4().hex)
        backup.write_bytes(caminho.read_bytes())
        # Primeiro publica ambas as chaves: se houver interrupção, dados antigos ainda são legíveis.
        escrever_env(caminho, {"TOTP_ENCRYPTION_KEY": nova, "TOTP_PREVIOUS_KEYS": ",".join(anteriores), "TOTP_LEGACY_JWT_KEY": legada})
        db.commit()
        # Verificação independente: todos os registros devem ser legíveis só com a chave nova.
        for usuario in db.query(Usuario).filter(Usuario.totp_secret.isnot(None)):
            Fernet(nova.encode("ascii")).decrypt(usuario.totp_secret.encode("ascii"))
        escrever_env(caminho, {"TOTP_LEGACY_JWT_KEY": ""})
    Base.metadata.create_all(engine)
    print(f"Migração concluída: {quantidade} configurações recifradas; tabelas de autenticação criadas.")
    print("Backup do .env preservado localmente. Reinicie o servidor para carregar a chave independente.")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        print(f"Migração interrompida ({type(erro).__name__}). Nenhum segredo foi exibido. Preserve as chaves de transição e investigue antes de reiniciar.")
        raise SystemExit(1)
