"""Limites antes da validação: tamanho, query ambígua e JSON não padrão."""
import json
from urllib.parse import parse_qsl
from starlette.responses import JSONResponse


def objeto_sem_duplicatas(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError('Chaves JSON duplicadas.')
        resultado[chave] = valor
    return resultado


def estrutura_limitada(valor, profundidade=0):
    if profundidade > 12:
        raise ValueError('JSON com aninhamento excessivo.')
    if isinstance(valor, (list, dict)):
        if len(valor) > 1000:
            raise ValueError('JSON com itens em excesso.')
        for item in (valor.values() if isinstance(valor, dict) else valor):
            estrutura_limitada(item, profundidade+1)


class EntradaSeguraMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def erro(codigo, mensagem):
            resposta = JSONResponse({'detail': mensagem}, status_code=codigo,
                headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})
            await resposta(scope, receive, send)

        query = scope.get('query_string', b'')
        if len(query) > 4096:
            return await erro(414, 'O endereço contém parâmetros longos demais.')
        try:
            pares = parse_qsl(query.decode('utf-8'), keep_blank_values=True, max_num_fields=30)
            if len({p[0] for p in pares}) != len(pares):
                return await erro(400, 'Envie cada parâmetro de consulta apenas uma vez.')
        except (UnicodeError, ValueError):
            return await erro(400, 'Parâmetros de consulta inválidos.')
        if scope['method'] not in {'POST','PUT','PATCH','DELETE'}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        tipo = headers.get(b'content-type', b'').split(b';')[0].strip().lower()
        limite = 8*1024*1024 if tipo == b'application/json' else 3*1024*1024
        try:
            if int(headers.get(b'content-length', b'0')) > limite:
                return await erro(413, 'O envio ultrapassa o tamanho permitido.')
        except ValueError:
            return await erro(400, 'Tamanho do envio inválido.')
        if tipo != b'application/json':
            # Multipart é validado pelos formulários; também limitado no streaming.
            total = 0
            async def limitado():
                nonlocal total
                mensagem = await receive()
                total += len(mensagem.get('body', b''))
                if total > limite:
                    from starlette.exceptions import HTTPException
                    raise HTTPException(413, 'O envio ultrapassa o tamanho permitido.')
                return mensagem
            return await self.app(scope, limitado, send)
        partes, total = [], 0
        while True:
            mensagem = await receive()
            if mensagem['type'] == 'http.disconnect':
                return
            corpo = mensagem.get('body', b'')
            total += len(corpo)
            if total > limite:
                return await erro(413, 'O envio ultrapassa o tamanho permitido.')
            partes.append(corpo)
            if not mensagem.get('more_body', False):
                break
        bruto = b''.join(partes)
        try:
            def invalido(_):
                raise ValueError('Número JSON não padrão.')
            dados = json.loads(bruto.decode('utf-8'), object_pairs_hook=objeto_sem_duplicatas, parse_constant=invalido)
            if not isinstance(dados, dict):
                raise ValueError('Esperado objeto JSON.')
            estrutura_limitada(dados)
        except (ValueError, UnicodeError, RecursionError):
            return await erro(422, 'JSON inválido: envie um objeto simples, sem chaves repetidas ou aninhamento excessivo.')
        entregue = False
        async def repetir():
            nonlocal entregue
            if not entregue:
                entregue = True
                return {'type':'http.request', 'body':bruto, 'more_body':False}
            return await receive()
        return await self.app(scope, repetir, send)
