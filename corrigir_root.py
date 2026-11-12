"""Correção explícita de duplicidade legada; não escolhe um root automaticamente."""
import argparse
from database import Base, SessionLocal, engine
from model import models
from services.root_unico import corrigir_duplicidade, roots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True, help='Conta root que será preservada')
    parser.add_argument('--aplicar', action='store_true', help='Rebaixar os outros roots, revogar sessões e instalar índice único')
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not args.aplicar:
            for usuario in roots(db):
                print(usuario.email, '— manter' if usuario.email.lower() == args.email.lower() else '— perderá privilégio root')
            print('Simulação. Nenhum privilégio foi alterado.')
            return 0
        alterados = corrigir_duplicidade(db, args.email)
        print(f'Root preservado: {args.email}. Contas rebaixadas: {len(alterados)}. Índice único instalado.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
