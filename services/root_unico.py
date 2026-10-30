"""Invariante: no máximo uma conta root, inclusive antes do primeiro login."""
from datetime import datetime, timezone

from auth.sessions import garantir_transacao
from model.models import Usuario, TipoUsuario, SessaoAutenticada
from services.auditoria import registrar_auditoria

NOME_INDICE = 'uq_usuarios_root_unico'


def roots(db):
    return db.query(Usuario).filter(Usuario.e_root_admin != False).all()


def instalar_indice(conexao):
    if conexao.dialect.name in {'sqlite', 'postgresql'}:
        # IF NOT EXISTS evita depender da reflexão de índices de expressão do SQLite.
        conexao.exec_driver_sql('CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_root_unico ON usuarios ((CASE WHEN e_root_admin THEN 1 ELSE NULL END))')
    elif conexao.dialect.name == 'mysql':
        # Índices funcionais são suportados pelo MySQL a partir de 8.0.13.
        from sqlalchemy import inspect
        if NOME_INDICE not in {i['name'] for i in inspect(conexao).get_indexes('usuarios')}:
            conexao.exec_driver_sql('CREATE UNIQUE INDEX uq_usuarios_root_unico ON usuarios ((CASE WHEN e_root_admin THEN 1 ELSE NULL END))')
    else:
        raise RuntimeError('Banco sem proteção de root configurada. A aplicação não será iniciada sem o índice único.')


def garantir_root_unico(engine):
    from sqlalchemy import select
    with engine.begin() as conexao:
        encontrados = conexao.execute(select(Usuario.uuid, Usuario.tipo_usuario).where(Usuario.e_root_admin != False)).all()
        if len(encontrados) > 1:
            raise RuntimeError('Mais de um root encontrado. Corrija explicitamente com corrigir_root.py --email EMAIL_DO_ROOT --aplicar antes de iniciar a aplicação.')
        if encontrados and encontrados[0].tipo_usuario != TipoUsuario.ADMINISTRADOR:
            raise RuntimeError('Conta root com perfil inválido. Corrija o cadastro antes de iniciar a aplicação.')
        instalar_indice(conexao)


def corrigir_duplicidade(db, email):
    garantir_transacao(db)
    encontrados = db.query(Usuario).filter(Usuario.e_root_admin != False).with_for_update().all()
    escolhido = next((u for u in encontrados if u.email.lower() == email.strip().lower()), None)
    if escolhido is None or escolhido.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise ValueError('O e-mail deve pertencer a uma das contas root existentes com perfil de administrador.')
    alterados = []
    for usuario in encontrados:
        if usuario.uuid == escolhido.uuid:
            continue
        usuario.e_root_admin = False
        usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
        db.query(SessaoAutenticada).filter_by(usuario_id=usuario.uuid).update({'revogada': True}, synchronize_session=False)
        registrar_auditoria(db, acao='root_duplicado_corrigido', recurso_tipo='usuario', recurso_id=usuario.uuid,
                            resultado='sucesso', usuario=escolhido,
                            detalhes={'root_preservado': escolhido.uuid, 'sessoes_revogadas': True})
        alterados.append(usuario.uuid)
    db.flush()
    instalar_indice(db.connection())
    db.commit()
    return alterados
