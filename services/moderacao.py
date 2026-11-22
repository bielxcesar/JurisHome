"""Validação local de linguagem ofensiva e telefone em atendimentos."""
import re
import unicodedata

_PALAVRAS = {"viado", "viadu", "viadao", "viadinho", "porra", "caralho", "merda", "bosta",
             "puta", "putaria", "puto", "foder", "fodase", "fdp", "pqp", "vsf", "vtnc",
             "buceta", "cacete", "arrombado", "arrombada", "cu", "otario", "otaria"}
_TELEFONE = re.compile(r"(?<![\w])(?:\+?55[ .-]*)?(?:\(?\d{2}\)?[ .-]*)?(?:9[ .-]*)?\d{4}[ .-]*\d{4}(?![\w])")
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _normalizar(valor):
    texto = ''.join(c for c in unicodedata.normalize('NFKD', valor.casefold()) if not unicodedata.combining(c))
    texto = texto.translate(str.maketrans({'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t'}))
    return re.sub(r'(.)\1+', r'\1', texto)


_BLOQUEADAS = {_normalizar(palavra) for palavra in _PALAVRAS}


def validar_atendimento(texto: str) -> str:
    if any(_normalizar(token.group()) in _BLOQUEADAS for token in _TOKEN.finditer(texto)):
        raise ValueError('Reescreva o texto sem ofensas ou palavras inadequadas.')
    if _TELEFONE.search(texto):
        raise ValueError('Não informe números de telefone no atendimento. Use apenas os dados necessários para explicar o problema.')
    return texto


def proteger_texto_legado(texto):
    if not isinstance(texto, str):
        return texto
    texto = _TELEFONE.sub('[telefone ocultado]', texto)
    return _TOKEN.sub(lambda m: '[conteúdo ocultado]' if _normalizar(m.group()) in _BLOQUEADAS else m.group(), texto)


def proteger_eventos(eventos):
    return [{chave: proteger_texto_legado(valor) if chave in {'mensagem','descricao'} else valor
             for chave, valor in item.items()} if isinstance(item, dict) else proteger_texto_legado(item) for item in eventos]
