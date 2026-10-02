import asyncio
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

os.environ.setdefault("JurisHome_senha", "segredo-de-teste-jurishome-com-mais-de-32-bytes")

import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.responses import Response

import auth.security as security
from auth.security import (
    cifrar_segredo_2fa,
    criar_access_token,
    criar_token_2fa_pendente,
    hash_senha,
    verificar_senha,
)
from database import Base, get_db
from feedback_database import get_feedback_db
from model import models  
from model.models import TipoUsuario, Usuario
from routes.auth import (
    Codigo2FA,
    CadastroUsuario,
    Credenciais,
    NovaSenhaRecuperacao,
    alterar_senha_recuperada,
    cadastrar_usuario,
    iniciar_recuperacao_senha,
    validar_recuperacao_senha,
)


class TestesSeguranca(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.secret_patch = patch(
            "auth.security.SECRET_KEY",
            "security-test-signing-key-with-at-least-32-bytes",
        )
        cls.secret_patch.start()
        from main import app

        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.secret_patch.stop()
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _usuario(self, papel=TipoUsuario.ESTUDANTE, email=None):
        usuario = Usuario(
            uuid=str(uuid.uuid4()),
            nome="Conta de teste",
            email=email or f"{uuid.uuid4().hex}@example.test",
            senha_hash=hash_senha("SenhaSegura123"),
            tipo_usuario=papel,
            totp_secret=cifrar_segredo_2fa("JBSWY3DPEHPK3PXP"),
            is_2fa_enabled=True,
        )
        self.db.add(usuario)
        self.db.commit()
        return usuario

    def _banco_teste(self):
        sessao = self.Session()
        try:
            yield sessao
        finally:
            sessao.close()

    def _request(self, method, path, data=None, token=None, cookie=None):
        overrides_anteriores = self.app.dependency_overrides.copy()
        self.app.dependency_overrides[get_db] = self._banco_teste
        self.app.dependency_overrides[get_feedback_db] = self._banco_teste

        corpo = json.dumps(data).encode("utf-8") if data is not None else b""
        cabecalhos = [(b"host", b"testserver"), (b"accept", b"text/html")]
        if data is not None:
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

        url = urlsplit(path)
        escopo = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode("ascii"),
            "query_string": url.query.encode("ascii"),
            "root_path": "",
            "headers": cabecalhos,
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
        }
        try:
            asyncio.run(self.app(escopo, receber, enviar))
        finally:
            self.app.dependency_overrides.clear()
            self.app.dependency_overrides.update(overrides_anteriores)

        inicio = next(item for item in mensagens if item["type"] == "http.response.start")
        corpo_resposta = b"".join(
            item.get("body", b"")
            for item in mensagens
            if item["type"] == "http.response.body"
        )
        headers = {
            chave.decode("latin1").lower(): valor.decode("latin1")
            for chave, valor in inicio["headers"]
        }
        return inicio["status"], headers, corpo_resposta

    def test_rotas_administrativas_rejeitam_sessao_ausente(self):
        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
        ):
            with self.subTest(caminho=caminho):
                status, headers, _ = self._request("GET", caminho)
                self.assertEqual(303, status)
                self.assertEqual("/?sessao=expirada", headers["location"])

        for caminho in ("/api/admin/auditoria", "/api/admin/feedbacks"):
            with self.subTest(caminho=caminho):
                status, _, _ = self._request("GET", caminho)
                self.assertEqual(401, status)

    def test_estudante_autenticado_nao_acessa_telas_nem_apis_admin(self):
        estudante = self._usuario()
        token = criar_access_token(estudante)

        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
            "/api/admin/auditoria",
            "/api/admin/feedbacks",
        ):
            with self.subTest(caminho=caminho):
                status, _, corpo = self._request("GET", caminho, token=token)
                self.assertEqual(403, status, corpo.decode("utf-8", errors="replace"))

    def test_administrador_autenticado_acessa_rotas_admin(self):
        administrador = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(administrador)

        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
            "/api/admin/auditoria",
            "/api/admin/feedbacks",
        ):
            with self.subTest(caminho=caminho):
                status, _, corpo = self._request("GET", caminho, token=token)
                self.assertEqual(200, status, corpo.decode("utf-8", errors="replace"))

    def test_token_adulterado_expirado_e_de_2fa_nao_autentica(self):
        usuario = self._usuario()
        agora = datetime.now(timezone.utc)
        tokens_invalidos = (
            "nao.e.um.jwt",
            criar_token_2fa_pendente(usuario),
            jwt.encode(
                {
                    "sub": usuario.uuid,
                    "tipo": "acesso",
                    "iat": agora - timedelta(hours=2),
                    "exp": agora - timedelta(hours=1),
                },
                security.SECRET_KEY,
                algorithm="HS256",
            ),
            jwt.encode(
                {
                    "sub": usuario.uuid,
                    "tipo": "acesso",
                    "iat": agora,
                    "exp": agora + timedelta(minutes=5),
                },
                "another-security-test-key-with-at-least-32-bytes",
                algorithm="HS256",
            ),
        )

        for token in tokens_invalidos:
            with self.subTest(token=token[:12]):
                status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
                self.assertEqual(401, status)

    def test_cookie_de_sessao_e_http_only_com_same_site_e_secure_configuravel(self):
        from routes.auth import _salvar_cookie_de_sessao

        resposta = Response()
        with patch.dict(os.environ, {"COOKIE_SECURE": "true"}):
            _salvar_cookie_de_sessao(resposta, "token-teste")

        cookie = resposta.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("secure", cookie)
        self.assertIn("path=/", cookie)
        self.assertIn("max-age=1800", cookie)

    def test_respostas_tem_headers_basicos_e_endpoints_auth_nao_sao_cacheaveis(self):
        status, headers, _ = self._request("GET", "/")
        self.assertEqual(200, status)
        self.assertEqual("nosniff", headers["x-content-type-options"])
        self.assertEqual("DENY", headers["x-frame-options"])
        self.assertEqual("strict-origin-when-cross-origin", headers["referrer-policy"])
        self.assertEqual("camera=(), geolocation=(), microphone=()", headers["permissions-policy"])

        status, headers, _ = self._request(
            "POST",
            "/api/auth/recuperacao/iniciar",
            {"email": "pessoa@example.test"},
        )
        self.assertEqual(200, status)
        self.assertEqual("no-store, max-age=0", headers["cache-control"])
        self.assertEqual("no-cache", headers["pragma"])

    def test_senha_nao_e_armazenada_em_texto_e_limite_bcrypt_em_bytes(self):
        senha = "SenhaSegura123"
        senha_hash = hash_senha(senha)
        self.assertNotEqual(senha, senha_hash)
        self.assertTrue(verificar_senha(senha, senha_hash))
        self.assertFalse(verificar_senha("senha incorreta", senha_hash))
        self.assertFalse(verificar_senha("a" * 73, senha_hash))

    def test_cadastro_publico_nao_permite_autopromocao_para_admin(self):
        dados = CadastroUsuario.model_validate(
            {
                "nome": "Conta sem privilégios",
                "email": "autopromocao@example.test",
                "senha": "SenhaSegura123",
                "confirmar_senha": "SenhaSegura123",
                "consentimento_lgpd": True,
                "tipo_usuario": "administrador",
                "e_root_admin": True,
            }
        )
        asyncio.run(cadastrar_usuario(dados, Response(), self.db))
        usuario = self.db.query(Usuario).filter_by(email=dados.email).one()
        self.assertEqual(TipoUsuario.ESTUDANTE, usuario.tipo_usuario)
        self.assertFalse(usuario.e_root_admin)

    def test_login_nao_revela_se_email_existe(self):
        self._usuario(email="existente@example.test")
        respostas = []
        for email in ("inexistente@example.test", "existente@example.test"):
            status, _, corpo = self._request(
                "POST",
                "/api/auth/login",
                {"email": email, "senha": "SenhaErrada123"},
            )
            respostas.append((status, json.loads(corpo)["detail"]))
        self.assertEqual(respostas[0], respostas[1])

    def test_busca_de_conteudo_nao_interpreta_entrada_como_sql(self):
        from model.models import Categoria, Conteudo, StatusConteudo, TipoFonte

        autor = self._usuario()
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Teste SQL")
        self.db.add(categoria)
        self.db.flush()
        self.db.add(
            Conteudo(
                titulo="Conteúdo público aprovado",
                resumo_home="Resumo de teste suficientemente longo.",
                corpo_texto="Texto de teste.",
                tipo_fonte=TipoFonte.ACORDAO,
                status=StatusConteudo.APROVADO,
                categoria_id=categoria.uuid,
                autor_id=autor.uuid,
            )
        )
        self.db.add(
            Conteudo(
                titulo="Conteúdo ainda não aprovado",
                resumo_home="Este conteúdo deve permanecer privado.",
                corpo_texto="Texto reservado.",
                tipo_fonte=TipoFonte.ACORDAO,
                status=StatusConteudo.EM_ANALISE,
                categoria_id=categoria.uuid,
                autor_id=autor.uuid,
            )
        )
        self.db.commit()

        status, _, corpo = self._request("GET", "/api/conteudos")
        self.assertEqual(200, status)
        publico = json.loads(corpo)
        self.assertEqual(["Conteúdo público aprovado"], [item["titulo"] for item in publico])

        injecao = urlencode({"busca": "' OR 1=1 --"})
        status, _, corpo = self._request("GET", f"/api/conteudos?{injecao}")
        self.assertEqual(200, status)
        self.assertEqual([], json.loads(corpo))

    def test_recuperacao_exige_email_e_codigo_totp_e_token_nao_pode_ser_reutilizado(self):
        import pyotp

        from routes.auth import decifrar_segredo_2fa

        segredo = pyotp.random_base32()
        usuario = Usuario(
            uuid=str(uuid.uuid4()),
            nome="Conta para recuperação",
            email="recuperacao@example.test",
            senha_hash=hash_senha("SenhaSegura123"),
            tipo_usuario=TipoUsuario.ESTUDANTE,
            totp_secret=cifrar_segredo_2fa(segredo),
            is_2fa_enabled=True,
        )
        self.db.add(usuario)
        self.db.commit()

        from routes.auth import ConfirmacaoRecuperacaoSenha, InicioRecuperacaoSenha

        desafio = iniciar_recuperacao_senha(InicioRecuperacaoSenha(email=usuario.email))["desafio_token"]
        with self.assertRaises(Exception) as contexto:
            validar_recuperacao_senha(
                ConfirmacaoRecuperacaoSenha(
                    email=usuario.email,
                    desafio_token=desafio,
                    codigo="000000" if pyotp.TOTP(segredo).now() != "000000" else "999999",
                ),
                self.db,
            )
        self.assertEqual(401, contexto.exception.status_code)

        codigo = pyotp.TOTP(decifrar_segredo_2fa(usuario.totp_secret)).now()
        autorizado = validar_recuperacao_senha(
            ConfirmacaoRecuperacaoSenha(
                email=usuario.email,
                desafio_token=desafio,
                codigo=codigo,
            ),
            self.db,
        )
        dados_nova_senha = NovaSenhaRecuperacao(
            token_redefinicao=autorizado["token_redefinicao"],
            nova_senha="NovaSenha!456",
            confirmar_senha="NovaSenha!456",
        )
        self.assertIn("sucesso", alterar_senha_recuperada(dados_nova_senha, self.db)["mensagem"].lower())
        self.assertTrue(verificar_senha("NovaSenha!456", usuario.senha_hash))

        with self.assertRaises(Exception) as contexto:
            alterar_senha_recuperada(dados_nova_senha, self.db)
        self.assertEqual(401, contexto.exception.status_code)


if __name__ == "__main__":
    unittest.main()
