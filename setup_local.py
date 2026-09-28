#Cria a configuracao local sem sobrescrever um .env existente.
from pathlib import Path
import secrets
import sys


ROOT = Path(__file__).resolve().parent
PLACEHOLDER = "__GERAR_CHAVE_LOCAL__"


def preparar_ambiente(diretorio: Path = ROOT) -> bool:
    exemplo = diretorio / ".env.example"
    destino = diretorio / ".env"

    if destino.exists():
        print("O arquivo .env ja existe; ele foi mantido sem alteracoes.")
        return False

    if not exemplo.is_file():
        raise FileNotFoundError(".env.example nao encontrado na pasta do projeto.")

    conteudo = exemplo.read_text(encoding="utf-8")
    if conteudo.count(PLACEHOLDER) != 1:
        raise ValueError("O modelo .env.example precisa conter exatamente um marcador de chave local.")

    destino.write_text(
        conteudo.replace(PLACEHOLDER, secrets.token_urlsafe(48)),
        encoding="utf-8",
    )
    print("Configuracao local criada em .env com uma chave aleatoria e banco SQLite.")
    print("Nao compartilhe nem versione esse arquivo.")
    return True


if __name__ == "__main__":
    try:
        preparar_ambiente()
    except (OSError, ValueError) as erro:
        print(f"Erro ao preparar ambiente: {erro}", file=sys.stderr)
        raise SystemExit(1) from erro
