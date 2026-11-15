"""Publicação e aceite de versões dos documentos legais."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.security import get_current_user_sem_aceite
from database import get_db
from model.models import RevisaoLegal, TipoUsuario, Usuario
from services.administradores import exigir_root
from services.auditoria import registrar_auditoria
from services.lgpd import DOCUMENTOS, LIMITE_DOCUMENTO, revisao_vigente, texto_inicial, versao_legal
from services.validacao import texto_simples

router = APIRouter()
templates = Jinja2Templates(directory="templates")
SEM_CACHE = {"Cache-Control": "no-store"}
TipoDocumento = Literal["termos", "privacidade"]


def _painel(usuario: Usuario) -> str:
    return "/home_admin" if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR else "/home_usuario"


def _documento_publico(request: Request, tipo: TipoDocumento, db: Session):
    _, arquivo, campo = DOCUMENTOS[tipo]
    revisao = revisao_vigente(db)
    return templates.TemplateResponse(
        request=request,
        name=arquivo,
        context={
            "versao_termos": versao_legal(revisao),
            "versao_politica": versao_legal(revisao),
            "texto_publicado": getattr(revisao, campo, None),
            "publicada_em": revisao.publicada_em.strftime("%d/%m/%Y") if revisao else None,
        },
        headers=SEM_CACHE,
    )


@router.get("/termos-de-aceite", response_class=HTMLResponse)
def pagina_termos_de_aceite(request: Request, db: Session = Depends(get_db)):
    return _documento_publico(request, "termos", db)


@router.get("/politica-de-privacidade", response_class=HTMLResponse)
def pagina_politica_de_privacidade(request: Request, db: Session = Depends(get_db)):
    return _documento_publico(request, "privacidade", db)


@router.get("/perfil/documentos-legais", response_class=HTMLResponse)
def editor(
    request: Request,
    tipo: TipoDocumento = "termos",
    db: Session = Depends(get_db),
    root: Usuario = Depends(exigir_root),
):
    revisao = revisao_vigente(db)
    return _render_editor(request, tipo, revisao)


def _render_editor(request, tipo, revisao, *, erro=None, rascunho=None, status_code=200):
    titulo, _, campo = DOCUMENTOS[tipo]
    texto = getattr(revisao, campo, None)
    return templates.TemplateResponse(
        request=request,
        name="documentos_legais_editor.html",
        context={
            "titulo": titulo,
            "tipo": tipo,
            "texto": rascunho if rascunho is not None else texto or texto_inicial(tipo),
            "versao": versao_legal(revisao),
            "limite": LIMITE_DOCUMENTO,
            "erro": erro,
            "pode_publicar": status_code != 409,
        },
        headers=SEM_CACHE,
        status_code=status_code,
    )


@router.post("/perfil/documentos-legais/{tipo}")
def publicar(
    request: Request,
    tipo: TipoDocumento,
    versao: Annotated[str, Form(max_length=50)],
    texto: Annotated[str, Form(min_length=1, max_length=LIMITE_DOCUMENTO)],
    confirmar: Annotated[Literal["sim"], Form()],
    db: Session = Depends(get_db),
    root: Usuario = Depends(exigir_root),
):
    revisao = revisao_vigente(db)
    atual = versao_legal(revisao)
    mensagem_conflito = "Outra versão foi publicada. Abra o editor atualizado e compare com seu rascunho antes de publicar."
    if versao != atual:
        return _render_editor(request, tipo, revisao, erro=mensagem_conflito, rascunho=texto, status_code=409)
    try:
        texto = texto_simples(texto.replace("\r\n", "\n").replace("\r", "\n"))
        if not texto:
            raise ValueError("Preencha o conteúdo antes de publicar.")
    except ValueError as erro:
        return _render_editor(request, tipo, revisao, erro=str(erro), rascunho=texto, status_code=422)

    _, _, campo = DOCUMENTOS[tipo]
    if texto == (getattr(revisao, campo, None) or texto_inicial(tipo)):
        return _render_editor(request, tipo, revisao, erro="Faça uma alteração antes de publicar.")
    nova = RevisaoLegal(
        anterior=atual,
        termos=getattr(revisao, "termos", None),
        politica=getattr(revisao, "politica", None),
        publicada_em=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    setattr(nova, campo, texto)
    try:
        db.add(nova)
        db.flush()
        registrar_auditoria(
            db, acao="documentos_legais_publicados", recurso_tipo="revisao_legal",
            recurso_id=versao_legal(nova), resultado="sucesso", usuario=root,
            detalhes={"tipo": tipo, "versao_anterior": atual},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return _render_editor(
            request, tipo, revisao_vigente(db), erro=mensagem_conflito,
            rascunho=texto, status_code=409,
        )
    return RedirectResponse("/aceitar-documentos", status_code=303, headers=SEM_CACHE)


def _render_aceite(request, revisao, *, erro=None, status_code=200):
    return templates.TemplateResponse(
        request=request,
        name="documentos_legais_aceite.html",
        context={"versao": versao_legal(revisao), "erro": erro},
        headers=SEM_CACHE,
        status_code=status_code,
    )


@router.get("/aceitar-documentos", response_class=HTMLResponse)
def pagina_aceite(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user_sem_aceite),
):
    revisao = revisao_vigente(db)
    if not revisao or (usuario.consentimento_lgpd and usuario.versao_termos == versao_legal(revisao)):
        return RedirectResponse(_painel(usuario), status_code=303, headers=SEM_CACHE)
    return _render_aceite(request, revisao)


@router.post("/aceitar-documentos")
def aceitar(
    request: Request,
    versao: Annotated[str, Form(max_length=50)],
    aceite: Annotated[Literal["sim"], Form()],
    ciencia: Annotated[Literal["sim"], Form()],
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user_sem_aceite),
):
    revisao = revisao_vigente(db)
    if not revisao or versao != versao_legal(revisao):
        return _render_aceite(request, revisao, erro="Os documentos mudaram. Leia a nova versão antes de confirmar.", status_code=409)

    # Serializa confirmações simultâneas da mesma conta no PostgreSQL.
    usuario = db.query(Usuario).filter_by(uuid=usuario.uuid).populate_existing().with_for_update().one()
    revisao = revisao_vigente(db)
    if versao != versao_legal(revisao):
        return _render_aceite(request, revisao, erro="Os documentos mudaram. Leia a nova versão antes de confirmar.", status_code=409)
    if not usuario.consentimento_lgpd or usuario.versao_termos != versao:
        usuario.consentimento_lgpd = True
        usuario.versao_termos = versao
        usuario.data_consentimento = datetime.now(timezone.utc).replace(tzinfo=None)
        registrar_auditoria(
            db, acao="documentos_legais_aceitos", recurso_tipo="revisao_legal",
            recurso_id=versao, resultado="sucesso", usuario=usuario,
        )
        db.commit()
    return RedirectResponse(_painel(usuario), status_code=303, headers=SEM_CACHE)
