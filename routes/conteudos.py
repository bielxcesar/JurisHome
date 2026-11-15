"""Rotas do acervo, da pesquisa e da leitura de matérias."""

import math
from datetime import datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.security import get_current_user, get_current_user_optional
from auth.sessions import garantir_transacao
from database import get_db
from model.models import Categoria, Conteudo, ConteudoLeitura, StatusConteudo, TipoUsuario, Usuario, fuso_br
from services.categorias import categoria_canonica, categoria_disponivel, categorias_disponiveis, combinar_tags
from services.conteudo_pedagogico import conteudo_categoria
from services.editorial import montar_editorial
from services.imagens import url_fonte_segura, url_imagem_segura
from services.validacao import TextoBusca, padrao_busca

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/api/conteudos/em-alta")
def conteudos_em_alta(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    inicio = (datetime.now(fuso_br).date() - timedelta(days=6)).isoformat()
    registros = db.query(Conteudo, func.count(ConteudoLeitura.usuario_id).label("leituras")).join(
        ConteudoLeitura, ConteudoLeitura.conteudo_id == Conteudo.uuid,
    ).filter(Conteudo.status == StatusConteudo.APROVADO, ConteudoLeitura.dia >= inicio,
        Conteudo.categoria_id.in_([c.uuid for c in categorias_disponiveis(db)])).group_by(
        Conteudo.uuid,
    ).order_by(func.count(ConteudoLeitura.usuario_id).desc(), Conteudo.criado_em.desc()).limit(4).all()
    return [{"uuid": c.uuid, "titulo": c.editorial.titulo_home if c.editorial and c.editorial.titulo_home else c.titulo, "categoria": c.categoria.nome if c.categoria else "Direito",
             "imagem_miniatura": c.imagem_miniatura, "leituras": total} for c, total in registros]


@router.get('/api/conteudos/interesse')
def materias_interesse(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    area = usuario.especialidade_juridica
    if not categoria_disponivel(area):
        return {'area': None, 'itens': []}
    area = categoria_canonica(area)
    categorias = [c.uuid for c in categorias_disponiveis(db) if categoria_canonica(c.nome) == area]
    registros = db.query(Conteudo).filter(
        Conteudo.status == StatusConteudo.APROVADO, Conteudo.categoria_id.in_(categorias)
    ).order_by(Conteudo.criado_em.desc()).limit(4).all()
    return {'area': area, 'itens': [{'uuid': c.uuid,
        'titulo': c.editorial.titulo_home if c.editorial and c.editorial.titulo_home else c.titulo,
        'categoria': c.categoria.nome, 'imagem_miniatura': url_imagem_segura(c.imagem_miniatura),
        'criado_em': c.criado_em.strftime('%d/%m/%Y') if c.criado_em else ''} for c in registros]}


@router.get("/api/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    return [{"uuid": c.uuid, "nome": c.nome} for c in categorias_disponiveis(db)]


@router.get("/api/conteudos")
def buscar_conteudos(
    busca: Annotated[TextoBusca | None, Query(max_length=80)] = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(Conteudo).filter(Conteudo.status == StatusConteudo.APROVADO, Conteudo.categoria_id.in_([c.uuid for c in categorias_disponiveis(db)]))
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
            "fonte_original": url_fonte_segura(c.fonte_original),
            "criado_em": c.criado_em.strftime("%d/%m/%Y") if c.criado_em else ""
        }
        for c in conteudos
    ]


@router.get("/pesquisa", response_class=HTMLResponse)
def pagina_pesquisa(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="pesquisa.html",
        context={"tipo_usuario": usuario.tipo_usuario.value},
    )


@router.get("/exibir-mais", response_class=HTMLResponse)
def pagina_exibir_mais(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="listagem_conteudos.html",
        context={"tipo_usuario": usuario.tipo_usuario.value, "visao": "recentes"},
    )


@router.get("/categorias", response_class=HTMLResponse)
def pagina_categorias(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request=request,
        name="listagem_conteudos.html",
        context={"tipo_usuario": usuario.tipo_usuario.value, "visao": "categorias",
                 "categorias_catalogo": [{"nome": c.nome, **conteudo_categoria(c.nome)}
                                         for c in categorias_disponiveis(db)]},
    )


@router.get("/materia/{conteudo_id}", response_class=HTMLResponse)
def pagina_materia(
    conteudo_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    conteudo = db.query(Conteudo).filter(Conteudo.uuid == conteudo_id).first()

    if not conteudo or (
        usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR
        and (not conteudo.categoria or not categoria_disponivel(conteudo.categoria.nome))
    ) or (
        conteudo.status != StatusConteudo.APROVADO
        and usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR
    ):
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")

    if usuario.tipo_usuario == TipoUsuario.ESTUDANTE:
        garantir_transacao(db)
        chave = {"usuario_id": usuario.uuid, "conteudo_id": conteudo.uuid,
                 "dia": datetime.now(fuso_br).date().isoformat()}
        try:
            with db.begin_nested():
                db.add(ConteudoLeitura(**chave))
                db.flush()
        except IntegrityError:
            pass  # Recarregar a matéria no mesmo dia não gera outra leitura.
        db.commit()

    tags_lista = combinar_tags(conteudo.categoria.nome if conteudo.categoria else "", conteudo.tags)
    paragrafos = [linha.strip() for linha in (conteudo.corpo_texto or "").splitlines() if linha.strip()]
    imagens = [url_imagem_segura(valor) for valor in (conteudo.imagem_corpo, conteudo.imagem_extra_2, conteudo.imagem_extra_3)]
    blocos = []
    for indice in range(max(len(paragrafos), len(imagens))):
        if indice < len(paragrafos):
            blocos.append({"tipo": "texto", "texto": paragrafos[indice]})
        if indice < len(imagens) and imagens[indice]:
            blocos.append({"tipo": "imagem", "url": imagens[indice], "alt": f"Imagem complementar {indice + 1} da matéria"})
    endereco = str(request.url)
    mensagem = quote(f"{conteudo.titulo}\n{endereco}", safe="")

    return templates.TemplateResponse(
        request=request,
        name="materia.html",
        context={
            "materia": conteudo,
            **montar_editorial(conteudo),
            "tags": tags_lista,
            "tipo_usuario": usuario.tipo_usuario.value,
            "blocos_materia": blocos,
            "capa_materia": url_imagem_segura(conteudo.imagem_miniatura),
            "fonte_materia": url_fonte_segura(conteudo.fonte_original),
            "tempo_leitura": max(1, math.ceil(len((conteudo.corpo_texto or "").split()) / 200)),
            "compartilhar_whatsapp": f"https://api.whatsapp.com/send?text={mensagem}",
            "compartilhar_email": f"mailto:?subject={quote(conteudo.titulo, safe='')}&body={mensagem}",
        }
    )


@router.get("/preview-materia", response_class=HTMLResponse)
def pagina_preview_materia(request: Request, usuario: Usuario | None = Depends(get_current_user_optional)):
    return templates.TemplateResponse(
        request=request,
        name="novaMateriaEX.html",
        context={"tipo_usuario": usuario.tipo_usuario.value if usuario else "usuario"},
    )
