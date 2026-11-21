import os
import logging

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exception_handlers import http_exception_handler
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from urllib.parse import urlsplit
from urllib.parse import quote
from fastapi.staticfiles import StaticFiles

from database import engine, SessionLocal
from services.categorias import garantir_categorias, corrigir_vinculos_legados
from services.root_unico import garantir_root_unico
from services.leituras import ciclo_retencao_metricas
from services.lgpd import publicar_atualizacao_privacidade
from services.administradores import exigir_root
from services.entrada_http import EntradaSeguraMiddleware
from services.erros import eh_pagina, resposta_erro
from feedback_database import criar_tabela_feedback
from model.models import Base, Usuario, Conteudo, Categoria, StatusConteudo
from auth.security import get_current_admin
from routes import admin, auditoria, auth, conteudos, feedbacks, glossario, juridle, legal, perfil, rotas
from services.auditoria import iniciar_contexto_auditoria, finalizar_contexto_auditoria

Base.metadata.create_all(bind=engine)
from services.glossario import instalar_catalogo_inicial
instalar_catalogo_inicial(engine)
if engine.dialect.name in {"sqlite", "postgresql"}:
    with engine.begin() as conexao:
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_conteudos_categoria_status_criado_em "
            "ON conteudos (categoria_id, status, criado_em)"
        )
garantir_root_unico(engine)
with SessionLocal() as db_catalogo:
    publicar_atualizacao_privacidade(db_catalogo)
    garantir_categorias(db_catalogo)
    corrigir_vinculos_legados(db_catalogo)
    from services.juridle import garantir_banco_inicial
    garantir_banco_inicial(db_catalogo)
    from services.tentativas_auth import limpar_antigos
    limpar_antigos(db_catalogo)
criar_tabela_feedback()

app = FastAPI(title="JurisHome", docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo_retencao_metricas)
app.add_middleware(EntradaSeguraMiddleware)

CAMINHOS_DOCUMENTACAO = {"/docs", "/openapi.json"}


@app.get("/docs", include_in_schema=False, dependencies=[Depends(exigir_root)])
def documentacao_swagger(request: Request):
    prefixo = request.scope.get("root_path", "").rstrip("/")
    return get_swagger_ui_html(openapi_url=f"{prefixo}/openapi.json", title="JurisHome API")


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(exigir_root)])
def esquema_openapi():
    return JSONResponse(app.openapi())


@app.middleware("http")
async def validar_origem_requisicao(request: Request, call_next):
    """Bloqueia operações de escrita iniciadas por outras origens."""
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origem = request.headers.get("origin") or request.headers.get("referer")
        esperada = urlsplit(os.getenv("PUBLIC_ORIGIN") or str(request.base_url))
        recebida = urlsplit(origem) if origem else None
        if (
            request.headers.get("sec-fetch-site") == "cross-site"
            or (recebida and (recebida.scheme, recebida.netloc) != (esperada.scheme, esperada.netloc))
            or ((request.cookies.get("jurishome_access_token") or request.cookies.get("jurishome_refresh_token")) and not origem
                and request.headers.get("sec-fetch-site") != "same-origin")
        ):
            return JSONResponse(status_code=403, content={"detail": "Origem da requisição não permitida."})
    return await call_next(request)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/images/logo.png")


@app.middleware("http")
async def adicionar_correlacao_auditoria(request: Request, call_next):
    tokens, correlacao_id = iniciar_contexto_auditoria()
    request.state.correlacao_id = correlacao_id
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlacao_id
        return response
    finally:
        finalizar_contexto_auditoria(tokens)


def adicionar_hsts(request: Request, resposta) -> None:
    origem_publica = urlsplit(os.getenv("PUBLIC_ORIGIN") or "")
    # O Railway termina o TLS no proxy. O esquema visto pelo Uvicorn pode ser HTTP.
    if origem_publica.scheme == "https" and origem_publica.netloc.lower() == request.url.netloc.lower():
        resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")


