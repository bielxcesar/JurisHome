import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from feedback_database import get_feedback_db
from model.models import FeedbackAtendimento


public_router = APIRouter(prefix="/api/feedbacks", tags=["feedbacks"])
admin_router = APIRouter(prefix="/api/admin/feedbacks", tags=["feedbacks-admin"])

TIPOS = (
    "Reclamação",
    "Dificuldade de acesso",
    "Problema técnico",
    "Sugestão",
    "Dúvida",
    "Elogio",
    "Outro",
)
STATUS = ("Recebido", "Em análise", "Respondido", "Resolvido", "Arquivado")
PRIORIDADES = ("Baixa", "Normal", "Alta", "Urgente")


class FeedbackCriacao(BaseModel):
    tipo: str
    assunto: str = Field(min_length=5, max_length=120)
    mensagem: str = Field(min_length=10, max_length=2000)
    avaliacao: int | None = Field(default=None, ge=1, le=5)

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, valor: str) -> str:
        if valor not in TIPOS:
            raise ValueError("Motivo do contato inválido.")
        return valor

    @field_validator("assunto")
    @classmethod
    def validar_assunto(cls, valor: str) -> str:
        valor = valor.strip()
        if not 5 <= len(valor) <= 120:
            raise ValueError("O assunto deve ter entre 5 e 120 caracteres.")
        return valor

    @field_validator("mensagem")
    @classmethod
    def validar_mensagem(cls, valor: str) -> str:
        valor = valor.strip()
        if not 10 <= len(valor) <= 2000:
            raise ValueError("A mensagem deve ter entre 10 e 2.000 caracteres.")
        return valor


