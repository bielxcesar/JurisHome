"""Quiz diário: banco revisado, sorteio privado e consumo atômico por pessoa/dia."""
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from model.models import (fuso_br, Usuario, JuridleRodada, JuridleDia,
                          JuridleQuestao, JuridleQuestaoUso)
from auth.sessions import garantir_transacao

TAMANHO_RODADA = 5
META_MENSAL = 150
FUSO = fuso_br


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def data_local(data):
    return data.replace(tzinfo=timezone.utc).astimezone(FUSO).date()


def limites_dia():
    dia = data_local(agora())
    inicio = datetime.combine(dia, datetime.min.time()).replace(tzinfo=FUSO)
    fim = datetime.combine(dia + timedelta(days=1), datetime.min.time()).replace(tzinfo=FUSO)
    return dia.isoformat(), inicio.astimezone(timezone.utc).replace(tzinfo=None), fim.astimezone(timezone.utc).replace(tzinfo=None)


def garantir_banco_inicial(db):
    """Migra os 25 termos já publicados, sem alterar questões existentes/revisadas."""
    from services.glossario import consultar_glossario
    from sqlalchemy.exc import IntegrityError
    catalogo = consultar_glossario()['itens']
    existentes = set(db.scalars(select(JuridleQuestao.chave_origem).where(JuridleQuestao.chave_origem.is_not(None))))
    rng = secrets.SystemRandom()
    for item in catalogo:
        chave = 'glossario:' + item['id']
        if chave in existentes:
            continue
        erradas = rng.sample([i['termo'] for i in catalogo if i['id'] != item['id']], 3)
        try:
            with db.begin_nested():
                db.add(JuridleQuestao(chave_origem=chave, enunciado='Qual termo corresponde a esta definição?',
                    definicao=item['definicao'], area=item['area'], opcoes_json=json.dumps([item['termo'], *erradas], ensure_ascii=False),
                    correta=0, explicacao=item['definicao'], exemplo=item['exemplo'], fonte_url=item['fonte']['url'],
                    referencia=item.get('referencia', ''), status='aprovada', origem='glossario', criada_em=agora(), atualizada_em=agora()))
                db.flush()
        except IntegrityError:
            # Inicializações concorrentes usam a chave de origem única.
            pass
    db.commit()


def progresso(db, usuario_id):
    rodadas = db.query(JuridleRodada).filter_by(usuario_id=usuario_id).order_by(JuridleRodada.criada_em, JuridleRodada.uuid).all()
    acertos = total = sequencia = recorde = coroas = concluidas = 0
    dias, recentes = set(), []
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
    hoje = data_local(agora())
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
        'concluida': rodada.concluida_em is not None, 'expirada': rodada.expira_em <= agora(),
        'expiraEm': rodada.expira_em.isoformat() + 'Z'}
    if rodada.concluida_em:
        resultado['acertos'] = sum(int(r['acertou']) for r in json.loads(rodada.respostas_json))
        resultado['coroa'] = resultado['acertos'] == TAMANHO_RODADA
    elif not resultado['expirada']:
        pergunta = json.loads(rodada.perguntas_json)[rodada.respondidas]
        resultado['pergunta'] = {k: pergunta.get(k, '' if k != 'opcoes' else []) for k in ('enunciado', 'definicao', 'opcoes')}
        if pergunta.get('imagem'):
            resultado['pergunta'].update(imagem=pergunta['imagem'], imagemAlt=pergunta.get('imagemAlt', ''), creditoImagem=pergunta.get('creditoImagem', ''))
    return resultado


def ativa(db, usuario_id, bloquear=False):
    """Retorna a rodada DO DIA, inclusive concluída; respeita o histórico legado."""
    dia, inicio, fim = limites_dia()
    consulta = db.query(JuridleDia).filter_by(usuario_id=usuario_id, dia=dia)
    registro = (consulta.with_for_update() if bloquear else consulta).first()
    if registro:
        return db.get(JuridleRodada, registro.rodada_id)
    consulta = db.query(JuridleRodada).filter(JuridleRodada.usuario_id == usuario_id,
        JuridleRodada.criada_em >= inicio, JuridleRodada.criada_em < fim).order_by(JuridleRodada.criada_em.desc(), JuridleRodada.uuid.desc())
    return (consulta.with_for_update() if bloquear else consulta).first()


