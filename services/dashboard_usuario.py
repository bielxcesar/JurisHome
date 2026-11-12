from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from model.models import (
    Categoria,
    CategoriaAcesso,
    ConteudoLeitura,
    fuso_br,
)

DIAS_RETENCAO_CATEGORIA = 90


def inicio_periodo(data_final: date, periodo_dias: int) -> date:
    if periodo_dias not in (30, DIAS_RETENCAO_CATEGORIA):
        raise ValueError("O período da dashboard deve ser de 30 ou 90 dias.")
    return data_final - timedelta(days=periodo_dias - 1)


def registrar_acesso_categoria(
    db: Session,
    usuario_id: str,
    categoria_id: str,
    hoje: date | None = None,
) -> bool:
    """Registra no máximo um acesso por usuário, categoria e dia local."""
    data_atual = hoje or datetime.now(fuso_br).date()
    data_acesso = data_atual.isoformat()
    inicio_retencao = (data_atual - timedelta(days=DIAS_RETENCAO_CATEGORIA - 1)).isoformat()
    limpar_acessos_categoria_antigos(db, usuario_id, inicio_retencao)
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


def limpar_acessos_categoria_antigos(db: Session, usuario_id: str, inicio_inclusivo: str) -> None:
    removidos = (
        db.query(CategoriaAcesso)
        .filter(
            CategoriaAcesso.usuario_id == usuario_id,
            CategoriaAcesso.dia < inicio_inclusivo,
        )
        .delete(synchronize_session=False)
    )
    if removidos:
        db.commit()


def obter_dashboard_estudos(
    db: Session,
    usuario_id: str,
    hoje: date | None = None,
    periodo_dias: int = 30,
) -> dict:
    """Calcula as matérias consultadas e categorias acessadas pelo próprio usuário."""
    data_final = hoje or datetime.now(fuso_br).date()
    data_inicio = inicio_periodo(data_final, periodo_dias)
    inicio = data_inicio.isoformat()
    fim = data_final.isoformat()
    limpar_acessos_categoria_antigos(
        db,
        usuario_id,
        (data_final - timedelta(days=DIAS_RETENCAO_CATEGORIA - 1)).isoformat(),
    )

    materias_total = (
        db.query(func.count(func.distinct(ConteudoLeitura.conteudo_id)))
        .filter(
            ConteudoLeitura.usuario_id == usuario_id,
            ConteudoLeitura.dia >= inicio,
            ConteudoLeitura.dia <= fim,
        )
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
            CategoriaAcesso.dia >= inicio,
            CategoriaAcesso.dia <= fim,
        )
        .group_by(Categoria.uuid, Categoria.nome)
        .order_by(func.count(CategoriaAcesso.categoria_id).desc(), Categoria.nome.asc())
        .all()
    )

    return {
        "indicadores": {
            "materias_total": int(materias_total),
        },
        "categorias": [
            {"categoria": nome, "quantidade": int(quantidade)}
            for nome, quantidade in acessos_por_categoria
        ],
        "periodo": {
            "dias": periodo_dias,
            "rotulo": f"Últimos {periodo_dias} dias",
            "inicio": inicio,
            "fim": fim,
        },
    }
