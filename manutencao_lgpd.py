import argparse
import json

from database import SessionLocal
from feedback_database import FeedbackSessionLocal
from services.retencao import aplicar_retencao


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula ou aplica a retenção de dados do JurisHome.")
    parser.add_argument(
        "--executar",
        action="store_true",
        help="Aplica as alterações. Sem esta opção, apenas mostra os registros alcançados.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    feedback_db = FeedbackSessionLocal()
    try:
        resultado = aplicar_retencao(db, feedback_db, executar=args.executar)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    finally:
        feedback_db.close()
        db.close()


if __name__ == "__main__":
    main()
