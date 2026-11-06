from services.validacao import TextoBusca, padrao_busca
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, func
from datetime import datetime, timedelta
from model.models import fuso_br
from auth.security import get_current_user
from typing import Annotated
from sqlalchemy.orm import Session
from database import get_db
from model.models import Categoria, Conteudo, StatusConteudo, ConteudoLeitura, Usuario
from services.imagens import url_fonte_segura, url_imagem_segura

router = APIRouter()

ROTULOS_TIPO_FONTE = {
    "acordao": "Acórdão",
    "doutrina": "Doutrina",
    "legislacao": "Legislação",
    "g1": "G1",
    "terra": "Terra",
    "uol": "UOL",
    "x": "X",
    "instagram": "Instagram",
}


@router.get("/api/conteudos/em-alta")
def conteudos_em_alta(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    inicio = (datetime.now(fuso_br).date() - timedelta(days=6)).isoformat()
    registros = db.query(Conteudo, func.count(ConteudoLeitura.usuario_id).label("leituras")).join(
        ConteudoLeitura, ConteudoLeitura.conteudo_id == Conteudo.uuid,
    ).filter(Conteudo.status == StatusConteudo.APROVADO, ConteudoLeitura.dia >= inicio).group_by(
        Conteudo.uuid,
    ).order_by(func.count(ConteudoLeitura.usuario_id).desc(), Conteudo.criado_em.desc()).limit(4).all()
    return [{"uuid": c.uuid, "titulo": c.editorial.titulo_home if c.editorial and c.editorial.titulo_home else c.titulo, "categoria": c.categoria.nome if c.categoria else "Direito",
             "imagem_miniatura": c.imagem_miniatura, "leituras": total} for c, total in registros]


@router.get('/api/conteudos/interesse')
def materias_interesse(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    area = usuario.especialidade_juridica
    if not area:
        return {'area': None, 'itens': []}
    registros = db.query(Conteudo).join(Categoria).filter(
        Conteudo.status == StatusConteudo.APROVADO, Categoria.nome == area
    ).order_by(Conteudo.criado_em.desc()).limit(4).all()
    return {'area': area, 'itens': [{'uuid': c.uuid,
        'titulo': c.editorial.titulo_home if c.editorial and c.editorial.titulo_home else c.titulo,
        'categoria': c.categoria.nome, 'imagem_miniatura': url_imagem_segura(c.imagem_miniatura),
        'criado_em': c.criado_em.strftime('%d/%m/%Y') if c.criado_em else ''} for c in registros]}


@router.get("/api/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    return [{"uuid": c.uuid, "nome": c.nome} for c in db.query(Categoria).order_by(Categoria.nome).all()]


@router.get("/api/conteudos")
def buscar_conteudos(
    busca: Annotated[TextoBusca | None, Query(max_length=80)] = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(Conteudo).filter(Conteudo.status == StatusConteudo.APROVADO)
    termo = (busca or "").strip()
    if termo:
        padrao = padrao_busca(termo)
        consulta = consulta.filter(
            or_(
                Conteudo.titulo.ilike(padrao, escape="\\"),
                Conteudo.sub_titulo.ilike(padrao, escape="\\"),
                Conteudo.resumo_home.ilike(padrao, escape="\\"),
                Conteudo.corpo_texto.ilike(padrao, escape="\\"),
                Conteudo.categoria.has(Categoria.nome.ilike(padrao, escape="\\")),
            )
        )
    conteudos = consulta.order_by(Conteudo.criado_em.desc()).all()
    
    return [
        {
            "uuid": c.uuid,
            "titulo": c.editorial.titulo_home if c.editorial and c.editorial.titulo_home else c.titulo,
            "sub_titulo": c.sub_titulo,
            "resumo_home": c.resumo_home,
            "categoria": c.categoria.nome if c.categoria else "Direito",
            "imagem_miniatura": url_imagem_segura(c.imagem_miniatura),
            "fonte": ROTULOS_TIPO_FONTE.get(c.tipo_fonte.value, "Fonte não identificada"),
            "fonte_original": url_fonte_segura(c.fonte_original),
            "criado_em": c.criado_em.strftime("%d/%m/%Y") if c.criado_em else ""
        }
        for c in conteudos
    ]
