"""Limites persistentes e atômicos por origem e identificador, inclusive contas inexistentes."""
import hashlib
import hmac
import ipaddress
import math
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from auth.sessions import garantir_transacao
from model.models import LimiteAutenticacao

MAX_FALHAS = 6
ESPERA_SEGUNDOS = 8 * 60


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def chave(tipo, valor):
    from auth.security import SECRET_KEY
    # Não armazena IP nem e-mail em claro; separação de domínio para esta finalidade.
    return hmac.new(SECRET_KEY.encode(), ('auth-limite-v1:' + tipo + ':' + valor).encode(), hashlib.sha256).hexdigest()


def origem(request):
    if request is None or not request.client:
        return None
    host = request.client.host
    try:
        ip = ipaddress.ip_address(host)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return str(ip)
    except ValueError:
        return str(host)[:150]


def segundos(baldes, usuario=None):
    limites = [b.bloqueado_ate for b in baldes if b.bloqueado_ate]
    if usuario is not None and usuario.bloqueado_ate:
        limites.append(usuario.bloqueado_ate.replace(tzinfo=None))
    return max([0, *[math.ceil((limite - agora()).total_seconds()) for limite in limites]])


def exigir_liberado(baldes, usuario=None):
    restante = segundos(baldes, usuario)
    if restante:
        raise HTTPException(429, 'Muitas tentativas inválidas. Aguarde o tempo indicado antes de tentar novamente.',
            headers={'Retry-After': str(restante), 'Cache-Control': 'no-store'})


def preparar(db, request=None, email=None):
    garantir_transacao(db)
    pares = []
    ip = origem(request)
    if ip:
        pares.append(('origem', chave('origem', ip)))
    if email:
        pares.append(('conta', chave('conta', email.strip().lower())))
    baldes = []
    for tipo, digest in sorted(pares, key=lambda p: p[1]):
        b = db.query(LimiteAutenticacao).filter_by(chave=digest).populate_existing().with_for_update().first()
        if b is None:
            try:
                with db.begin_nested():
                    b = LimiteAutenticacao(chave=digest, tipo=tipo, falhas=0, ultima_em=agora())
                    db.add(b)
                    db.flush()
            except IntegrityError:
                b = db.query(LimiteAutenticacao).filter_by(chave=digest).populate_existing().with_for_update().one()
        # Tentar durante o bloqueio NÃO estende sua duração.
        if b.bloqueado_ate and b.bloqueado_ate <= agora():
            b.falhas, b.bloqueado_ate = 0, None
        elif not b.bloqueado_ate and b.ultima_em <= agora() - timedelta(seconds=ESPERA_SEGUNDOS):
            b.falhas = 0
        baldes.append(b)
    exigir_liberado(baldes)
    return baldes


def falhar(baldes):
    instante = agora()
    for b in baldes:
        b.falhas += 1
        b.ultima_em = instante
        if b.falhas >= MAX_FALHAS:
            b.bloqueado_ate = instante + timedelta(seconds=ESPERA_SEGUNDOS)


def concluir(baldes):
    # Somente autenticação COMPLETA (incluindo MFA) reinicia a sequência.
    for b in baldes:
        b.falhas, b.bloqueado_ate, b.ultima_em = 0, None, agora()


def estado_origem(db, request):
    ip = origem(request)
    b = db.get(LimiteAutenticacao, chave('origem', ip)) if ip else None
    espera = segundos([b] if b else [])
    return {'bloqueado': espera > 0, 'aguardeSegundos': espera}


def limpar_antigos(db):
    db.query(LimiteAutenticacao).filter(LimiteAutenticacao.ultima_em < agora() - timedelta(days=1)).delete(synchronize_session=False)
    db.commit()
