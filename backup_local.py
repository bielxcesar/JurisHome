"""Backup local do SQLite com rotação de 30 dias para o ambiente acadêmico."""

import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def caminho_sqlite(url: str) -> Path:
    configuracao = make_url(url)
    if not configuracao.drivername.startswith("sqlite") or not configuracao.database:
        raise ValueError("O backup local aceita somente DATABASE_URL SQLite.")
    caminho = configuracao.database
    if os.name == "nt" and caminho.startswith("/") and len(caminho) > 2 and caminho[2] == ":":
        caminho = caminho[1:]
    return Path(caminho).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria backup SQLite e remove cópias com mais de 30 dias.")
    parser.add_argument("--destino", default="backups", help="Diretório restrito para armazenar as cópias.")
    args = parser.parse_args()
    load_dotenv()

    origem = caminho_sqlite(os.getenv("DATABASE_URL", "sqlite:///./juris_home.db"))
    if not origem.is_file():
        raise FileNotFoundError(f"Banco local não encontrado: {origem}")

    destino = Path(args.destino).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(timezone.utc)
    arquivo = destino / f"jurishome-backup-{agora:%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(origem) as banco_origem, sqlite3.connect(arquivo) as banco_destino:
        banco_origem.backup(banco_destino)

    limite = agora - timedelta(days=30)
    removidos = 0
    for copia in destino.glob("jurishome-backup-*.db"):
        modificado = datetime.fromtimestamp(copia.stat().st_mtime, timezone.utc)
        if copia != arquivo and modificado < limite:
            copia.unlink()
            removidos += 1
    print(f"Backup criado: {arquivo}")
    print(f"Cópias vencidas removidas: {removidos}")


if __name__ == "__main__":
    main()
