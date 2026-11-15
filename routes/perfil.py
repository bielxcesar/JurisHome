"""Tela de perfil e operações de acompanhamento do leitor."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from auth.security import get_current_user
from database import get_db
from model.models import Categoria, TipoUsuario, Usuario
from services.categorias import CATALOGO
from services.dashboard_usuario import obter_dashboard_estudos, registrar_acesso_categoria
from services.imagens import normalizar_imagem_bytes
from services.validacao import ModeloSeguro, area_interesse, linha, nome_pessoa

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class RegistroAcessoCategoria(ModeloSeguro):
    categoria: str = Field(min_length=1, max_length=100)

    @field_validator("categoria")
    @classmethod
    def limpar_categoria(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Selecione uma categoria válida.")
        return valor


@router.get("/perfil", response_class=HTMLResponse)
def pagina_perfil(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="perfil.html",
        context={
            "usuario": usuario,
            "categorias_perfil": list(CATALOGO),
            "tipo_usuario": usuario.tipo_usuario.value if hasattr(usuario, "tipo_usuario") and hasattr(usuario.tipo_usuario, "value") else "usuario",
            "mostrar_dashboard": usuario.tipo_usuario == TipoUsuario.ESTUDANTE,
        },
    )


async def validar_campos_perfil(request: Request):
    formulario = await request.form()
    pares = list(formulario.multi_items())
    if any(chave not in {'nome','faculdade','interesse','foto'} for chave, _ in pares) or len({chave for chave, _ in pares}) != len(pares):
        raise HTTPException(422, 'Envie apenas os campos previstos do perfil, sem repetições.')


@router.post("/api/perfil/atualizar", dependencies=[Depends(validar_campos_perfil)])
def atualizar_perfil(
    nome: str = Form(...),
    faculdade: str = Form(None),
    interesse: str = Form(None),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    try:
        nome = nome_pessoa(nome)
        if faculdade is not None:
            faculdade = linha(faculdade, 150)
        if interesse:
            interesse = area_interesse(interesse)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from None

    if foto and foto.filename:
        limite = 2 * 1024 * 1024
        conteudo = foto.file.read(limite + 1)
        if len(conteudo) > limite:
            raise HTTPException(status_code=413, detail="A foto deve ter no máximo 2 MB.")
        try:
            jpeg = normalizar_imagem_bytes(conteudo, limite=limite, tamanho=1024, qualidade=85)
        except ValueError as erro:
            raise HTTPException(status_code=422, detail=str(erro)) from erro
        pasta = Path("static/uploads")
        pasta.mkdir(parents=True, exist_ok=True)
        nome_arquivo = f"{uuid.uuid4().hex}.jpg"
        (pasta / nome_arquivo).write_bytes(jpeg)
        usuario.foto_perfil = f"/static/uploads/{nome_arquivo}"

    usuario.nome = nome
    if faculdade is not None:
        usuario.universidade = faculdade.strip() or None
    if interesse is not None:
        usuario.especialidade_juridica = interesse.strip() or None
    db.commit()
    db.refresh(usuario)
    return {"status": "sucesso", "mensagem": "Perfil atualizado com sucesso!"}


@router.get("/api/perfil/dashboard")
def api_dashboard_perfil(
    response: Response,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
    periodo: int = Query(default=30, ge=30, le=90),
):
    if usuario.tipo_usuario != TipoUsuario.ESTUDANTE:
        raise HTTPException(status_code=404, detail="Página não encontrada.")
    if periodo not in (30, 90):
        raise HTTPException(status_code=422, detail="Selecione um período de 30 ou 90 dias.")

    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return obter_dashboard_estudos(db, str(usuario.uuid), periodo_dias=periodo)


@router.post("/api/perfil/categoria-acesso")
def api_registrar_acesso_categoria(
    dados: RegistroAcessoCategoria,
    response: Response,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if usuario.tipo_usuario != TipoUsuario.ESTUDANTE:
        raise HTTPException(status_code=404, detail="Página não encontrada.")

    categoria = db.query(Categoria).filter(Categoria.nome == dados.categoria).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    registrado = registrar_acesso_categoria(db, str(usuario.uuid), str(categoria.uuid))
    return {"registrado": registrado}
