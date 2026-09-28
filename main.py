import os

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import engine
from feedback_database import criar_tabela_feedback
from model.models import Base, Usuario, Conteudo, Categoria, StatusConteudo
from auth.security import get_current_admin
from routes import auth, paginas, admin, auditoria, conteudos, glossario, feedbacks
from services.auditoria import iniciar_contexto_auditoria, finalizar_contexto_auditoria

Base.metadata.create_all(bind=engine)
criar_tabela_feedback()

app = FastAPI(title="JurisHome")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/images/logo.png")


@app.middleware("http")
async def adicionar_correlacao_auditoria(request: Request, call_next):
    tokens, correlacao_id = iniciar_contexto_auditoria()
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlacao_id
        return response
    finally:
        finalizar_contexto_auditoria(tokens)


@app.middleware("http")
async def adicionar_cabecalhos_seguranca(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), geolocation=(), microphone=()",
    )

    if request.url.path.startswith(("/api/auth/", "/api/usuarios/me")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(HTTPException)
async def tratar_erro_http(request: Request, erro: HTTPException):
    paginas_protegidas = {
        "/home_usuario", "/home_Usuario.html", "/templates/home_Usuario.html",
        "/configuracoes-usuario", "/templates/confUsuario.html",
        "/home_admin", "/configuracao", "/admin-feedbacks", "/admin/auditoria",
        "/exibir-mais", "/categorias",
    }
    if erro.status_code == 401 and (
        request.url.path in paginas_protegidas or request.url.path.startswith("/materia/")
    ):
        resposta = RedirectResponse(url="/?sessao=expirada", status_code=303)
        resposta.delete_cookie(key="jurishome_access_token", path="/")
        return resposta
    return await http_exception_handler(request, erro)

app.mount("/static", StaticFiles(directory="static"), name="static")

# A autorização administrativa permanece ligada por padrão. Só desative
# explicitamente em uma demonstração local, nunca em produção.
exigir_auth_admin = os.getenv("REQUIRE_ADMIN_AUTH", "true").lower() == "true"
admin_dependencies = [Depends(get_current_admin)] if exigir_auth_admin else []

app.include_router(paginas.router)
app.include_router(auth.router)
app.include_router(admin.router, dependencies=admin_dependencies)
app.include_router(auditoria.admin_router, dependencies=admin_dependencies)
app.include_router(conteudos.router)
app.include_router(glossario.router)
app.include_router(feedbacks.public_router)
app.include_router(feedbacks.admin_router, dependencies=admin_dependencies)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