class AlteracaoStatus(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validar_status(cls, valor: str) -> str:
        if valor not in STATUS:
            raise ValueError("Status inválido.")
        return valor


class AlteracaoPrioridade(BaseModel):
    prioridade: str

    @field_validator("prioridade")
    @classmethod
    def validar_prioridade(cls, valor: str) -> str:
        if valor not in PRIORIDADES:
            raise ValueError("Prioridade inválida.")
        return valor


class MensagemAdministrativa(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)

    @field_validator("mensagem")
    @classmethod
    def limpar_mensagem(cls, valor: str) -> str:
        return valor.strip()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(data: datetime) -> str:
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.isoformat()


def _ler_json(valor: str) -> list[dict]:
    try:
        dados = json.loads(valor or "[]")
        return dados if isinstance(dados, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _salvar_json(valor: list[dict]) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _gerar_protocolo(db: Session) -> str:
    data = _agora().strftime("%Y%m%d")
    while True:
        sufixo = str(uuid.uuid4().int)[-4:]
        protocolo = f"JH-{data}-{sufixo}"
        existe = db.query(FeedbackAtendimento).filter_by(protocolo=protocolo).first()
        if not existe:
            return protocolo


def _buscar(db: Session, feedback_id: str) -> FeedbackAtendimento:
    feedback = db.query(FeedbackAtendimento).filter_by(id=feedback_id).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback não encontrado.")
    return feedback


def _adicionar_historico(
    feedback: FeedbackAtendimento,
    tipo: str,
    descricao: str,
    visibilidade: str,
) -> None:
    historico = _ler_json(feedback.historico_json)
    historico.append(
        {
            "id": f"hist-{uuid.uuid4()}",
            "tipo": tipo,
            "autor": "Administrador JurisHome",
            "descricao": descricao,
            "criadoEm": _iso(_agora()),
            "visibilidade": visibilidade,
        }
    )
    feedback.historico_json = _salvar_json(historico)


def _serializar(feedback: FeedbackAtendimento, incluir_interno: bool = True) -> dict:
    historico = _ler_json(feedback.historico_json)
    if not incluir_interno:
        historico = [item for item in historico if item.get("visibilidade") != "interna"]

    resultado = {
        "id": feedback.id,
        "protocolo": feedback.protocolo,
        "usuario": {
            "id": feedback.usuario_id,
            "nome": feedback.usuario_nome,
            "email": feedback.usuario_email,
        },
        "tipo": feedback.tipo,
        "assunto": feedback.assunto,
        "mensagem": feedback.mensagem,
        "avaliacao": feedback.avaliacao,
        "status": feedback.status,
        "prioridade": feedback.prioridade,
        "criadoEm": _iso(feedback.criado_em),
        "atualizadoEm": _iso(feedback.atualizado_em),
        "respostas": _ler_json(feedback.respostas_json),
        "historico": historico,
        "novo": feedback.novo,
        "arquivado": feedback.arquivado,
    }
    if incluir_interno:
        resultado["observacoesInternas"] = _ler_json(feedback.observacoes_json)
    return resultado


def _confirmar_alteracao(db: Session, feedback: FeedbackAtendimento) -> dict:
    feedback.atualizado_em = _agora()
    db.commit()
    db.refresh(feedback)
    return _serializar(feedback)


@public_router.post("", status_code=status.HTTP_201_CREATED)
def criar_feedback(dados: FeedbackCriacao, db: Session = Depends(get_feedback_db)):
    agora = _agora()
    feedback_id = f"fb-{uuid.uuid4()}"
    historico = [
        {
            "id": f"hist-{uuid.uuid4()}",
            "tipo": "criacao",
            "autor": "Usuário",
            "descricao": "Feedback enviado.",
            "criadoEm": _iso(agora),
            "visibilidade": "publica",
        }
    ]
    feedback = FeedbackAtendimento(
        id=feedback_id,
        protocolo=_gerar_protocolo(db),
        usuario_id="usr-sessao",
        usuario_nome="Usuário",
        usuario_email="usuario@jurishome.local",
        tipo=dados.tipo,
        assunto=dados.assunto,
        mensagem=dados.mensagem,
        avaliacao=dados.avaliacao,
        status="Recebido",
        prioridade="Normal",
        respostas_json="[]",
        observacoes_json="[]",
        historico_json=_salvar_json(historico),
        novo=True,
        arquivado=False,
        criado_em=agora,
        atualizado_em=agora,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return _serializar(feedback, incluir_interno=False)


@admin_router.get("")
def listar_feedbacks(db: Session = Depends(get_feedback_db)):
    registros = db.query(FeedbackAtendimento).order_by(FeedbackAtendimento.criado_em.desc()).all()
    return [_serializar(item) for item in registros]


@admin_router.get("/{feedback_id}")
def consultar_feedback(feedback_id: str, db: Session = Depends(get_feedback_db)):
    return _serializar(_buscar(db, feedback_id))


@admin_router.patch("/{feedback_id}/status")
def alterar_status(feedback_id: str, dados: AlteracaoStatus, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    feedback.status = dados.status
    feedback.arquivado = dados.status == "Arquivado"
    _adicionar_historico(feedback, "status", f"Status: {dados.status}.", "publica")
    return _confirmar_alteracao(db, feedback)


@admin_router.patch("/{feedback_id}/prioridade")
def alterar_prioridade(feedback_id: str, dados: AlteracaoPrioridade, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    feedback.prioridade = dados.prioridade
    _adicionar_historico(feedback, "prioridade", f"Prioridade: {dados.prioridade}.", "interna")
    return _confirmar_alteracao(db, feedback)


@admin_router.post("/{feedback_id}/respostas")
def responder_feedback(feedback_id: str, dados: MensagemAdministrativa, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    respostas = _ler_json(feedback.respostas_json)
    respostas.append(
        {
            "id": f"resp-{uuid.uuid4()}",
            "autor": "Equipe JurisHome",
            "papel": "administrador",
            "mensagem": dados.mensagem,
            "criadoEm": _iso(_agora()),
        }
    )
    feedback.respostas_json = _salvar_json(respostas)
    feedback.status = "Respondido"
    feedback.arquivado = False
    feedback.novo = False
    _adicionar_historico(feedback, "resposta", "Resposta enviada.", "publica")
    return _confirmar_alteracao(db, feedback)


@admin_router.post("/{feedback_id}/observacoes")
def adicionar_observacao(feedback_id: str, dados: MensagemAdministrativa, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    observacoes = _ler_json(feedback.observacoes_json)
    observacoes.append(
        {
            "id": f"obs-{uuid.uuid4()}",
            "autor": "Administrador JurisHome",
            "mensagem": dados.mensagem,
            "criadoEm": _iso(_agora()),
        }
    )
    feedback.observacoes_json = _salvar_json(observacoes)
    _adicionar_historico(feedback, "observacao", "Observação adicionada.", "interna")
    return _confirmar_alteracao(db, feedback)


@admin_router.patch("/{feedback_id}/visto")
def marcar_como_visto(feedback_id: str, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    feedback.novo = False
    return _confirmar_alteracao(db, feedback)


@admin_router.patch("/{feedback_id}/arquivar")
def arquivar_feedback(feedback_id: str, db: Session = Depends(get_feedback_db)):
    feedback = _buscar(db, feedback_id)
    feedback.status = "Arquivado"
    feedback.arquivado = True
    _adicionar_historico(feedback, "status", "Status: Arquivado.", "publica")
    return _confirmar_alteracao(db, feedback)
