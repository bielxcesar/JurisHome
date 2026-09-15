import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (essencial para o PostgreSQL local)
load_dotenv()

# Conexão com o banco (Busca no .env, se não achar, usa SQLite como plano B)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./juris_home.db")

# Correção necessária para o prefixo do PostgreSQL gerado pelo Railway
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Argumentos específicos: SQLite exige isso para multithread; PostgreSQL não precisa
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

# Criação do motor do banco de dados
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

# Configuração da sessão
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para a criação dos modelos
Base = declarative_base()

# Função geradora de sessão para injeção de dependência no FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()