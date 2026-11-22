"""Tela de perfil e operações de acompanhamento do leitor."""

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from auth.security import get_current_user
from database import get_db
from model.models import Categoria, TipoUsuario, Usuario, obter_hora_local
from services.categorias import CATALOGO
from services.dashboard_usuario import obter_dashboard_estudos, registrar_acesso_categoria
from services.lgpd import data_aceite_local, revisao_vigente, versao_legal
from services.validacao import ModeloSeguro, area_interesse, linha, nome_pessoa
from services.avatares import AVATARES_PERFIL, AVATAR_POR_ID, AVATAR_POR_URL

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
    db: Session = Depends(get_db),
):
    revisao = revisao_vigente(db)
    versao_atual = versao_legal(revisao)
    return templates.TemplateResponse(
        request=request,
        name="perfil.html",
        context={
            "usuario": usuario,
            "avatares": AVATARES_PERFIL,
            "avatar_atual_id": (AVATAR_POR_URL.get(usuario.foto_perfil) or AVATARES_PERFIL[0])["id"],
            "foto_perfil_url": (AVATAR_POR_URL.get(usuario.foto_perfil) or AVATARES_PERFIL[0])["url"],
            "data_aceite": data_aceite_local(usuario.data_consentimento),
            "dois_fatores_ativos": bool(usuario.is_2fa_enabled and usuario.totp_secret),
            "versao_legal_atual": versao_atual,
            "aceite_atual": bool(usuario.consentimento_lgpd and usuario.versao_termos == versao_atual),
            "categorias_perfil": list(CATALOGO),
            "tipo_usuario": usuario.tipo_usuario.value if hasattr(usuario, "tipo_usuario") and hasattr(usuario.tipo_usuario, "value") else "usuario",
            "mostrar_dashboard": usuario.tipo_usuario == TipoUsuario.ESTUDANTE,
        },
    )


async def validar_campos_perfil(request: Request):
    formulario = await request.form()
    pares = list(formulario.multi_items())
    permitidos = {"nome", "faculdade", "interesse", "avatar_id", "versao"}
    if any(chave not in permitidos for chave, _ in pares) or len({chave for chave, _ in pares}) != len(pares):
        raise HTTPException(422, "Envie apenas os campos previstos do perfil, sem repetições.")


@router.post("/api/perfil/atualizar", dependencies=[Depends(validar_campos_perfil)])
def atualizar_perfil(
    nome: str = Form(...),
    faculdade: str | None = Form(None),
    interesse: str | None = Form(None),
    avatar_id: str | None = Form(None),
    versao: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not usuario.atualizado_em or versao != usuario.atualizado_em.isoformat():
        raise HTTPException(409, "Seu perfil foi alterado em outra sessão. Recarregue a página antes de salvar.")
    try:
        nome = nome_pessoa(nome)
        if faculdade is not None:
            faculdade = linha(faculdade, 150)
        if interesse:
            interesse = area_interesse(interesse)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from None

    avatar = None
    if avatar_id:
        avatar = AVATAR_POR_ID.get(avatar_id)
        if avatar is None:
            raise HTTPException(422, "Escolha um avatar disponível na galeria.")

    valores = {"nome": nome, "atualizado_em": obter_hora_local()}
    if faculdade is not None:
        valores["universidade"] = faculdade.strip() or None
    if interesse is not None:
        valores["especialidade_juridica"] = interesse.strip() or None
    if avatar:
        valores["foto_perfil"] = avatar["url"]

    atualizadas = db.query(Usuario).filter(
        Usuario.uuid == usuario.uuid,
        Usuario.atualizado_em == usuario.atualizado_em,
    ).update(valores, synchronize_session=False)
    if atualizadas != 1:
        db.rollback()
        raise HTTPException(409, "Seu perfil foi alterado em outra sessão. Recarregue a página antes de salvar.")
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
