"""Rodadas individuais; perguntas e gabaritos ficam no servidor."""
import json
import secrets
from datetime import datetime, timedelta, timezone
from model.models import fuso_br

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.sessions import garantir_transacao
from model.models import JuridleRodada
from services.glossario import consultar_glossario

TAMANHO_RODADA = 5
FUSO = fuso_br


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def data_local(data):
    return data.replace(tzinfo=timezone.utc).astimezone(FUSO).date()


def perguntas():
    catalogo = consultar_glossario()['itens']
    rng = secrets.SystemRandom()
    resultado = []
    for item in rng.sample(catalogo, TAMANHO_RODADA):
        opcoes = [item, *rng.sample([outro for outro in catalogo if outro['id'] != item['id']], 3)]
        rng.shuffle(opcoes)
        resultado.append({
            'enunciado': 'Qual termo corresponde a esta definição?', 'definicao': item['definicao'],
            'opcoes': [opcao['termo'] for opcao in opcoes],
            'correta': next(i for i, opcao in enumerate(opcoes) if opcao['id'] == item['id']),
            'explicacao': item['definicao'], 'exemplo': item['exemplo'],
            'fonte': item['fonte'], 'termoId': item['id'],
        })
    return resultado


def progresso(db: Session, usuario_id: str):
    rodadas = db.query(JuridleRodada).filter_by(usuario_id=usuario_id).order_by(JuridleRodada.criada_em, JuridleRodada.uuid).all()
    acertos = total = sequencia = recorde = coroas = concluidas = 0
    dias = set()
    recentes = []
    for rodada in rodadas:
        respostas = json.loads(rodada.respostas_json)
        for resposta in respostas:
            total += 1
            acertos += int(resposta['acertou'])
            sequencia = sequencia + 1 if resposta['acertou'] else 0
            recorde = max(recorde, sequencia)
        if rodada.concluida_em:
            concluidas += 1
            pontos = sum(int(r['acertou']) for r in respostas)
            coroas += int(pontos == TAMANHO_RODADA)
            dias.add(data_local(rodada.concluida_em))
            recentes.append({'uuid': rodada.uuid, 'acertos': pontos, 'total': TAMANHO_RODADA,
                             'data': rodada.concluida_em.isoformat() + 'Z', 'coroa': pontos == TAMANHO_RODADA})
    hoje = datetime.now(FUSO).date()
    inicio = hoje if hoje in dias else hoje - timedelta(days=1)
    frequencia = 0
    while inicio in dias:
        frequencia += 1
        inicio -= timedelta(days=1)
    return {'nivel': 1 + acertos // 10, 'acertos': acertos, 'respondidas': total,
            'sequencia': sequencia, 'melhorSequencia': recorde, 'frequencia': frequencia,
            'coroas': coroas, 'rodadas': concluidas, 'historico': list(reversed(recentes[-5:]))}


def serializar(rodada):
    if not rodada:
        return None
    resultado = {'uuid': rodada.uuid, 'respondidas': rodada.respondidas, 'total': TAMANHO_RODADA,
                 'concluida': rodada.concluida_em is not None}
    if rodada.concluida_em:
        resultado['acertos'] = sum(int(r['acertou']) for r in json.loads(rodada.respostas_json))
        resultado['coroa'] = resultado['acertos'] == TAMANHO_RODADA
    else:
        pergunta = json.loads(rodada.perguntas_json)[rodada.respondidas]
        resultado['pergunta'] = {k: pergunta[k] for k in ('enunciado', 'definicao', 'opcoes')}
    return resultado


def ativa(db, usuario_id):
    return db.query(JuridleRodada).filter_by(ativa_chave=usuario_id).first()


def iniciar(db, usuario_id):
    garantir_transacao(db)
    rodada = db.query(JuridleRodada).filter_by(ativa_chave=usuario_id).with_for_update().first()
    if rodada and rodada.expira_em > agora():
        return rodada
    if rodada:
        rodada.ativa_chave = None
        db.flush()
    nova = JuridleRodada(usuario_id=usuario_id, ativa_chave=usuario_id,
                         perguntas_json=json.dumps(perguntas(), ensure_ascii=False), respostas_json='[]',
                         criada_em=agora(), expira_em=agora() + timedelta(hours=24))
    try:
        with db.begin_nested():
            db.add(nova)
            db.flush()
    except IntegrityError:
        # Duas abas iniciando juntas recebem a mesma rodada.
        existente = ativa(db, usuario_id)
        if existente is None:
            raise HTTPException(409, 'Sua rodada mudou em outra aba. Tente novamente.')
        return existente
    db.commit()
    return nova


def responder(db, usuario_id, rodada_id, indice, opcao):
    garantir_transacao(db)
    rodada = db.query(JuridleRodada).filter_by(uuid=rodada_id, usuario_id=usuario_id).with_for_update().first()
    if not rodada:
        raise HTTPException(404, 'Rodada não encontrada.')
    respostas = json.loads(rodada.respostas_json)
    if indice < len(respostas):
        # Repetir a mesma requisição não soma pontos de novo.
        anterior = respostas[indice]
        if anterior['opcao'] != opcao:
            raise HTTPException(409, 'Esta pergunta já foi respondida.')
        return rodada, anterior
    if rodada.concluida_em or rodada.expira_em <= agora() or indice != rodada.respondidas:
        raise HTTPException(409, 'Rodada expirada ou pergunta fora de ordem. Atualize o jogo.')
    pergunta = json.loads(rodada.perguntas_json)[indice]
    resposta = {'opcao': opcao, 'acertou': opcao == pergunta['correta'], 'correta': pergunta['correta'],
                'explicacao': pergunta['explicacao'], 'exemplo': pergunta['exemplo'],
                'fonte': pergunta['fonte'], 'termoId': pergunta['termoId']}
    respostas.append(resposta)
    rodada.respostas_json = json.dumps(respostas, ensure_ascii=False)
    rodada.respondidas += 1
    if rodada.respondidas == TAMANHO_RODADA:
        rodada.concluida_em = agora()
        rodada.ativa_chave = None
    db.commit()
    return rodada, resposta
