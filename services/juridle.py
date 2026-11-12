"""Quiz diário: banco revisado, sorteio privado e consumo atômico por pessoa/dia."""
import json
import secrets
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import load_only
from model.models import (fuso_br, Usuario, JuridleRodada, JuridleDia,
                          JuridleQuestao, JuridleQuestaoUso)
from auth.sessions import garantir_transacao

TAMANHO_RODADA = 5
META_MENSAL = 150
FUSO = fuso_br
VIRADA = time(5)
UM_DIA = timedelta(days=1)


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def data_local(data):
    local = data.replace(tzinfo=timezone.utc).astimezone(FUSO)
    return local.date() - UM_DIA if local.time() < VIRADA else local.date()


def limites_dia(instante=None):
    dia = data_local(instante if instante is not None else agora())
    inicio = datetime.combine(dia, VIRADA, tzinfo=FUSO)
    fim = datetime.combine(dia + UM_DIA, VIRADA, tzinfo=FUSO)
    return dia.isoformat(), inicio.astimezone(timezone.utc).replace(tzinfo=None), fim.astimezone(timezone.utc).replace(tzinfo=None)


def garantir_banco_inicial(db):
    """Migra os termos já publicados, sem alterar questões existentes ou revisadas."""
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


def resumo_coroas(dias, instante):
    hoje = data_local(instante)
    ontem = hoje - UM_DIA
    anterior = None
    sequencia = recorde = atual = 0
    for dia in sorted(dias):
        sequencia = sequencia + 1 if anterior == dia - UM_DIA else 1
        recorde = max(recorde, sequencia)
        if dia in (ontem, hoje):
            atual = sequencia
        anterior = dia
    _, _, fim = limites_dia(instante)
    return {'coroaHoje': hoje in dias, 'sequenciaCoroas': atual,
            'recordeCoroas': recorde, 'proximaRodadaEm': fim.isoformat() + 'Z',
            'diaDesafio': hoje.isoformat()}


def coroa_diaria(db, usuario_id):
    concluidas = db.query(JuridleRodada.concluida_em, JuridleRodada.respostas_json).filter(
        JuridleRodada.usuario_id == usuario_id, JuridleRodada.concluida_em.is_not(None))
    dias = {data_local(data) for data, respostas in concluidas
            if sum(int(r['acertou']) for r in json.loads(respostas)) == TAMANHO_RODADA}
    instante = agora()
    return {**resumo_coroas(dias, instante), 'servidorEm': instante.isoformat() + 'Z'}


def progresso(db, usuario_id, instante=None):
    instante = instante if instante is not None else agora()
    rodadas = db.query(JuridleRodada).options(load_only(
        JuridleRodada.respostas_json, JuridleRodada.concluida_em)).filter_by(usuario_id=usuario_id).order_by(JuridleRodada.criada_em, JuridleRodada.uuid).all()
    acertos = total = sequencia = recorde = coroas = concluidas = 0
    dias, dias_coroa, recentes = set(), set(), []
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
            dia = data_local(rodada.concluida_em)
            dias.add(dia)
            if pontos == TAMANHO_RODADA:
                dias_coroa.add(dia)
            recentes.append({'uuid': rodada.uuid, 'acertos': pontos, 'total': TAMANHO_RODADA,
                'data': rodada.concluida_em.isoformat() + 'Z', 'coroa': pontos == TAMANHO_RODADA})
    hoje = data_local(instante)
    inicio = hoje if hoje in dias else hoje - timedelta(days=1)
    frequencia = 0
    while inicio in dias:
        frequencia += 1
        inicio -= timedelta(days=1)
    return {**resumo_coroas(dias_coroa, instante), 'nivel': 1 + acertos // 10, 'acertos': acertos, 'respondidas': total,
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


def ativa(db, usuario_id, bloquear=False, janela=None):
    """Retorna a rodada DO DIA, inclusive concluída; respeita o histórico legado."""
    dia, inicio, fim = janela if janela is not None else limites_dia()
    consulta = db.query(JuridleDia).filter_by(usuario_id=usuario_id, dia=dia)
    registro = (consulta.with_for_update() if bloquear else consulta).first()
    if registro:
        rodada = db.get(JuridleRodada, registro.rodada_id)
        if inicio <= rodada.criada_em < fim:
            return rodada
    consulta = db.query(JuridleRodada).filter(JuridleRodada.usuario_id == usuario_id,
        JuridleRodada.criada_em >= inicio, JuridleRodada.criada_em < fim).order_by(JuridleRodada.criada_em.desc(), JuridleRodada.uuid.desc())
    return (consulta.with_for_update() if bloquear else consulta).first()


def iniciar(db, usuario_id):
    garantir_transacao(db)
    # A conta é o mutex estável no PostgreSQL/MySQL; BEGIN IMMEDIATE protege SQLite.
    usuario = db.query(Usuario).filter_by(uuid=usuario_id).with_for_update().first()
    if not usuario:
        raise HTTPException(404, 'Conta não encontrada.')
    instante = agora()
    janela = limites_dia(instante)
    dia, _, fim = janela
    rodada = ativa(db, usuario_id, bloquear=True, janela=janela)
    if rodada:
        return rodada
    # Uma questão sorteada fica reservada mesmo que a pessoa abandone a rodada.
    corte = (data_local(instante) - timedelta(days=29)).isoformat()
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
        perguntas_json=json.dumps(perguntas, ensure_ascii=False), respostas_json='[]', criada_em=instante, expira_em=fim)
    db.add(nova)
    db.flush()
    registro = db.get(JuridleDia, (usuario_id, dia))
    if registro:
        # Uma rodada legada iniciada antes das 05h pertence ao dia anterior.
        registro.rodada_id = nova.uuid
    else:
        db.add(JuridleDia(usuario_id=usuario_id, dia=dia, rodada_id=nova.uuid))
    db.add_all([JuridleQuestaoUso(usuario_id=usuario_id, questao_id=i, rodada_id=nova.uuid, dia=dia) for i in escolhidas])
    db.commit()
    return nova


def estado(db, usuario_id):
    instante = agora()
    janela = limites_dia(instante)
    rodada = ativa(db, usuario_id, janela=janela)
    _, _, fim = janela
    return {'rodada': serializar(rodada), 'progresso': progresso(db, usuario_id, instante),
        'disponivel': rodada is None, 'proximaRodadaEm': fim.isoformat() + 'Z',
        'servidorEm': instante.isoformat() + 'Z'}


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
    instante = agora()
    if rodada.concluida_em or rodada.expira_em <= instante or indice != rodada.respondidas or data_local(rodada.criada_em) != data_local(instante):
        raise HTTPException(409, 'Rodada encerrada ou pergunta fora de ordem. Atualize o jogo.')
    pergunta = json.loads(rodada.perguntas_json)[indice]
    resposta = {'opcao': opcao, 'acertou': opcao == pergunta['correta'], 'correta': pergunta['correta'],
        'explicacao': pergunta['explicacao'], 'exemplo': pergunta.get('exemplo', ''),
        'fonte': pergunta.get('fonte', {}), 'referencia': pergunta.get('referencia', ''), 'termoId': pergunta.get('termoId', '')}
    respostas.append(resposta)
    rodada.respostas_json = json.dumps(respostas, ensure_ascii=False)
    rodada.respondidas += 1
    if rodada.respondidas == TAMANHO_RODADA:
        rodada.concluida_em = instante
        rodada.ativa_chave = None
    db.commit()
    return rodada, resposta