def iniciar(db, usuario_id):
    garantir_transacao(db)
    # A conta é o mutex estável no PostgreSQL/MySQL; BEGIN IMMEDIATE protege SQLite.
    usuario = db.query(Usuario).filter_by(uuid=usuario_id).with_for_update().first()
    if not usuario:
        raise HTTPException(404, 'Conta não encontrada.')
    dia, _, fim = limites_dia()
    rodada = ativa(db, usuario_id, bloquear=True)
    if rodada:
        if not db.get(JuridleDia, (usuario_id, dia)):
            db.add(JuridleDia(usuario_id=usuario_id, dia=dia, rodada_id=rodada.uuid))
            db.commit()
        return rodada
    # Uma questão sorteada fica reservada mesmo que a pessoa abandone a rodada.
    corte = (data_local(agora()) - timedelta(days=29)).isoformat()
    usadas = select(JuridleQuestaoUso.questao_id).where(JuridleQuestaoUso.usuario_id == usuario_id, JuridleQuestaoUso.dia >= corte)
    ids = list(db.scalars(select(JuridleQuestao.uuid).where(JuridleQuestao.status == 'aprovada', JuridleQuestao.uuid.not_in(usadas))))
    if len(ids) < TAMANHO_RODADA:
        raise HTTPException(409, 'Ainda não há cinco questões inéditas aprovadas para você. Aguarde a ampliação do banco de questões.')
    rng = secrets.SystemRandom()
    escolhidas = rng.sample(ids, TAMANHO_RODADA)
    itens = {q.uuid: q for q in db.query(JuridleQuestao).filter(JuridleQuestao.uuid.in_(escolhidas)).all()}
    perguntas = []
    for questao_id in escolhidas:
        q = itens[questao_id]
        opcoes = json.loads(q.opcoes_json)
        ordem = list(range(4))
        rng.shuffle(ordem)
        perguntas.append({'questaoId': q.uuid, 'enunciado': q.enunciado, 'definicao': q.definicao or '',
            'opcoes': [opcoes[i] for i in ordem], 'correta': ordem.index(q.correta), 'explicacao': q.explicacao,
            'exemplo': q.exemplo or '', 'fonte': {'url': q.fonte_url}, 'referencia': q.referencia or '',
            'termoId': '', 'imagem': q.imagem, 'imagemAlt': q.imagem_alt, 'creditoImagem': q.imagem_credito})
    # Limpa a chave legada; a unicidade por dia é garantida pela nova tabela.
    db.query(JuridleRodada).filter_by(ativa_chave=usuario_id).update({'ativa_chave': None}, synchronize_session=False)
    nova = JuridleRodada(usuario_id=usuario_id, ativa_chave=usuario_id,
        perguntas_json=json.dumps(perguntas, ensure_ascii=False), respostas_json='[]', criada_em=agora(), expira_em=fim)
    db.add(nova)
    db.flush()
    db.add(JuridleDia(usuario_id=usuario_id, dia=dia, rodada_id=nova.uuid))
    db.add_all([JuridleQuestaoUso(usuario_id=usuario_id, questao_id=i, rodada_id=nova.uuid, dia=dia) for i in escolhidas])
    db.commit()
    return nova


def estado(db, usuario_id):
    rodada = ativa(db, usuario_id)
    _, _, fim = limites_dia()
    return {'rodada': serializar(rodada), 'progresso': progresso(db, usuario_id),
        'disponivel': rodada is None, 'proximaRodadaEm': fim.isoformat() + 'Z'}


def responder(db, usuario_id, rodada_id, indice, opcao):
    garantir_transacao(db)
    rodada = db.query(JuridleRodada).filter_by(uuid=rodada_id, usuario_id=usuario_id).populate_existing().with_for_update().first()
    if not rodada:
        raise HTTPException(404, 'Rodada não encontrada.')
    respostas = json.loads(rodada.respostas_json)
    if indice < len(respostas):
        anterior = respostas[indice]
        if anterior['opcao'] != opcao:
            raise HTTPException(409, 'Esta pergunta já foi respondida.')
        return rodada, anterior
    if rodada.concluida_em or rodada.expira_em <= agora() or indice != rodada.respondidas or data_local(rodada.criada_em) != data_local(agora()):
        raise HTTPException(409, 'Rodada encerrada ou pergunta fora de ordem. Atualize o jogo.')
    pergunta = json.loads(rodada.perguntas_json)[indice]
    resposta = {'opcao': opcao, 'acertou': opcao == pergunta['correta'], 'correta': pergunta['correta'],
        'explicacao': pergunta['explicacao'], 'exemplo': pergunta.get('exemplo', ''),
        'fonte': pergunta.get('fonte', {}), 'referencia': pergunta.get('referencia', ''), 'termoId': pergunta.get('termoId', '')}
    respostas.append(resposta)
    rodada.respostas_json = json.dumps(respostas, ensure_ascii=False)
    rodada.respondidas += 1
    if rodada.respondidas == TAMANHO_RODADA:
        rodada.concluida_em = agora()
        rodada.ativa_chave = None
    db.commit()
    return rodada, resposta
