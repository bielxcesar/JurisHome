import asyncio
import importlib.util
import json
import os
import sys
import unittest
from io import BytesIO
from http.cookies import SimpleCookie
from types import ModuleType
from unittest.mock import patch

os.environ.setdefault("JurisHome_senha", "segredo-de-teste-jurishome-com-mais-de-32-bytes")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from starlette.responses import Response

from auth.security import hash_senha, verificar_senha
from database import Base
from model import models  
from routes.auth import (
    AtualizacaoSenha,
    CadastroUsuario,
    Codigo2FA,
    Credenciais,
    SolicitacaoAnonimizacao,
    anonimizar_meus_dados,
    atualizar_senha,
    ativar_2fa_no_cadastro,
    cadastrar_usuario,
    consultar_ies_api_publica,
    consultar_instituicao_emec,
    login,
    validar_2fa,
)


class AutenticacaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def requisicao_http(self, metodo, caminho, dados=None, token=None, cookie=None):
        from main import app
        from database import get_db

        def banco_de_teste():
            sessao = self.Session()
            try:
                yield sessao
            finally:
                sessao.close()

        app.dependency_overrides[get_db] = banco_de_teste
        corpo = json.dumps(dados).encode("utf-8") if dados is not None else b""
        cabecalhos = [(b"host", b"testserver"), (b"accept", b"text/html")]
        if dados is not None:
            cabecalhos.append((b"content-type", b"application/json"))
        if token:
            cabecalhos.append((b"authorization", f"Bearer {token}".encode("ascii")))
        if cookie:
            cabecalhos.append((b"cookie", cookie.encode("ascii")))
        mensagens = []

        async def receber():
            return {"type": "http.request", "body": corpo, "more_body": False}

        async def enviar(mensagem):
            mensagens.append(mensagem)

        escopo = {
            "type": "http", "http_version": "1.1", "method": metodo,
            "scheme": "http", "path": caminho, "raw_path": caminho.encode("ascii"),
            "query_string": b"", "root_path": "", "headers": cabecalhos,
            "client": ("testclient", 1234), "server": ("testserver", 80),
        }
        try:
            asyncio.run(app(escopo, receber, enviar))
        finally:
            app.dependency_overrides.pop(get_db, None)
        inicio = next(mensagem for mensagem in mensagens if mensagem["type"] == "http.response.start")
        resposta = b"".join(mensagem.get("body", b"") for mensagem in mensagens if mensagem["type"] == "http.response.body")
        headers = [(chave.decode("latin1"), valor.decode("latin1")) for chave, valor in inicio["headers"]]
        return inicio["status"], headers, resposta

    def test_cadastro_guarda_senha_com_hash_e_exige_configuracao_2fa(self):
        resultado = asyncio.run(
            cadastrar_usuario(
                CadastroUsuario(
                    nome="Erick Santos",
                    email="erick@example.com",
                    senha="SenhaSegura123",
                    confirmar_senha="SenhaSegura123",
                    consentimento_lgpd=True,
                ),
                Response(),
                self.db,
            )
        )

        self.assertTrue(resultado["requer_configuracao_2fa"])
        self.assertTrue(resultado["configuracao_token"])
        self.assertTrue(resultado["qr_code"].startswith("data:image/png;base64,"))
        usuario = self.db.query(models.Usuario).filter_by(email="erick@example.com").one()
        self.assertNotEqual("SenhaSegura123", usuario.senha_hash)
        self.assertTrue(verificar_senha("SenhaSegura123", usuario.senha_hash))
        self.assertTrue(usuario.consentimento_lgpd)
        self.assertIsNotNone(usuario.data_consentimento)
        self.assertEqual("2.2", usuario.versao_termos)
        self.assertIsNone(usuario.universidade)
        self.assertEqual(
            1,
            self.db.query(models.LogAuditoria).filter_by(acao="cadastro", resultado="sucesso").count(),
        )

        login_resultado = login(Credenciais(email="erick@example.com", senha="SenhaSegura123"), Response(), self.db)
        self.assertTrue(login_resultado["requer_configuracao_2fa"])
        self.assertEqual(resultado["segredo"], login_resultado["segredo"])
        self.assertNotIn("access_token", login_resultado)

    def test_cadastro_exige_consentimento_lgpd(self):
        with self.assertRaises(Exception) as contexto:
            asyncio.run(
                cadastrar_usuario(
                    CadastroUsuario(
                        nome="Ana Silva",
                        email="ana@example.com",
                        senha="SenhaSegura123",
                        confirmar_senha="SenhaSegura123",
                        consentimento_lgpd=False,
                    ),
                    Response(),
                    self.db,
                )
            )
        self.assertEqual(422, contexto.exception.status_code)

    def test_cadastro_devolve_erro_legivel_para_email_e_confirmacao(self):
        dados = {
            "nome": "Pessoa Teste",
            "email": "sem-arroba.exemplo.com",
            "senha": "SenhaSegura123",
            "confirmar_senha": "SenhaSegura123",
            "consentimento_lgpd": True,
        }
        codigo, _, corpo = self.requisicao_http("POST", "/api/auth/cadastro", dados)
        self.assertEqual(422, codigo)
        erros = json.loads(corpo)["detail"]
        self.assertTrue(any("Informe um e-mail válido." in erro["msg"] for erro in erros))

        codigo, _, corpo = self.requisicao_http(
            "POST",
            "/api/auth/login",
            {"email": "sem-arroba", "senha": "SenhaSegura123"},
        )
        self.assertEqual(422, codigo)
        erros = json.loads(corpo)["detail"]
        self.assertTrue(any("Informe um e-mail válido." in erro["msg"] for erro in erros))

        dados["email"] = "teste@example.com"
        dados["confirmar_senha"] = "OutraSenha456"
        codigo, _, corpo = self.requisicao_http("POST", "/api/auth/cadastro", dados)
        self.assertEqual(422, codigo)
        erros = json.loads(corpo)["detail"]
        self.assertTrue(any("As senhas não conferem." in erro["msg"] for erro in erros))

    def test_bloqueia_conta_apos_cinco_senhas_invalidas(self):
        asyncio.run(
            cadastrar_usuario(
                CadastroUsuario(
                    nome="Bruno Lima",
                    email="bruno@example.com",
                    senha="SenhaSegura123",
                    confirmar_senha="SenhaSegura123",
                    consentimento_lgpd=True,
                ),
                Response(),
                self.db,
            )
        )

        for _ in range(5):
            with self.assertRaises(HTTPException) as contexto:
                login(Credenciais(email="bruno@example.com", senha="Invalida123"), Response(), self.db)
            self.assertEqual(401, contexto.exception.status_code)

        with self.assertRaises(HTTPException) as contexto:
            login(Credenciais(email="bruno@example.com", senha="SenhaSegura123"), Response(), self.db)
        self.assertEqual(423, contexto.exception.status_code)

    def test_troca_senha_exige_a_senha_atual_e_emite_nova_sessao(self):
        asyncio.run(
            cadastrar_usuario(
                CadastroUsuario(
                    nome="Clara Alves",
                    email="clara@example.com",
                    senha="SenhaSegura123",
                    confirmar_senha="SenhaSegura123",
                    consentimento_lgpd=True,
                ),
                Response(),
                self.db,
            )
        )
        usuario = self.db.query(models.Usuario).filter_by(email="clara@example.com").one()

        with self.assertRaises(HTTPException) as contexto:
            atualizar_senha(
                AtualizacaoSenha(senha_atual="Invalida123", nova_senha="NovaSenha456"),
                Response(),
                usuario,
                self.db,
            )
        self.assertEqual(400, contexto.exception.status_code)

        resultado = atualizar_senha(
            AtualizacaoSenha(senha_atual="SenhaSegura123", nova_senha="NovaSenha456"),
            Response(),
            usuario,
            self.db,
        )
        self.assertTrue(resultado["access_token"])
        self.assertTrue(verificar_senha("NovaSenha456", usuario.senha_hash))

    def test_anonimizacao_remove_dados_e_preserva_rastreabilidade(self):
        usuario = models.Usuario(
            uuid="usr-anonimizacao-001",
            nome="Titular Exemplo",
            email="titular@example.com",
            senha_hash=hash_senha("SenhaSegura123"),
            tipo_usuario=models.TipoUsuario.ESTUDANTE,
            universidade="Universidade Exemplo",
            especialidade_juridica="Direito Civil",
            totp_secret="segredo-cifrado-de-teste",
            is_2fa_enabled=True,
            consentimento_lgpd=True,
            data_consentimento=models.datetime.now(models.timezone.utc).replace(tzinfo=None),
            versao_termos="1.2",
        )
        atendimento = models.FeedbackAtendimento(
            id="fb-anonimizacao-001",
            protocolo="JH-20260925-0001",
            usuario_id=usuario.uuid,
            usuario_nome=usuario.nome,
            usuario_email=usuario.email,
            tipo="Dúvida",
            assunto="Assunto com dado pessoal",
            mensagem="Mensagem pessoal que deve ser removida.",
            avaliacao=4,
            status="Respondido",
            prioridade="Normal",
            respostas_json='[{"mensagem":"resposta reservada"}]',
            observacoes_json='[{"mensagem":"nota interna reservada"}]',
            historico_json='[{"id":"hist-1","tipo":"criacao","autor":"Titular Exemplo","descricao":"texto pessoal","criadoEm":"2026-09-25T10:00:00+00:00","visibilidade":"publica"}]',
        )
        legado = models.Feedback(
            mensagem="Mensagem antiga com dados pessoais.",
            tipo="Dúvida",
            usuario_id=usuario.uuid,
        )
        log_anterior = models.LogAuditoria(
            usuario_id=usuario.uuid,
            usuario_tipo="estudante",
            acao="perfil_alterado",
            recurso_tipo="usuario",
            recurso_id=usuario.uuid,
            resultado="sucesso",
            correlacao_id="correlacao-anterior-001",
            detalhes_json="{}",
        )
        self.db.add_all([usuario, atendimento, legado, log_anterior])
        self.db.commit()

        resposta = Response()
        resultado = anonimizar_meus_dados(
            SolicitacaoAnonimizacao(senha="SenhaSegura123", confirmacao="ANONIMIZAR"),
            resposta,
            usuario,
            self.db,
            self.db,
        )

        self.assertEqual("Usuário anonimizado", usuario.nome)
        self.assertTrue(usuario.email.startswith("anonimizado-"))
        self.assertIsNone(usuario.senha_hash)
        self.assertIsNone(usuario.totp_secret)
        self.assertIsNone(usuario.universidade)
        self.assertTrue(usuario.consentimento_lgpd)
        self.assertEqual("1.2", usuario.versao_termos)

        self.db.refresh(atendimento)
        self.assertEqual("JH-20260925-0001", atendimento.protocolo)
        self.assertEqual("Respondido", atendimento.status)
        self.assertEqual("Assunto anonimizado", atendimento.assunto)
        self.assertNotIn("Mensagem pessoal", atendimento.mensagem)
        self.assertEqual("[]", atendimento.respostas_json)
        self.assertEqual("[]", atendimento.observacoes_json)
        self.assertNotIn("Titular Exemplo", atendimento.historico_json)

        self.db.refresh(legado)
        self.assertNotIn("Mensagem antiga", legado.mensagem)

        log = self.db.query(models.LogAuditoria).filter_by(acao="dados_pessoais_anonimizados").one()
        self.assertEqual(usuario.uuid, log.usuario_id)
        self.assertEqual("sucesso", log.resultado)
        self.assertNotIn("titular@example.com", log.detalhes_json)
        self.assertNotIn("SenhaSegura123", log.detalhes_json)
        self.assertEqual(1, self.db.query(models.LogAuditoria).filter_by(acao="perfil_alterado").count())
        self.assertEqual(2, self.db.query(models.LogAuditoria).count())
        self.assertEqual(usuario.uuid, resultado["registro_preservado"]["usuario_id"])
        self.assertIn("jurishome_access_token", resposta.headers.get("set-cookie", ""))

    @unittest.skipUnless(importlib.util.find_spec("pyotp"), "pyotp não está instalado")
    def test_2fa_gera_segredo_cifrado_e_exige_codigo_no_login(self):
        import pyotp

        configuracao = asyncio.run(
            cadastrar_usuario(
                CadastroUsuario(
                    nome="Diego Nunes",
                    email="diego@example.com",
                    senha="SenhaSegura123",
                    confirmar_senha="SenhaSegura123",
                    consentimento_lgpd=True,
                ),
                Response(),
                self.db,
            )
        )
        usuario = self.db.query(models.Usuario).filter_by(email="diego@example.com").one()

        self.assertNotEqual(configuracao["segredo"], usuario.totp_secret)
        self.assertTrue(configuracao["qr_code"].startswith("data:image/png;base64,"))
        primeira_sessao = ativar_2fa_no_cadastro(
            Codigo2FA(
                desafio_token=configuracao["configuracao_token"],
                codigo=pyotp.TOTP(configuracao["segredo"]).now(),
            ),
            Response(),
            self.db,
        )
        self.assertTrue(primeira_sessao["access_token"])
        self.assertTrue(usuario.is_2fa_enabled)
        resposta_login = login(Credenciais(email="diego@example.com", senha="SenhaSegura123"), Response(), self.db)
        self.assertTrue(resposta_login["requer_2fa"])
        self.assertTrue(resposta_login["desafio_token"])
        sessao = validar_2fa(
            Codigo2FA(
                desafio_token=resposta_login["desafio_token"],
                codigo=pyotp.TOTP(configuracao["segredo"]).now(),
            ),
            Response(),
            self.db,
        )
        self.assertTrue(sessao["access_token"])

    @unittest.skipUnless(importlib.util.find_spec("pyotp"), "pyotp não está instalado")
    def test_bloqueia_brute_force_de_codigo_2fa_sem_resetar_no_login(self):
        import pyotp

        configuracao = asyncio.run(
            cadastrar_usuario(
                CadastroUsuario(
                    nome="Marina Costa",
                    email="marina@example.com",
                    senha="SenhaSegura123",
                    confirmar_senha="SenhaSegura123",
                    consentimento_lgpd=True,
                ),
                Response(),
                self.db,
            )
        )
        segredo = configuracao["segredo"]
        ativar_2fa_no_cadastro(
            Codigo2FA(
                desafio_token=configuracao["configuracao_token"],
                codigo=pyotp.TOTP(segredo).now(),
            ),
            Response(),
            self.db,
        )

        for _ in range(4):
            with self.assertRaises(HTTPException) as contexto:
                login(Credenciais(email="marina@example.com", senha="SenhaErrada123"), Response(), self.db)
            self.assertEqual(401, contexto.exception.status_code)

        desafio = login(Credenciais(email="marina@example.com", senha="SenhaSegura123"), Response(), self.db)
        self.assertEqual(4, self.db.query(models.Usuario).filter_by(email="marina@example.com").one().tentativas_login_falhas)
        totp = pyotp.TOTP(segredo)
        codigo_invalido = next(
            f"{codigo:06d}"
            for codigo in range(1_000_000)
            if not totp.verify(f"{codigo:06d}", valid_window=1)
        )
        with self.assertRaises(HTTPException) as contexto:
            validar_2fa(
                Codigo2FA(desafio_token=desafio["desafio_token"], codigo=codigo_invalido),
                Response(),
                self.db,
            )
        self.assertEqual(401, contexto.exception.status_code)

        with self.assertRaises(HTTPException) as contexto:
            login(Credenciais(email="marina@example.com", senha="SenhaSegura123"), Response(), self.db)
        self.assertEqual(423, contexto.exception.status_code)

    @unittest.skipUnless(importlib.util.find_spec("pyotp"), "pyotp não está instalado")
    def test_fluxo_http_cadastro_ativacao_saida_e_login_exigem_2fa(self):
        import pyotp

        codigo, headers, _ = self.requisicao_http("GET", "/home_usuario")
        self.assertEqual(303, codigo)
        self.assertIn(("location", "/?sessao=expirada"), headers)
        for rota in ("/exibir-mais", "/categorias"):
            with self.subTest(rota=rota):
                codigo, headers, _ = self.requisicao_http("GET", rota)
                self.assertEqual(303, codigo)
                self.assertIn(("location", "/?sessao=expirada"), headers)

        codigo, headers, corpo = self.requisicao_http(
            "POST", "/api/auth/cadastro",
            {"nome": "Teste Completo", "email": "completo@example.com", "senha": "SenhaSegura123", "confirmar_senha": "SenhaSegura123", "consentimento_lgpd": True},
        )
        cadastro = json.loads(corpo)
        self.assertEqual(201, codigo)
        self.assertTrue(cadastro["requer_configuracao_2fa"])
        self.assertTrue(cadastro["qr_code"].startswith("data:image/png;base64,"))
        self.assertFalse(any(chave == "set-cookie" for chave, _ in headers))

        codigo, _, _ = self.requisicao_http("GET", "/api/usuarios/me", token=cadastro["configuracao_token"])
        self.assertEqual(401, codigo)
        codigo, _, _ = self.requisicao_http("GET", "/home_usuario")
        self.assertEqual(303, codigo)

        codigo_invalido = "000000" if pyotp.TOTP(cadastro["segredo"]).now() != "000000" else "999999"
        codigo, _, _ = self.requisicao_http(
            "POST", "/api/auth/2fa/ativar-cadastro",
            {"desafio_token": cadastro["configuracao_token"], "codigo": codigo_invalido},
        )
        self.assertEqual(400, codigo)

        codigo, headers, corpo = self.requisicao_http(
            "POST", "/api/auth/2fa/ativar-cadastro",
            {"desafio_token": cadastro["configuracao_token"], "codigo": pyotp.TOTP(cadastro["segredo"]).now()},
        )
        self.assertEqual(200, codigo)
        self.assertTrue(json.loads(corpo)["access_token"])
        cookie_resposta = SimpleCookie()
        cookie_resposta.load(next(valor for chave, valor in headers if chave == "set-cookie"))
        cookie = f"jurishome_access_token={cookie_resposta['jurishome_access_token'].value}"
        codigo, _, _ = self.requisicao_http("GET", "/home_usuario", cookie=cookie)
        self.assertEqual(200, codigo)
        for rota, visao in (("/exibir-mais", "recentes"), ("/categorias", "categorias")):
            with self.subTest(rota=rota):
                codigo, _, corpo = self.requisicao_http("GET", rota, cookie=cookie)
                self.assertEqual(200, codigo)
                if isinstance(corpo, bytes):
                    corpo = corpo.decode("utf-8")
                self.assertIn(f'data-visao="{visao}"', corpo)

        codigo, _, _ = self.requisicao_http("POST", "/api/auth/logout", cookie=cookie)
        self.assertEqual(204, codigo)
        codigo, _, _ = self.requisicao_http("GET", "/home_usuario")
        self.assertEqual(303, codigo)

        codigo, headers, corpo = self.requisicao_http(
            "POST", "/api/auth/login", {"email": "completo@example.com", "senha": "SenhaSegura123"},
        )
        login_pendente = json.loads(corpo)
        self.assertEqual(200, codigo)
        self.assertTrue(login_pendente["requer_2fa"])
        self.assertFalse(any(chave == "set-cookie" for chave, _ in headers))
        codigo, _, _ = self.requisicao_http("GET", "/api/usuarios/me", token=login_pendente["desafio_token"])
        self.assertEqual(401, codigo)

        codigo, headers, corpo = self.requisicao_http(
            "POST", "/api/auth/2fa/validar",
            {"desafio_token": login_pendente["desafio_token"], "codigo": pyotp.TOTP(cadastro["segredo"]).now()},
        )
        self.assertEqual(200, codigo)
        self.assertTrue(json.loads(corpo)["access_token"])
        self.assertTrue(any(chave == "set-cookie" for chave, _ in headers))

    def test_favicon_nao_retorna_404(self):
        codigo, headers, _ = self.requisicao_http("GET", "/favicon.ico")
        self.assertEqual(307, codigo)
        self.assertIn(("location", "/static/images/logo.png"), headers)

    def test_consulta_emec_mapeia_o_retorno_da_biblioteca(self):
        pacote = ModuleType("emec_api")
        api = ModuleType("emec_api.api")
        cliente = ModuleType("emec_api.api.client")

        class InstituicaoFalsa:
            def __init__(self, codigo):
                self.codigo = codigo

            def parse(self):
                return None

            def get_full_json(self):
                return {
                    "nome_da_ies": "Universidade de Mogi das Cruzes",
                    "sigla": "UMC",
                    "situacao": "ATIVA",
                    "campus": [{"code": "1", "city": "Mogi das Cruzes", "uf": "SP"}],
                }

        cliente.Institution = InstituicaoFalsa
        with patch.dict(
            sys.modules,
            {"emec_api": pacote, "emec_api.api": api, "emec_api.api.client": cliente},
        ):
            resultado = consultar_instituicao_emec(123)

        self.assertEqual("Universidade de Mogi das Cruzes", resultado["nome"])
        self.assertEqual("UMC", resultado["sigla"])
        self.assertEqual("SP", resultado["campus"][0]["uf"])

    def test_consulta_emec_usa_fonte_publica_se_biblioteca_nao_importar(self):
        resultado_publico = {"nome": "Universidade pública"}
        with patch.dict(sys.modules, {"emec_api": None}):
            with patch("routes.auth.consultar_ies_api_publica", return_value=resultado_publico) as consulta:
                resultado = consultar_instituicao_emec(123)

        self.assertEqual(resultado_publico, resultado)
        consulta.assert_called_once_with(123)

    def test_consulta_api_externa_mapeia_codigo_emec(self):
        resposta_externa = {
            "features": [
                {
                    "attributes": {
                        "ies_cdg_mec_ies": 521,
                        "ies_nome": "UNIVERSIDADE DE MOGI DAS CRUZES",
                        "ies_sigla": "UMC",
                        "ies_campus": "Centro Cívico",
                        "ies_municipio": "MOGI DAS CRUZES",
                        "ies_uf": "SP",
                        "curso_situacao": "CADASTRADO",
                    }
                }
            ]
        }
        import json

        with patch("routes.auth.urlopen", return_value=BytesIO(json.dumps(resposta_externa).encode("utf-8"))):
            resultado = consultar_ies_api_publica(521)

        self.assertIsNotNone(resultado)
        self.assertEqual("UNIVERSIDADE DE MOGI DAS CRUZES", resultado["nome"])
        self.assertEqual("UMC", resultado["sigla"])
        self.assertEqual("SP", resultado["campus"][0]["uf"])

if __name__ == "__main__":
    unittest.main()
