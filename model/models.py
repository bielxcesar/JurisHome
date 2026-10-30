import enum
import uuid as uuid_lib
from datetime import datetime, timezone
from dateutil import tz

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean,
    CheckConstraint, UniqueConstraint, Index, case
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from database import Base

# =====================================================================
# Configuração do Fuso Horário Local (São Paulo / Brasília)
# =====================================================================
fuso_br = tz.gettz("America/Sao_Paulo")

def obter_hora_local():
    """Retorna a data e hora atual no fuso horário do Brasil."""
    return datetime.now(fuso_br)

class TipoUsuario(str, enum.Enum):
    ESTUDANTE = "estudante"
    ADMINISTRADOR = "administrador"


class TipoFonte(str, enum.Enum):
    ACORDAO = "acordao"
    DOUTRINA = "doutrina"
    LEGISLACAO = "legislacao"
    G1 = "g1"
    TERRA = "terra"
    UOL = "uol"
    X = "x"
    INSTAGRAM = "instagram"


class StatusConteudo(str, enum.Enum):
    EM_ANALISE = "em_analise"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


def gerar_uuid() -> str:
    return str(uuid_lib.uuid4())


class Usuario(Base):
    __tablename__ = "usuarios"

    uuid = Column(CHAR(36), primary_key=True, default=gerar_uuid)

    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=True)
    foto_perfil = Column(String, nullable=True)
    
    tipo_usuario = Column(
        Enum(TipoUsuario, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TipoUsuario.ESTUDANTE,
        index=True,
    )
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

    criado_em = Column(DateTime, default=obter_hora_local, nullable=False)
    atualizado_em = Column(DateTime, default=obter_hora_local, onupdate=obter_hora_local, nullable=False)

    conteudos_criados = relationship("Conteudo", back_populates="autor")
    feedbacks = relationship("Feedback", back_populates="usuario")

    __table_args__ = (
        CheckConstraint("tentativas_login_falhas >= 0", name="ck_usuarios_tentativas_nao_negativas"),
        CheckConstraint("NOT e_root_admin OR tipo_usuario = 'administrador'", name="ck_root_deve_ser_administrador"),
        # Roots produzem a mesma chave 1; as outras contas produzem NULL.
        # Um índice único aceita vários NULLs, mas nunca dois roots.
        Index("uq_usuarios_root_unico", case((e_root_admin, 1), else_=None), unique=True).ddl_if(dialect=("sqlite", "postgresql")),
    )


class DesafioConsumido(Base):
    __tablename__ = "auth_desafios_consumidos"
    digest = Column(String(64), primary_key=True)
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=False, index=True)
    expira_em = Column(DateTime, nullable=False, index=True)


class AdministradorExcluido(Base):
    """Preserva vínculos editoriais sem manter uma conta de acesso ativa."""
    __tablename__ = "administradores_excluidos"
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), primary_key=True)
    excluido_por = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=False)
    excluido_em = Column(DateTime, nullable=False)


class CodigoTotpConsumido(Base):
    __tablename__ = "auth_totp_consumidos"
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), primary_key=True)
    segredo_digest = Column(String(64), primary_key=True)
    intervalo = Column(Integer, primary_key=True)


class SessaoAutenticada(Base):
    __tablename__ = "auth_sessoes"
    id = Column(String(36), primary_key=True, default=gerar_uuid)
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=False, index=True)
    criada_em = Column(DateTime, nullable=False)
    expira_em = Column(DateTime, nullable=False, index=True)
    revogada = Column(Boolean, nullable=False, default=False)


class RefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    digest = Column(String(64), primary_key=True)
    sessao_id = Column(String(36), ForeignKey("auth_sessoes.id"), nullable=False, index=True)
    usado = Column(Boolean, nullable=False, default=False)


class Categoria(Base):
    __tablename__ = "categorias"

    uuid = Column(CHAR(36), primary_key=True, default=gerar_uuid)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)

    subcategorias = relationship("Subcategoria", back_populates="categoria", cascade="all, delete-orphan")
    conteudos = relationship("Conteudo", back_populates="categoria")


class JuridleRodada(Base):
    __tablename__ = "juridle_rodadas"
    uuid = Column(String(36), primary_key=True, default=gerar_uuid)
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=False, index=True)
    # Apenas uma rodada ativa por pessoa; NULL permite manter o histórico concluído.
    ativa_chave = Column(String(36), unique=True, nullable=True)
    perguntas_json = Column(Text, nullable=False)
    respostas_json = Column(Text, nullable=False, default="[]")
    respondidas = Column(Integer, nullable=False, default=0)
    criada_em = Column(DateTime, nullable=False)
    expira_em = Column(DateTime, nullable=False)
    concluida_em = Column(DateTime, nullable=True)


