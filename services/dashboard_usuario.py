from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from model.models import (
    Categoria,
    CategoriaAcesso,
    ConteudoLeitura,
    fuso_br,
)


def registrar_acesso_categoria(
    db: Session,
    usuario_id: str,
    categoria_id: str,
    hoje: date | None = None,
) -> bool:
    """Registra no máximo um acesso por usuário, categoria e dia local."""
    data_atual = hoje or datetime.now(fuso_br).date()
    data_acesso = data_atual.isoformat()
    inicio_mes = data_atual.replace(day=1).isoformat()
    limpar_acessos_categoria_antigos(db, usuario_id, inicio_mes)
    chave = {
        "usuario_id": usuario_id,
        "categoria_id": categoria_id,
        "dia": data_acesso,
    }

    if db.query(CategoriaAcesso).filter_by(**chave).first():
        return False

    try:
        with db.begin_nested():
            db.add(CategoriaAcesso(**chave))
            db.flush()
    except IntegrityError:
        # A chave primária composta também protege contra cliques simultâneos.
        # O context manager já reverteu o savepoint; não desfazer transações
        # externas que possam ter sido abertas pelo chamador.
        if db.query(CategoriaAcesso).filter_by(**chave).first():
            return False
        raise

    db.commit()
    return True


def limpar_acessos_categoria_antigos(db: Session, usuario_id: str, inicio_mes: str) -> None:
    removidos = (
        db.query(CategoriaAcesso)
        .filter(
            CategoriaAcesso.usuario_id == usuario_id,
            CategoriaAcesso.dia < inicio_mes,
        )
        .delete(synchronize_session=False)
    )
    if removidos:
        db.commit()


def obter_dashboard_estudos(db: Session, usuario_id: str, hoje: date | None = None) -> dict:
    """Calcula as matérias consultadas e categorias acessadas pelo próprio usuário."""
    data_final = hoje or datetime.now(fuso_br).date()
    inicio_mes = data_final.replace(day=1).isoformat()
    fim_mes = data_final.isoformat()
    limpar_acessos_categoria_antigos(db, usuario_id, inicio_mes)

    materias_total = (
        db.query(func.count(func.distinct(ConteudoLeitura.conteudo_id)))
        .filter(ConteudoLeitura.usuario_id == usuario_id)
        .scalar()
        or 0
    )
    acessos_por_categoria = (
        db.query(
            Categoria.nome,
            func.count(CategoriaAcesso.categoria_id).label("quantidade"),
        )
        .select_from(CategoriaAcesso)
        .join(Categoria, Categoria.uuid == CategoriaAcesso.categoria_id)
        .filter(
            CategoriaAcesso.usuario_id == usuario_id,
            CategoriaAcesso.dia >= inicio_mes,
            CategoriaAcesso.dia <= fim_mes,
        )
        .group_by(Categoria.uuid, Categoria.nome)
        .order_by(func.count(CategoriaAcesso.categoria_id).desc(), Categoria.nome.asc())
        .all()
    )

    return {
        "indicadores": {
            "materias_total": int(materias_total),
        },
        "categorias_mes": [
            {"categoria": nome, "quantidade": int(quantidade)}
            for nome, quantidade in acessos_por_categoria
        ],
        "periodo": {"inicio": inicio_mes, "fim": fim_mes},
    }