@app.middleware("http")
async def adicionar_cabecalhos_seguranca(request: Request, call_next):
    response = await call_next(request)
    adicionar_hsts(request, response)
    if request.url.path in CAMINHOS_DOCUMENTACAO:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), geolocation=(), microphone=()",
    )

    if request.url.path.startswith(("/api/auth/", "/api/usuarios/me", "/api/admin/", "/api/juridle/", "/api/perfil/", "/api/feedbacks", "/api/conteudos/em-alta", "/api/conteudos/interesse", "/admin/auditoria", "/admin/tabela-noticias", "/admin/administradores/")) or request.url.path in {"/home_admin", "/home_usuario", "/home_Usuario.html", "/templates/home_Usuario.html", "/perfil", "/juridle", "/juridle/ampliar", "/conhecimento", "/curiosidades", "/configuracoes-usuario", "/templates/confUsuario.html", "/configuracao", "/admin-feedbacks", "/feedback"} or request.url.path in {"/glossario", "/consulta-lei", "/preview-materia"} or request.url.path.startswith("/materia/") or (request.cookies.get('jurishome_access_token') and response.headers.get('content-type', '').startswith('text/html')):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(StarletteHTTPException)
async def tratar_erro_http(request: Request, erro: StarletteHTTPException):
    if request.url.path in CAMINHOS_DOCUMENTACAO and erro.status_code in {401, 403}:
        return resposta_erro(request, 404)

    if erro.status_code == 428 and request.method == "GET" and eh_pagina(request):
        return RedirectResponse("/aceitar-documentos", status_code=303, headers={"Cache-Control": "no-store"})

    paginas_protegidas = {
        "/home_usuario", "/home_Usuario.html", "/templates/home_Usuario.html",
        "/configuracoes-usuario", "/templates/confUsuario.html",
        "/home_admin", "/configuracao", "/admin-feedbacks", "/admin/auditoria",
        "/exibir-mais", "/categorias",
        "/perfil", "/pesquisa", "/feedback", "/juridle", "/juridle/ampliar", "/curiosidades", "/conhecimento", "/admin/tabela-noticias",
    }
    if erro.status_code == 401 and (erro.headers or {}).get("X-Session-Reason") == "novo_acesso" and eh_pagina(request):
        resposta = RedirectResponse("/?sessao=substituida", status_code=303, headers={"Cache-Control": "no-store"})
        resposta.delete_cookie("jurishome_access_token", path="/")
        resposta.delete_cookie("jurishome_refresh_token", path="/")
        return resposta
    if erro.status_code == 401 and (
        request.url.path in paginas_protegidas or request.url.path.startswith(("/materia/", "/admin/administradores/"))
    ):
        if request.cookies.get("jurishome_refresh_token"):
            return RedirectResponse(url="/renovar-sessao?destino=" + quote(request.url.path, safe=""), status_code=303)
        resposta = resposta_erro(request, 404)
        resposta.delete_cookie(key="jurishome_access_token", path="/")
        return resposta
    if erro.status_code == 403 and not request.url.path.startswith("/api/"):
        return resposta_erro(request, 404)
    if erro.status_code >= 500:
        return resposta_erro(request, erro.status_code)
    if eh_pagina(request):
        codigo = 404 if erro.status_code == 403 else erro.status_code
        resposta = resposta_erro(request, codigo)
        if erro.headers:
            for nome in ("Allow", "Retry-After"):
                if nome in erro.headers:
                    resposta.headers[nome] = erro.headers[nome]
        return resposta
    return await http_exception_handler(request, erro)


@app.exception_handler(RequestValidationError)
async def tratar_dados_invalidos(request: Request, erro: RequestValidationError):
    if eh_pagina(request):
        return resposta_erro(request, 422)
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': list(e['loc']), 'msg': str(e['msg']), 'type': e['type']}
        for e in erro.errors()
    ]}, headers={'Cache-Control':'no-store'})


@app.exception_handler(Exception)
async def tratar_erro_inesperado(request: Request, erro: Exception):
    resposta = resposta_erro(request, 500)
    adicionar_hsts(request, resposta)
    logging.getLogger("jurishome.erros").error("Falha interna. Tipo=%s Referencia=%s", type(erro).__name__, resposta.headers["X-Correlation-ID"])
    return resposta


@app.get("/erro/{codigo}", include_in_schema=False)
def visualizar_erro(request: Request, codigo: int):
    if not 400 <= codigo <= 599:
        raise HTTPException(404, "Página não encontrada.")
    return resposta_erro(request, codigo)

app.mount("/static", StaticFiles(directory="static"), name="static")

admin_dependencies = [Depends(get_current_admin)]

app.include_router(rotas.router)
app.include_router(perfil.router)
app.include_router(legal.router)
app.include_router(auth.router)
app.include_router(admin.router, dependencies=admin_dependencies)
app.include_router(auditoria.admin_router, dependencies=admin_dependencies)
app.include_router(conteudos.router)
app.include_router(glossario.router)
app.include_router(feedbacks.public_router)
app.include_router(feedbacks.admin_router, dependencies=admin_dependencies)
app.include_router(juridle.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
