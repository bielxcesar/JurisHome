import os

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles

from database import engine
from feedback_database import criar_tabela_feedback
from model.models import Base, Usuario, Conteudo, Categoria, StatusConteudo
from auth.security import get_current_admin
from routes import paginas, admin, conteudos, glossario, feedbacks

Base.metadata.create_all(bind=engine)
criar_tabela_feedback()

app = FastAPI(title="JurisHome")

app.mount("/static", StaticFiles(directory="static"), name="static")

# TODO: enquanto o login com Google Authenticator (2FA) não está pronto,
# deixamos a proteção do admin desligada por padrão. Defina
# REQUIRE_ADMIN_AUTH=true no .env assim que o fluxo de login existir —
# NUNCA rode em produção com isso desligado.
exigir_auth_admin = os.getenv("REQUIRE_ADMIN_AUTH", "false").lower() == "true"
admin_dependencies = [Depends(get_current_admin)] if exigir_auth_admin else []

app.include_router(paginas.router)
app.include_router(admin.router, dependencies=admin_dependencies)
app.include_router(conteudos.router)
app.include_router(glossario.router)
app.include_router(feedbacks.public_router)
app.include_router(feedbacks.admin_router, dependencies=admin_dependencies)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