class ConteudoLeitura(Base):
    __tablename__ = "conteudo_leituras"
    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), primary_key=True)
    conteudo_id = Column(String, ForeignKey("conteudos.uuid", ondelete="CASCADE"), primary_key=True)
    dia = Column(String(10), primary_key=True)


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    uuid = Column(CHAR(36), primary_key=True, default=gerar_uuid)
    nome = Column(String(100), nullable=False)
    categoria_id = Column(CHAR(36), ForeignKey("categorias.uuid"), nullable=False)

    categoria = relationship("Categoria", back_populates="subcategorias")
    conteudos = relationship("Conteudo", back_populates="subcategoria")

    __table_args__ = (
        UniqueConstraint("nome", "categoria_id", name="uq_subcategoria_nome_por_categoria"),
    )

# Area de adição de conteudo 
class Conteudo(Base):
    __tablename__ = "conteudos"

    uuid = Column(String, primary_key=True, default=gerar_uuid)
    titulo = Column(String, nullable=False)
    sub_titulo = Column(String, nullable=True)
    resumo_home = Column(String, nullable=False)
    corpo_texto = Column(Text, nullable=False)
    
    # Colunas de imagem grandes (Text)
    imagem_miniatura = Column(Text, nullable=True)
    imagem_corpo = Column(Text, nullable=True)
    imagem_extra_2 = Column(Text, nullable=True)
    imagem_extra_3 = Column(Text, nullable=True)
    
    fonte_original = Column(String, nullable=True)
    fonte_imagem = Column(String, nullable=True)

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

    categoria_id = Column(CHAR(36), ForeignKey("categorias.uuid"), nullable=False)
    subcategoria_id = Column(CHAR(36), ForeignKey("subcategorias.uuid"), nullable=True)
    autor_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=False)

    # Corrigido para pegar a hora do Brasil na criação do conteúdo
    criado_em = Column(DateTime, default=obter_hora_local, nullable=False)

    categoria = relationship("Categoria", back_populates="conteudos")
    subcategoria = relationship("Subcategoria", back_populates="conteudos")
    autor = relationship("Usuario", back_populates="conteudos_criados")
    feedbacks = relationship("Feedback", back_populates="conteudo", cascade="all, delete-orphan")
    tags = Column(String, nullable=True)
    editorial = relationship("ConteudoEditorial", back_populates="conteudo", uselist=False, cascade="all, delete-orphan")


class ConteudoEditorial(Base):
    __tablename__ = "conteudo_editorial"
    conteudo_id = Column(String, ForeignKey("conteudos.uuid", ondelete="CASCADE"), primary_key=True)
    titulo_home = Column(String(180), nullable=True)
    configuracao_json = Column(Text, nullable=False, default="{}")
    conteudo = relationship("Conteudo", back_populates="editorial")
    
class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    mensagem = Column(Text, nullable=False)
    tipo = Column(String(50), nullable=True)

    usuario_id = Column(CHAR(36), ForeignKey("usuarios.uuid"), nullable=True)
    conteudo_id = Column(CHAR(36), ForeignKey("conteudos.uuid"), nullable=True)
    
    criado_em = Column(DateTime, default=obter_hora_local, nullable=False)

    usuario = relationship("Usuario", back_populates="feedbacks")
    conteudo = relationship("Conteudo", back_populates="feedbacks")


class FeedbackAtendimento(Base):
    __tablename__ = "feedback_atendimentos"

    id = Column(String(50), primary_key=True)
    protocolo = Column(String(30), unique=True, index=True, nullable=False)
    usuario_id = Column(String(50), nullable=False, default="usr-sessao")
    usuario_nome = Column(String(100), nullable=False)
    usuario_email = Column(String(150), nullable=False)
    tipo = Column(String(50), nullable=False)
    assunto = Column(String(120), nullable=False)
    mensagem = Column(Text, nullable=False)
    avaliacao = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="Recebido", index=True)
    prioridade = Column(String(20), nullable=False, default="Normal", index=True)
    respostas_json = Column(Text, nullable=False, default="[]")
    observacoes_json = Column(Text, nullable=False, default="[]")
    historico_json = Column(Text, nullable=False, default="[]")
    novo = Column(Boolean, nullable=False, default=True)
    arquivado = Column(Boolean, nullable=False, default=False)
    
    criado_em = Column(DateTime, default=obter_hora_local, nullable=False)
    atualizado_em = Column(DateTime, default=obter_hora_local, onupdate=obter_hora_local, nullable=False)

    __table_args__ = (
        CheckConstraint("avaliacao IS NULL OR (avaliacao >= 1 AND avaliacao <= 5)", name="ck_feedback_avaliacao"),
    )


class LogAuditoria(Base):
    #Registra operações relevantes realizadas no JurisHome.

    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(CHAR(36), nullable=True, index=True)
    usuario_tipo = Column(String(30), nullable=False, default="anonimo")
    acao = Column(String(80), nullable=False, index=True)
    recurso_tipo = Column(String(80), nullable=False, index=True)
    recurso_id = Column(String(100), nullable=True)
    resultado = Column(String(20), nullable=False, index=True)
    correlacao_id = Column(String(36), nullable=False, index=True)
    detalhes_json = Column(Text, nullable=False, default="{}")
    
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
