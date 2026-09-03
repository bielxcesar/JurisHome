from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String,Text, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Aqui defino os unicos Usuarios
class TipoUsuario (str, enum.Enum):
    ESTUDANTE = "estudante"
    ADMINISTRADOR = "administrador"

# Definicao de categoria de fonte para o material
class TipoFonte(str, enum.Enum):
    ACORDAO = "acordao"
    Doutrina = "doutrina"
    Legislacao = "legislacao"

class StatusConteudo(str, enum.Enum):
    EM_ANALISE = "em_analise"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"

# Coloquei a base do banco de dados e a tabela de usuario, com os campos que o usuario vai ter
class Usuario(Base):

    __tablename__= "usuarios"

    id = Column (Integer, primary_key=True, index=True)
    nome = Column (String (100), nullable=False)
    email = Column (String (150), unique=True, index=True, nullable=False)
    senha_hash = Column (String(255), nullable=True)
    google_id = Column (String(255), nullable=True, unique=True)
    tipo_usuario = Column (Enum(TipoUsuario), nullable=False, default=TipoUsuario.ESTUDANTE)
    e_root_admin = Column(Boolean, default=False, nullable=False)

    universidade = Column (String(255), nullable=True)
    especialidade_juridica = Column (String(100), nullable=True)

    totp_secret = Column (String(255), nullable=True)
    is_2fa_enabled = Column (Boolean, default=False)


    tentativas_login_falhas = Column (Integer, default=0)
    ultima_falha_login = Column (DateTime, nullable=True)
    bloqueado_ate = Column (DateTime, nullable=True)


    token_validos_apos = Column (DateTime, nullable=True)

    consentimento_lgpd = Column (Boolean, default=False, nullable=False)
    data_consentimento = Column (DateTime, nullable=True)
    versao_termos = Column (String(50), default="1.0")


    criado_em = Column (DateTime, default=datetime.utcnow)
    atualizado_em = Column (DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign key para a tabela de conteudo
    conteudos_criados = relationship("Conteudo", back_populates="autor")
    feedbacks = relationship("Feedback", back_populates="usuario")

class Categoria (Base):

    __tablename__ = "categorias"

    id = Column (Integer, primary_key=True, index=True)
    nome = Column (String(100), nullable=False, unique=True)
    descricao = Column (Text, nullable=True)

    conteudos = relationship("Conteudo", back_populates="categoria")

class Conteudo (Base):

    __tablename__ = "conteudos"

    id = Column (Integer, primary_key=True, index=True)

    titulo = Column (String(200), nullable=False)
    sub_titulo = Column (String(200), nullable=True)
    resumo_home = Column (String(500), nullable=False)
    corpo_texto = Column (Text, nullable=False)
    fonte_original = Column (String(500), nullable=True)

    # Midia e Fontes
    imagem_miniatura = Column (String(500), nullable=True)
    imagem_corpo = Column (String(500), nullable=True)
    fonte_imagem = Column (String(200), nullable=True)

    #Classificação e validação
    tipo_fonte = Column (Enum(TipoFonte), nullable=False)
    status = Column (Enum(StatusConteudo), nullable=False, default=StatusConteudo.EM_ANALISE)

    # Foreign key para as outras tabelas
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"), nullable=True)
    autor_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Conexões de retorno
    categoria = relationship("Categoria", back_populates="conteudos")
    subcategoria = relationship("Subcategoria", back_populates="conteudos")
    autor = relationship("Usuario", back_populates="conteudos_criados")
    feedbacks = relationship("Feedback", back_populates="conteudo")

class Feedback (Base):

    __tablename__ = "feedbacks"

    id = Column (Integer, primary_key=True, index=True)
    mensagem = Column (Text, nullable=False)
    tipo = Column (String(50), nullable=True)  # Pode ser "elogio", "sugestão", "reclamação", etc.

    # Foreign key para as outras tabelas
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    conteudo_id = Column(Integer, ForeignKey("conteudos.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Conexões de retorno
    usuario = relationship("Usuario", back_populates="feedbacks")
    conteudo = relationship("Conteudo", back_populates="feedbacks")

