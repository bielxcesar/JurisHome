import asyncio
import json
import unittest
from pydantic import ValidationError
from services.validacao import ModeloSeguro, email_valido, nome_pessoa, nova_senha, busca_segura, fonte_http
from services.entrada_http import EntradaSeguraMiddleware


class ValidacaoEntradaTests(unittest.TestCase):
    def test_nomes_acentuados_e_limites_sem_codigo_ou_numeros(self):
        self.assertEqual(nome_pessoa('  João da Silva  '), 'João da Silva')
        self.assertEqual(nome_pessoa('Jose\u0301'), 'José')
        for nome in ('Joao123', '<script>alert(1)</script>', '{"nome":"Ana"}', 'Ana\x00', 'Ana\nSilva', 'X'*101):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                nome_pessoa(nome)

    def test_email_sintaxe_usual_sem_aspas_controles_ou_injecao(self):
        self.assertEqual(email_valido(' Ana.Silva+teste@EXEMPLO.com '), 'ana.silva+teste@exemplo.com')
        for email in ("'or'1'='1@example.com", 'x<script>@example.com', 'x@example.com\nBcc:teste@example.com', 'a..b@example.com', 'a@-example.com', 'a'*65+'@example.com'):
            with self.subTest(email=email), self.assertRaises(ValueError):
                email_valido(email)

    def test_senha_oito_a_vinte_cinco_maiuscula_numero_simbolo(self):
        self.assertEqual(nova_senha('Abc!1234'), 'Abc!1234')
        self.assertEqual(nova_senha('Ab1!'+'x'*21), 'Ab1!'+'x'*21)
        for senha in ('Ab1!xxx', 'Ab1!'+'x'*22, 'abc!1234','Abcdefg!','Abcdefg1','Abc 1234','Abc!1234\n'):
            with self.subTest(senha=senha), self.assertRaises(ValueError):
                nova_senha(senha)

    def test_campos_texto_rejeitam_objetos_listas_extras_e_controles(self):
        class Entrada(ModeloSeguro):
            texto: str
        for dados in ({'texto':{'$ne':None}}, {'texto':['cmd']}, {'texto':123}, {'texto':'válido','root':True}, {'texto':'a\x00b'}):
            with self.subTest(dados=dados), self.assertRaises(ValidationError):
                Entrada.model_validate(dados)
        self.assertEqual(Entrada(texto='Uma frase; com "aspas", acentos e pontuação.').texto, 'Uma frase; com "aspas", acentos e pontuação.')

    def test_busca_curta_e_links_http_com_credenciais_bloqueadas(self):
        self.assertEqual(busca_segura("D'Ávila art. 5º § 1º"), "D'Ávila art. 5º § 1º")
        for busca in ('x'*81, '{"$ne":null}', '<img src=x>', 'a\x00b'):
            with self.assertRaises(ValueError):
                busca_segura(busca)
        self.assertEqual(fonte_http('https://exemplo.test/fonte?tema=civil'), 'https://exemplo.test/fonte?tema=civil')
        for url in ('javascript:alert(1)', 'data:text/html,<script>', 'https://usuario:senha@exemplo.test','https://exemplo.test/" onerror="x','https://exemplo.test:errado'):
            with self.assertRaises(ValueError):
                fonte_http(url)

    def requisicao(self, corpo=b'{}', query=b'', tamanho=None):
        respostas, invocacoes = [], []
        async def app(scope, receive, send):
            mensagem = await receive()
            invocacoes.append(mensagem.get('body'))
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'ok'})
        async def receber():
            return {'type':'http.request','body':corpo,'more_body':False}
        async def enviar(msg):
            respostas.append(msg)
        headers=[(b'content-type',b'application/json')]
        if tamanho:
            headers.append((b'content-length',str(tamanho).encode()))
        asyncio.run(EntradaSeguraMiddleware(app)({'type':'http','method':'POST','path':'/api/teste','query_string':query,'headers':headers},receber,enviar))
        return respostas[0]['status'], invocacoes

    def test_json_repetido_profundo_nao_padrao_e_corpo_grande(self):
        for corpo in (b'{"nome":"Ana","nome":"root"}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'[]', b'{"x":'+b'['*20+b'0'+b']'*20+b'}'):
            with self.subTest(corpo=corpo):
                status, chamadas = self.requisicao(corpo)
                self.assertEqual(status, 422)
                self.assertFalse(chamadas)
        self.assertEqual(self.requisicao(tamanho=9*1024*1024), (413, []))
        self.assertEqual(self.requisicao(query=b'busca=nome&busca=root'), (400, []))
        self.assertEqual(self.requisicao(query=b'x='+b'a'*4096), (414, []))
        self.assertEqual(self.requisicao(b'{"texto":"DROP TABLE usuarios;"}'), (200,[b'{"texto":"DROP TABLE usuarios;"}']))
        # É texto, nunca um comando. A defesa SQL ocorre no vínculo de parâmetros.

