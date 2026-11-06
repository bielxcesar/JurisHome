"""Contratos de entrada. Texto nunca é interpretado como SQL, HTML ou comando."""
import re
import unicodedata
from typing import Annotated
from urllib.parse import urlsplit
from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator


def texto_seguro(valor):
    if not isinstance(valor, str):
        raise ValueError('Informe texto, sem objetos ou listas.')
    if any(unicodedata.category(c) in {'Cc', 'Cs', 'Cf'} and c not in '\n\r\t' for c in valor):
        raise ValueError('O texto contém caracteres de controle não permitidos.')
    return valor


def linha(valor, limite=180):
    valor = unicodedata.normalize('NFC', texto_seguro(valor)).strip()
    if len(valor) > limite or any(c in valor for c in '\n\r\t'):
        raise ValueError(f'Use uma única linha com até {limite} caracteres.')
    if re.search(r'<\s*/?\s*[A-Za-z!]', valor):
        raise ValueError('Este campo aceita texto simples, sem marcação HTML.')
    return valor


def nome_pessoa(valor, limite=100):
    valor = ' '.join(unicodedata.normalize('NFC', texto_seguro(valor)).strip().split(' '))
    if not 2 <= len(valor) <= limite or not all(c.isalpha() or c == ' ' for c in valor):
        raise ValueError(f'Use de 2 a {limite} caracteres, somente letras, acentos e espaços no nome.')
    return valor


def email_valido(valor):
    valor = texto_seguro(valor).strip().lower()
    if len(valor) > 150 or valor.count('@') != 1:
        raise ValueError('Informe um e-mail válido. Use até 150 caracteres.')
    local, dominio = valor.split('@')
    # Sintaxe usual; ponto, +, _ e hífen são válidos. Sem aspas/HTML/SQL em identificadores.
    if (not 1 <= len(local) <= 64 or not re.fullmatch(r'[a-z0-9._+\-]+', local) or local.startswith('.') or local.endswith('.') or '..' in local
        or len(dominio) > 253 or '.' not in dominio
        or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?', parte) for parte in dominio.split('.'))):
        raise ValueError('Informe um e-mail válido. Exemplo: nome@exemplo.com.')
    return valor


def nova_senha(valor):
    texto_seguro(valor)  # Não normalizar, aparar nem alterar a senha.
    if (not 8 <= len(valor) <= 25 or not any(c.isupper() for c in valor)
        or not re.search(r'[0-9]', valor) or not any(not c.isalnum() and not c.isspace() for c in valor)
        or any(c in valor for c in '\r\n\t') or len(valor.encode('utf-8')) > 72):
        raise ValueError('Use de 8 a 25 caracteres, com uma letra maiúscula, um número e um caractere especial (até 72 bytes).')
    return valor


def busca_segura(valor):
    valor = linha(valor, 80)
    if any(c in valor for c in '<>{}[]`\\'):
        raise ValueError('Use até 80 caracteres de texto na busca, sem HTML ou estruturas JSON.')
    return valor


def padrao_busca(valor):
    return '%' + valor.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def fonte_http(valor):
    if valor is None or valor == '':
        return valor
    valor = linha(valor, 2000)
    try:
        u = urlsplit(valor)
        if (u.scheme not in {'http','https'} or not u.hostname or u.username or u.password
            or any(c.isspace() or c in '<>"`\\' for c in valor)):
            raise ValueError()
        _ = u.port
    except ValueError:
        raise ValueError('Informe um link válido iniciado por http:// ou https://, sem credenciais.') from None
    return valor


def area_interesse(valor):
    from services.categorias import CATALOGO
    if valor not in CATALOGO:
        raise ValueError('Escolha uma das áreas de interesse disponíveis.')
    return valor


TextoBusca = Annotated[str, BeforeValidator(busca_segura)]


class ModeloSeguro(BaseModel):
    model_config = ConfigDict(extra='forbid', coerce_numbers_to_str=False)

    @field_validator('*', mode='after')
    @classmethod
    def sem_controles(cls, valor):
        if isinstance(valor, str):
            texto_seguro(valor)
        elif isinstance(valor, list):
            for item in valor:
                if isinstance(item, str):
                    texto_seguro(item)
        return valor
