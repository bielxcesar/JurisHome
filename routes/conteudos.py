from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from typing import Annotated
from sqlalchemy.orm import Session
from database import get_db
from model.models import Categoria, Conteudo, StatusConteudo

router = APIRouter()


@router.get("/api/conteudos")
def buscar_conteudos(
    busca: Annotated[str | None, Query(max_length=120)] = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(Conteudo).filter(Conteudo.status == StatusConteudo.APROVADO)
    termo = (busca or "").strip()
    if termo:
        padrao = f"%{termo}%"
        consulta = consulta.filter(
            or_(
                Conteudo.titulo.ilike(padrao),
                Conteudo.sub_titulo.ilike(padrao),
                Conteudo.resumo_home.ilike(padrao),
                Conteudo.corpo_texto.ilike(padrao),
                Conteudo.categoria.has(Categoria.nome.ilike(padrao)),
            )
        )
    conteudos = consulta.order_by(Conteudo.criado_em.desc()).all()
    
    return [
        {
            "uuid": c.uuid,
            "titulo": c.titulo,
            "sub_titulo": c.sub_titulo,
            "resumo_home": c.resumo_home,
            "categoria": c.categoria.nome if c.categoria else "Direito",
            "imagem_miniatura": c.imagem_miniatura,
            "criado_em": c.criado_em.strftime("%d/%m/%Y") if c.criado_em else ""
        }
        for c in conteudos
    ]
