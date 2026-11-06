import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from model.models import Categoria, Conteudo, StatusConteudo, TipoFonte, TipoUsuario, Usuario
from routes.conteudos import buscar_conteudos
from services.categorias import CATALOGO
from services.conteudo_pedagogico import CONTEUDO_PEDAGOGICO, conteudo_categoria
from routes.paginas import pagina_categorias
from starlette.requests import Request


class ConteudosApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

        autor = Usuario(
            uuid="usuario-teste",
            nome="Estudante Teste",
            email="estudante@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ESTUDANTE,
        )
        categoria = Categoria(nome="Direito Civil")
        self.session.add_all([autor, categoria])
        self.session.flush()
        self.session.add(
            Conteudo(
                titulo="Conteúdo sem imagem",
                resumo_home="Resumo de teste",
                corpo_texto="Texto de teste",
                tipo_fonte=TipoFonte.DOUTRINA,
                status=StatusConteudo.APROVADO,
                categoria_id=categoria.uuid,
                autor_id=autor.uuid,
                imagem_miniatura="javascript:alert(1)",
                fonte_original="javascript:alert(1)",
            )
        )
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_api_rejeita_urls_de_imagem_e_fonte_com_esquema_perigoso(self):
        resposta = buscar_conteudos(db=self.session)

        self.assertEqual(1, len(resposta))
        self.assertIsNone(resposta[0]["imagem_miniatura"])
        self.assertIsNone(resposta[0]["fonte_original"])
        self.assertEqual("Doutrina", resposta[0]["fonte"])

    def test_api_expõe_fonte_original_https_quando_disponível(self):
        materia = self.session.query(Conteudo).one()
        materia.fonte_original = "https://g1.globo.com/direito/noticia"
        self.session.commit()

        resposta = buscar_conteudos(db=self.session)

        self.assertEqual("https://g1.globo.com/direito/noticia", resposta[0]["fonte_original"])

    def test_todas_as_categorias_têm_os_tres_pilares_e_fontes_oficiais(self):
        self.assertEqual(set(CATALOGO), set(CONTEUDO_PEDAGOGICO))
        for nome in CATALOGO:
            with self.subTest(categoria=nome):
                conteudo = conteudo_categoria(nome)
                self.assertTrue(conteudo["descricao"])
                self.assertTrue(conteudo["assuntos"])
                self.assertTrue(conteudo["cotidiano"])
                self.assertTrue(conteudo["curiosidade"]["texto"])
                self.assertTrue(conteudo["legislacoes"])
                for lei in conteudo["legislacoes"]:
                    self.assertTrue(lei["url"].startswith("https://www.planalto.gov.br/"))

    def test_alias_de_categoria_retorna_o_mesmo_conteudo(self):
        self.assertEqual(
            conteudo_categoria("Direito Penal"),
            conteudo_categoria("Penal"),
        )

    def test_pagina_de_categorias_entrega_as_quatro_secoes(self):
        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/categorias",
            "raw_path": b"/categorias",
            "query_string": b"categoria=Direito%20Civil",
            "headers": [],
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
        })
        estudante = self.session.query(Usuario).one()

        resposta = pagina_categorias(request, estudante, self.session)
        html = resposta.body.decode("utf-8")

        self.assertIn("CONHEÇA A ÁREA", html)
        self.assertIn("CURIOSIDADES JURÍDICAS", html)
        self.assertIn("LEGISLAÇÃO EM DESTAQUE", html)
        self.assertIn("Notícias jurídicas", html)
        self.assertIn("https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm", html)

    def test_home_tem_um_destino_direto_para_cada_categoria_do_catalogo(self):
        script = Path("static/js/home.js").read_text(encoding="utf-8")
        template = Path("templates/listagem_conteudos.html").read_text(encoding="utf-8")

        for nome in CATALOGO:
            with self.subTest(categoria=nome):
                self.assertIn(f"['{nome}'", script)
        self.assertIn("/categorias?categoria='+encodeURIComponent(c.nome)", script)
        self.assertIn("new URLSearchParams(location.search).get('categoria')", template)
