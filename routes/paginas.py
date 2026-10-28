from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, File, Form

from database import get_db
from auth.security import get_current_user
from model.models import Conteudo, Usuario, TipoUsuario, StatusConteudo
from services.lgpd import POLITICA_PRIVACIDADE_VERSAO, TERMOS_VERSAO
from services.imagens import url_fonte_segura, url_imagem_segura
from services.categorias import combinar_tags
from urllib.parse import quote
import math

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/2fatores", response_class=HTMLResponse)
def pagina_2fatores(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="2fatores.html"
    )


@router.get("/renovar-sessao", response_class=HTMLResponse)
def pagina_renovar_sessao(request: Request, destino: str = "/home_usuario"):
    permitidos = {"/home_usuario", "/home_admin", "/perfil", "/pesquisa", "/categorias", "/exibir-mais", "/configuracoes-usuario", "/configuracao", "/admin-feedbacks", "/admin/auditoria", "/feedback"}
    if destino not in permitidos and not (destino.startswith("/materia/") and destino.removeprefix("/materia/").replace("-", "").isalnum()):
        destino = "/home_usuario"
    return templates.TemplateResponse(request=request, name="renovar_sessao.html", context={"destino": destino})


@router.get("/recuperar-senha", response_class=HTMLResponse)
def pagina_recuperar_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha.html")


@router.get("/recuperar-senha/confirmar", response_class=HTMLResponse)
def pagina_confirmar_recuperacao(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_codigo.html")


@router.get("/recuperar-senha/nova", response_class=HTMLResponse)
def pagina_nova_senha(request: Request):
    return templates.TemplateResponse(request=request, name="recuperar_senha_nova.html")


@router.get("/termos-de-aceite", response_class=HTMLResponse)
def pagina_termos_de_aceite(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="termos.html",
        context={"versao_termos": TERMOS_VERSAO},
    )


@router.get("/politica-de-privacidade", response_class=HTMLResponse)
def pagina_politica_de_privacidade(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="politica_privacidade.html",
        context={"versao_politica": POLITICA_PRIVACIDADE_VERSAO},
    )
from fastapi import Form

@router.post("/api/perfil/atualizar")
def atualizar_perfil(
    nome: str = Form(...),
    faculdade: str = Form(None),
    interesse: str = Form(None),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    nome = nome.strip()
    if not 3 <= len(nome) <= 100:
        raise HTTPException(status_code=422, detail="O nome deve ter entre 3 e 100 caracteres.")
    # Se tiver esses campos no model, descomente:
    # usuario.faculdade = faculdade
    # usuario.interesse = interesse

    if foto and foto.filename:
        limite = 2 * 1024 * 1024
        conteudo = foto.file.read(limite + 1)
        if len(conteudo) > limite:
            raise HTTPException(status_code=413, detail="A foto deve ter no máximo 2 MB.")
        try:
            with Image.open(BytesIO(conteudo)) as imagem:
                if imagem.format not in {"JPEG", "PNG", "WEBP"} or imagem.width * imagem.height > 16_000_000:
                    raise ValueError("Formato ou dimensões inválidos")
                imagem.load()
                imagem = imagem.convert("RGB")
                imagem.thumbnail((1024, 1024))
                pasta = Path("static/uploads")
                pasta.mkdir(parents=True, exist_ok=True)
                nome_arquivo = f"{uuid.uuid4().hex}.jpg"
                imagem.save(pasta / nome_arquivo, format="JPEG", quality=85)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as erro:
            raise HTTPException(status_code=422, detail="Envie uma imagem JPEG, PNG ou WebP válida.") from erro
        usuario.foto_perfil = f"/static/uploads/{nome_arquivo}"

    usuario.nome = nome
    db.commit()
    db.refresh(usuario)
    return {"status": "sucesso", "mensagem": "Perfil atualizado com sucesso!"}

@router.get("/configuracoes-usuario", response_class=HTMLResponse)
@router.get("/templates/confUsuario.html", response_class=HTMLResponse) 
def pagina_configuracoes_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="confUsuario.html", 
        context={
            "titulo_configuracao": "Troca de senha",
            "destino_voltar": "/home_usuario",
            "destino_feedback": "/configuracoes-usuario#feedback",
            "rotulo_feedback": "Feedback e suporte",
            "rotulo_sair": "Sair",
            "feedback_interno": True,
            "mostrar_auditoria": False,
            "mostrar_exclusao_dados": True,
        },
    )


@router.get("/feedback", response_class=HTMLResponse)
def pagina_feedback(request: Request, usuario: Usuario = Depends(get_current_user)):
    return templates.TemplateResponse(request=request, name="feedback-suporte.html")


@router.get("/home_usuario", response_class=HTMLResponse)
@router.get("/home_Usuario.html", response_class=HTMLResponse)
@router.get("/templates/home_Usuario.html", response_class=HTMLResponse)
async def get_home_usuario(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request, 
        name="home_Usuario.html"
    )

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
            "tipo_usuario": usuario.tipo_usuario.value if hasattr(usuario, "tipo_usuario") and hasattr(usuario.tipo_usuario, "value") else "usuario",
        },
    )

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
):
    return templates.TemplateResponse(
        request=request,
        name="listagem_conteudos.html",
        context={"tipo_usuario": usuario.tipo_usuario.value, "visao": "categorias"},
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
        conteudo.status != StatusConteudo.APROVADO
        and usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR
    ):
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    
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


@router.get("/cadastro", response_class=HTMLResponse)
def pagina_cadastro(request: Request):
    return templates.TemplateResponse(request=request, name="cadastro.html")

@router.get("/preview-materia", response_class=HTMLResponse)
def pagina_preview_materia(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="novaMateriaEX.html"
    )
