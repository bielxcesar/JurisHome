from services.validacao import ModeloSeguro, TextoBusca, fonte_http, linha
import json
import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from auth.security import get_current_user
from auth.sessions import garantir_transacao
from database import get_db
from model.models import Usuario, TipoUsuario, JuridleQuestao
from services import juridle
from services.auditoria import registrar_auditoria
from services.imagens import normalizar_imagem, url_fonte_segura

router = APIRouter(tags=['Juridle'])
templates = Jinja2Templates(directory='templates')


def administrador(usuario: Usuario = Depends(get_current_user)):
    if usuario.tipo_usuario != TipoUsuario.ADMINISTRADOR:
        raise HTTPException(404, 'Página não encontrada.')
    return usuario


class Resposta(ModeloSeguro):
    model_config = ConfigDict(extra='forbid')
    pergunta: int = Field(strict=True, ge=0, lt=juridle.TAMANHO_RODADA)
    opcao: int = Field(strict=True, ge=0, le=3)


@router.get('/api/juridle/estado')
def estado(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return juridle.estado(db, usuario.uuid)


@router.post('/api/juridle/rodadas')
def iniciar(db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    rodada = juridle.iniciar(db, usuario.uuid)
    return {**juridle.estado(db, usuario.uuid), 'rodada': juridle.serializar(rodada)}


@router.post('/api/juridle/rodadas/{rodada_id}/respostas')
def responder(rodada_id: str, dados: Resposta, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    rodada, resultado = juridle.responder(db, usuario.uuid, rodada_id, dados.pergunta, dados.opcao)
    return {**juridle.estado(db, usuario.uuid), 'rodada': juridle.serializar(rodada), 'resultado': resultado}


class QuestaoEntrada(ModeloSeguro):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    enunciado: str = Field(min_length=10, max_length=1000)
    area: str = Field(default='Conhecimentos jurídicos', min_length=3, max_length=100)
    correta: str = Field(min_length=1, max_length=300)
    erradas: list[str] = Field(min_length=3, max_length=3)
    explicacao: str = Field(min_length=20, max_length=2000)
    fonte_url: str = Field(max_length=2000)
    referencia: str = Field(default='', max_length=200)
    imagem: str | None = None
    imagem_alt: str = Field(default='', max_length=200)
    imagem_credito: str = Field(default='', max_length=1000)

    @field_validator('fonte_url')
    @classmethod
    def fonte_valida(cls, valor):
        return fonte_http(valor)

    @field_validator('imagem')
    @classmethod
    def imagem_valida(cls, valor):
        return normalizar_imagem(valor)

    @model_validator(mode='after')
    def alternativas_validas(self):
        opcoes = [self.correta, *self.erradas]
        if any(not o.strip() or len(o) > 300 for o in opcoes):
            raise ValueError('Preencha quatro alternativas de até 300 caracteres.')
        normalizadas = [' '.join(unicodedata.normalize('NFKC', o).casefold().split()) for o in opcoes]
        if len(set(normalizadas)) != 4:
            raise ValueError('As quatro alternativas devem ser diferentes.')
        if self.imagem and (not self.imagem_alt or not self.imagem_credito):
            raise ValueError('Informe a descrição e o crédito da imagem opcional.')
        return self


class Revisao(ModeloSeguro):
    model_config = ConfigDict(extra='forbid')
    decisao: Literal['aprovar', 'rejeitar', 'arquivar']
    versao: int = Field(strict=True, ge=1)
    motivo: str = Field(default='', max_length=500)


@router.get('/juridle/ampliar', response_class=HTMLResponse)
def pagina_banco(request: Request, usuario: Usuario = Depends(administrador)):
    return templates.TemplateResponse(request=request, name='juridle-questoes.html', context={
        'tipo_usuario': usuario.tipo_usuario.value, 'e_root': usuario.e_root_admin})


def resumo(q):
    return {'uuid': q.uuid, 'enunciado': q.enunciado, 'area': q.area, 'status': q.status,
        'origem': q.origem, 'versao': q.versao, 'criadaEm': q.criada_em.isoformat() + 'Z', 'motivo': q.motivo_revisao or ''}


@router.get('/api/juridle/questoes')
def listar(status: Literal['todas', 'pendente', 'aprovada', 'rejeitada', 'arquivada'] = 'todas',
           busca: TextoBusca = Query(default='', max_length=80), pagina: int = Query(default=1, ge=1),
           db: Session = Depends(get_db), usuario: Usuario = Depends(administrador)):
    consulta = db.query(JuridleQuestao)
    if not usuario.e_root_admin:
        consulta = consulta.filter_by(autor_id=usuario.uuid)
    if status != 'todas':
        consulta = consulta.filter_by(status=status)
    if busca.strip():
        consulta = consulta.filter(JuridleQuestao.enunciado.ilike('%' + busca.strip().replace('%', '\\%').replace('_', '\\_') + '%', escape='\\'))
    total = consulta.count()
    itens = consulta.order_by(JuridleQuestao.criada_em.desc(), JuridleQuestao.uuid).offset((pagina-1)*10).limit(10).all()
    aprovadas = db.query(JuridleQuestao).filter_by(status='aprovada').count()
    pendentes = db.query(JuridleQuestao).filter_by(status='pendente')
    if not usuario.e_root_admin:
        pendentes = pendentes.filter_by(autor_id=usuario.uuid)
    return {'itens': [resumo(q) for q in itens], 'total': total, 'pagina': pagina,
        'root': bool(usuario.e_root_admin), 'aprovadas': aprovadas, 'pendentes': pendentes.count(),
        'meta': juridle.META_MENSAL, 'diasCobertos': aprovadas // juridle.TAMANHO_RODADA}


@router.post('/api/juridle/questoes', status_code=201)
def criar(dados: QuestaoEntrada, db: Session = Depends(get_db), usuario: Usuario = Depends(administrador)):
    garantir_transacao(db)
    db.query(Usuario).filter_by(uuid=usuario.uuid).with_for_update().one()
    from datetime import timedelta
    if db.query(JuridleQuestao).filter(JuridleQuestao.autor_id == usuario.uuid, JuridleQuestao.criada_em >= juridle.agora() - timedelta(hours=1)).count() >= 60:
        raise HTTPException(429, 'Limite de 60 questões por hora. Continue mais tarde.')
    q = JuridleQuestao(enunciado=dados.enunciado, area=dados.area, opcoes_json=json.dumps([dados.correta, *dados.erradas], ensure_ascii=False),
        correta=0, explicacao=dados.explicacao, fonte_url=dados.fonte_url, referencia=dados.referencia,
        imagem=dados.imagem, imagem_alt=dados.imagem_alt, imagem_credito=dados.imagem_credito,
        autor_id=usuario.uuid, status='pendente', origem='administrador', criada_em=juridle.agora(), atualizada_em=juridle.agora())
    db.add(q)
    db.flush()
    registrar_auditoria(db, acao='juridle_questao_enviada', recurso_tipo='juridle_questao', recurso_id=q.uuid,
        usuario=usuario, resultado='sucesso')
    db.commit()
    return resumo(q)


@router.get('/api/juridle/questoes/{questao_id}')
def detalhes(questao_id: str, db: Session = Depends(get_db), usuario: Usuario = Depends(administrador)):
    q = db.get(JuridleQuestao, questao_id)
    if not q or (not usuario.e_root_admin and q.autor_id != usuario.uuid):
        raise HTTPException(404, 'Questão não encontrada.')
    return {**resumo(q), 'opcoes': json.loads(q.opcoes_json), 'correta': q.correta, 'definicao': q.definicao or '',
        'explicacao': q.explicacao, 'fonte_url': q.fonte_url, 'referencia': q.referencia,
        'imagem': q.imagem, 'imagem_alt': q.imagem_alt, 'imagem_credito': q.imagem_credito}


@router.post('/api/juridle/questoes/{questao_id}/revisao')
def revisar(questao_id: str, dados: Revisao, db: Session = Depends(get_db), usuario: Usuario = Depends(administrador)):
    if not usuario.e_root_admin:
        raise HTTPException(403, 'Somente o root pode revisar questões.')
    garantir_transacao(db)
    q = db.query(JuridleQuestao).filter_by(uuid=questao_id).populate_existing().with_for_update().first()
    if not q:
        raise HTTPException(404, 'Questão não encontrada.')
    if q.versao != dados.versao:
        raise HTTPException(409, 'Esta questão foi alterada. Atualize a lista antes de revisar.')
    if dados.decisao == 'arquivar':
        if q.status != 'aprovada':
            raise HTTPException(409, 'Somente questões aprovadas podem ser arquivadas.')
    elif q.status != 'pendente':
        raise HTTPException(409, 'Esta questão já foi revisada.')
    if dados.decisao in ('rejeitar', 'arquivar') and len(dados.motivo.strip()) < 5:
        raise HTTPException(422, 'Informe o motivo com pelo menos cinco caracteres.')
    q.status = {'aprovar': 'aprovada', 'rejeitar': 'rejeitada', 'arquivar': 'arquivada'}[dados.decisao]
    q.revisor_id = usuario.uuid
    q.motivo_revisao = dados.motivo.strip()
    q.revisada_em = q.atualizada_em = juridle.agora()
    q.versao += 1
    registrar_auditoria(db, acao='juridle_questao_revisada', recurso_tipo='juridle_questao', recurso_id=q.uuid,
        usuario=usuario, resultado='sucesso', detalhes={'decisao': dados.decisao, 'versao': q.versao})
    db.commit()
    return resumo(q)
