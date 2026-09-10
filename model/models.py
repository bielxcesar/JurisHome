import enum
import uuid as uuid_lib
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean,
    CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TipoUsuario(str, enum.Enum):
    ESTUDANTE = "estudante"
    ADMINISTRADOR = "administrador"


class TipoFonte(str, enum.Enum):
    ACORDAO = "acordao"
    DOUTRINA = "doutrina"
    LEGISLACAO = "legislacao"


class StatusConteudo(str, enum.Enum):
    EM_ANALISE = "em_analise"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


def gerar_uuid() -> str:
    return str(uuid_lib.uuid4())


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(36), unique=True, index=True, nullable=False, default=gerar_uuid)

    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=True)
    google_id = Column(String(255), unique=True, index=True, nullable=True)

    tipo_usuario = Column(
        Enum(TipoUsuario, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TipoUsuario.ESTUDANTE,
        index=True,
    )
    # Só é relevante quando tipo_usuario == ADMINISTRADOR.
    # Esse é o único admin que não pode ser removido nem rebaixado — é a
    # conta semeada manualmente pelo dev, e a partir dela outros usuários
    # são promovidos a admin. A checagem de "não pode deletar/rebaixar"
    # fica na camada de rotas/CRUD, não dá pra garantir só com o schema.
    e_root_admin = Column(Boolean, default=False, nullable=False)

    # Campos específicos de aluno — ficam nulos para admins.
    universidade = Column(String(255), nullable=True)
    especialidade_juridica = Column(String(100), nullable=True)

    totp_secret = Column(String(255), nullable=True)
    is_2fa_enabled = Column(Boolean, default=False, nullable=False)

    tentativas_login_falhas = Column(Integer, default=0, nullable=False)
    ultima_falha_login = Column(DateTime, nullable=True)
    bloqueado_ate = Column(DateTime, nullable=True)

    token_validos_apos = Column(DateTime, nullable=True)

    consentimento_lgpd = Column(Boolean, default=False, nullable=False)
    data_consentimento = Column(DateTime, nullable=True)
    versao_termos = Column(String(50), default="1.0")

    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    conteudos_criados = relationship("Conteudo", back_populates="autor")
    feedbacks = relationship("Feedback", back_populates="usuario")

    __table_args__ = (
        CheckConstraint("tentativas_login_falhas >= 0", name="ck_usuarios_tentativas_nao_negativas"),
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)

    subcategorias = relationship("Subcategoria", back_populates="categoria", cascade="all, delete-orphan")
    conteudos = relationship("Conteudo", back_populates="categoria")


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)

    categoria = relationship("Categoria", back_populates="subcategorias")
    conteudos = relationship("Conteudo", back_populates="subcategoria")

    __table_args__ = (
        UniqueConstraint("nome", "categoria_id", name="uq_subcategoria_nome_por_categoria"),
    )


class Conteudo(Base):
    __tablename__ = "conteudos"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(CHAR(36), unique=True, index=True, nullable=False, default=gerar_uuid)

    titulo = Column(String(200), nullable=False)
    sub_titulo = Column(String(200), nullable=True)
    resumo_home = Column(String(500), nullable=False)
    corpo_texto = Column(Text, nullable=False)
    fonte_original = Column(String(500), nullable=True)

    imagem_miniatura = Column(String(500), nullable=True)
    imagem_corpo = Column(String(500), nullable=True)
    fonte_imagem = Column(String(200), nullable=True)

    tipo_fonte = Column(
        Enum(TipoFonte, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status = Column(
        Enum(StatusConteudo, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StatusConteudo.EM_ANALISE,
        index=True,
    )

    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"), nullable=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    categoria = relationship("Categoria", back_populates="conteudos")
    subcategoria = relationship("Subcategoria", back_populates="conteudos")
    autor = relationship("Usuario", back_populates="conteudos_criados")
    feedbacks = relationship("Feedback", back_populates="conteudo", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    mensagem = Column(Text, nullable=False)
    tipo = Column(String(50), nullable=True)

    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    conteudo_id = Column(Integer, ForeignKey("conteudos.id"), nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="feedbacks")
    conteudo = relationship("Conteudo", back_populates="feedbacks")