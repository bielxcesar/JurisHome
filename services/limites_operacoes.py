"""Limites compartilhados entre processos, mantidos no mesmo banco da aplicação."""
import math
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from auth.sessions import garantir_transacao
from model.models import LimiteOperacao
from services.tentativas_auth import agora, chave, origem


def obter(db, tipo, identificador):
    garantir_transacao(db)
    digest = chave('operacao-' + tipo, str(identificador))
    registro = db.query(LimiteOperacao).filter_by(chave=digest).populate_existing().with_for_update().first()
    if registro is None:
        try:
            with db.begin_nested():
                registro = LimiteOperacao(chave=digest, insistencias=0)
                db.add(registro)
                db.flush()
        except IntegrityError:
            registro = db.query(LimiteOperacao).filter_by(chave=digest).populate_existing().with_for_update().one()
    return registro


def verificar_cadastro(db, request):
    ip = origem(request)
    if not ip:
        raise HTTPException(503, 'Não foi possível verificar a origem do cadastro. Tente novamente.')
    registro = obter(db, 'cadastro', ip)
    instante = agora()
    if registro.bloqueado_ate and registro.bloqueado_ate > instante:
        restante = math.ceil((registro.bloqueado_ate - instante).total_seconds())
        raise HTTPException(429, 'Limite de cadastros atingido. Aguarde uma hora antes de tentar novamente.', headers={'Retry-After': str(restante)})
    if registro.bloqueado_ate:
        registro.bloqueado_ate, registro.insistencias = None, 0
    if registro.proxima_em and registro.proxima_em > instante:
        registro.insistencias += 1
        if registro.insistencias >= 3:
            registro.bloqueado_ate = instante + timedelta(hours=1)
            restante = 3600
            mensagem = 'Foram detectadas tentativas repetidas. Novos cadastros estão bloqueados por uma hora.'
        else:
            restante = math.ceil((registro.proxima_em - instante).total_seconds())
            mensagem = f'Aguarde 5 minutos entre cadastros. Tentativas repetidas podem causar bloqueio de uma hora ({registro.insistencias}/3).'
        db.commit()
        raise HTTPException(429, mensagem, headers={'Retry-After': str(restante)})
    return registro


def verificar_materia(db, usuario_id):
    registro = obter(db, 'materia', usuario_id)
    instante = agora()
    if registro.proxima_em and registro.proxima_em > instante:
        restante = math.ceil((registro.proxima_em - instante).total_seconds())
        raise HTTPException(429, 'Aguarde 15 minutos entre envios de matérias.', headers={'Retry-After': str(restante)})
    return registro


def concluir(registro, minutos):
    registro.proxima_em = agora() + timedelta(minutes=minutos)
    registro.insistencias = 0
