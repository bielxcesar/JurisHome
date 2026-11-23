"""Contas fictícias exclusivamente em um SQLite dedicado e identificado."""
import argparse
import base64
import getpass
import hashlib
import hmac
import os
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values

DESTINO = ROOT / 'tests' / 'dados_gerados' / 'usuarios_ficticios.sqlite3'
DOMINIO = 'example.invalid'
MARCA = 'jurishome-usuarios-ficticios-v1'


def verificar_ambiente():
    # As duas fontes são examinadas separadamente: uma não pode ocultar produção na outra.
    fontes = [dict(dotenv_values(ROOT / '.env')), dict(os.environ)]
    for fonte in fontes:
        for chave, valor in fonte.items():
            chave = chave.upper()
            valor = (valor or '').strip()
            if not valor:
                continue
            if chave.startswith('RAILWAY_') or (chave in {'ENV', 'ENVIRONMENT', 'APP_ENV', 'AMBIENTE', 'FLASK_ENV', 'NODE_ENV'} and valor.lower() in {'prod', 'production', 'producao', 'produção'}):
                raise RuntimeError('Execução recusada: configuração de produção ou Railway detectada.')
            if chave in {'DATABASE_URL', 'FEEDBACK_DATABASE_URL'} and not valor.startswith('sqlite:'):
                raise RuntimeError('Execução recusada: há banco configurado que não é SQLite.')
    if os.environ.get('JURISHOME_TEST_MODE') != '1':
        raise RuntimeError('Defina JURISHOME_TEST_MODE=1 para confirmar o uso de teste.')
    if DESTINO.parent.is_symlink() or DESTINO.is_symlink():
        raise RuntimeError('O destino não pode ser um link simbólico.')


def senha_para(chave, numero):
    if len(chave) < 16:
        raise ValueError('A frase secreta deve ter pelo menos 16 caracteres.')
    digest = hmac.new(chave.encode('utf-8'), f'jurishome-teste-{numero:03d}'.encode('ascii'), hashlib.sha256).digest()
    return 'J!7' + base64.urlsafe_b64encode(digest).decode('ascii')[:22]


def abrir():
    verificar_ambiente()
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    existia = DESTINO.exists()
    import sqlite3
    if existia:
        with closing(sqlite3.connect(f'{DESTINO.as_uri()}?mode=ro', uri=True)) as con:
            try:
                marcador = con.execute('SELECT marca FROM gerador_metadados').fetchone()
            except sqlite3.DatabaseError as erro:
                raise RuntimeError('Banco existente não pertence ao gerador; nenhuma alteração foi feita.') from erro
            if marcador != (MARCA,):
                raise RuntimeError('Banco existente não pertence ao gerador; nenhuma alteração foi feita.')
    else:
        with closing(sqlite3.connect(DESTINO)) as con, con:
            con.execute('CREATE TABLE gerador_metadados (marca TEXT NOT NULL)')
            con.execute('INSERT INTO gerador_metadados VALUES (?)', (MARCA,))
            con.execute('CREATE TABLE gerador_usuarios (usuario_id TEXT PRIMARY KEY NOT NULL)')
    os.environ['DATABASE_URL'] = 'sqlite:///' + DESTINO.as_posix()
    os.environ['FEEDBACK_DATABASE_URL'] = os.environ['DATABASE_URL']
    os.environ.setdefault('JurisHome_senha', base64.urlsafe_b64encode(os.urandom(32)).decode('ascii'))
    from sqlalchemy import create_engine
    from database import Base
    import model.models  # noqa: F401
    # Sempre criar uma conexão própria para o arquivo dedicado, mesmo se o
    # módulo database já tiver sido carregado em outro contexto.
    engine = create_engine('sqlite:///' + DESTINO.as_posix(), hide_parameters=True)
    Base.metadata.create_all(engine)
    return engine


def criar(chave):
    # Validar antes de tocar no banco.
    senha_para(chave, 1)
    engine = abrir()
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session
    from auth.security import hash_senha
    from model.models import TipoUsuario, Usuario
    from services.validacao import email_valido, nome_pessoa, nova_senha
    criados = 0
    with Session(engine) as sessao, sessao.begin():
        for numero in range(1, 101):
            email = email_valido(f'usuario{numero:03d}@{DOMINIO}')
            usuario = sessao.scalar(select(Usuario).where(Usuario.email == email))
            if usuario:
                pertence = sessao.execute(text('SELECT 1 FROM gerador_usuarios WHERE usuario_id = :id'), {'id': usuario.uuid}).first()
                if not pertence:
                    raise RuntimeError('Um e-mail fictício já pertence a outro registro; operação cancelada.')
                continue
            senha = nova_senha(senha_para(chave, numero))
            usuario = Usuario(nome=nome_pessoa('Pessoa Ficticia'), email=email, senha_hash=hash_senha(senha), tipo_usuario=TipoUsuario.ESTUDANTE, consentimento_lgpd=False)
            sessao.add(usuario)
            sessao.flush()
            sessao.execute(text('INSERT INTO gerador_usuarios (usuario_id) VALUES (:id)'), {'id': usuario.uuid})
            criados += 1
    engine.dispose()
    return criados


def remover():
    engine = abrir()
    from sqlalchemy import text
    # Sem cascata: se existirem vínculos, as restrições impedem excluir dados associados.
    with engine.begin() as con:
        con.exec_driver_sql('PRAGMA foreign_keys=ON')
        quantidade = con.execute(text('SELECT COUNT(*) FROM gerador_usuarios')).scalar_one()
        con.execute(text('DELETE FROM usuarios WHERE uuid IN (SELECT usuario_id FROM gerador_usuarios)'))
        con.execute(text('DELETE FROM gerador_usuarios'))
    engine.dispose()
    return quantidade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=['criar', 'remover', 'senha'])
    parser.add_argument('--numero', type=int, help='Número da conta entre 1 e 100, para a ação senha.')
    args = parser.parse_args()
    try:
        if args.acao == 'senha':
            verificar_ambiente()
            if args.numero is None or not 1 <= args.numero <= 100:
                raise ValueError('Informe --numero entre 1 e 100.')
            chave = getpass.getpass('Frase secreta usada na criação: ')
            print(senha_para(chave, args.numero))
        elif args.acao == 'criar':
            verificar_ambiente()
            chave = getpass.getpass('Frase secreta para as contas (mínimo 16 caracteres): ')
            if chave != getpass.getpass('Confirme a frase secreta: '):
                raise ValueError('As frases não conferem.')
            print(f'{criar(chave)} conta(s) criada(s).')
        else:
            print(f'{remover()} conta(s) removida(s).')
    except Exception as erro:
        print(f'Operação não concluída: {erro}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
