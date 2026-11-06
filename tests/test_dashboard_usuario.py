import unittest
from datetime import date, timedelta

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from database import Base
from model.models import (
    Categoria,
    CategoriaAcesso,
    Conteudo,
    ConteudoLeitura,
    StatusConteudo,
    TipoFonte,
    TipoUsuario,
    Usuario,
)
from routes.paginas import (
    RegistroAcessoCategoria,
    api_dashboard_perfil,
    api_registrar_acesso_categoria,
    pagina_perfil,
)
from services.dashboard_usuario import obter_dashboard_estudos, registrar_acesso_categoria


class DashboardUsuarioTests(unittest.TestCase):
    @staticmethod
    def _requisicao_perfil():
        return Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/perfil",
            "raw_path": b"/perfil",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 1234),
            "server": ("testserver", 80),
        })

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.hoje = date(2026, 11, 2)

        estudante = Usuario(
            uuid="estudante-dashboard",
            nome="Estudante Dashboard",
            email="dashboard@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ESTUDANTE,
        )
        self.estudante = estudante
        outro_estudante = Usuario(
            uuid="outro-estudante-dashboard",
            nome="Outro Estudante",
            email="outro-dashboard@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ESTUDANTE,
        )
        civil = Categoria(nome="Direito Civil")
        penal = Categoria(nome="Direito Penal")
        self.categorias = {"Direito Civil": civil, "Direito Penal": penal}
        self.session.add_all([estudante, outro_estudante, civil, penal])
        self.session.flush()

        materias = {}
        for identificador, categoria in (("materia-civil-1", civil), ("materia-civil-2", civil), ("materia-penal-1", penal)):
            materias[identificador] = Conteudo(
                uuid=identificador,
                titulo=f"Título {identificador}",
                resumo_home="Resumo de teste",
                corpo_texto="Conteúdo de teste",
                tipo_fonte=TipoFonte.DOUTRINA,
                status=StatusConteudo.APROVADO,
                categoria_id=categoria.uuid,
                autor_id=estudante.uuid,
            )
        self.session.add_all(materias.values())
        self.session.flush()

        ontem = (self.hoje - timedelta(days=1)).isoformat()
        inicio_periodo = (self.hoje - timedelta(days=6)).isoformat()
        fora_periodo = (self.hoje - timedelta(days=7)).isoformat()
        self.session.add_all([
            ConteudoLeitura(usuario_id=estudante.uuid, conteudo_id="materia-civil-1", dia=self.hoje.isoformat()),
            ConteudoLeitura(usuario_id=estudante.uuid, conteudo_id="materia-civil-1", dia=ontem),
            ConteudoLeitura(usuario_id=estudante.uuid, conteudo_id="materia-civil-2", dia=inicio_periodo),
            ConteudoLeitura(usuario_id=estudante.uuid, conteudo_id="materia-penal-1", dia=fora_periodo),
            ConteudoLeitura(usuario_id=outro_estudante.uuid, conteudo_id="materia-penal-1", dia=self.hoje.isoformat()),
            CategoriaAcesso(usuario_id=estudante.uuid, categoria_id=civil.uuid, dia="2026-10-31"),
            CategoriaAcesso(usuario_id=estudante.uuid, categoria_id=civil.uuid, dia="2026-11-01"),
            CategoriaAcesso(usuario_id=estudante.uuid, categoria_id=civil.uuid, dia="2026-11-02"),
            CategoriaAcesso(usuario_id=estudante.uuid, categoria_id=penal.uuid, dia="2026-11-02"),
            CategoriaAcesso(usuario_id=outro_estudante.uuid, categoria_id=civil.uuid, dia="2026-11-02"),
        ])

        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_indicador_conta_materias_distintas(self):
        dados = obter_dashboard_estudos(self.session, "estudante-dashboard", self.hoje)

        self.assertEqual({"materias_total": 3}, dados["indicadores"])
        self.assertNotIn("rodadas_juridle_concluidas", dados["indicadores"])

    def test_categorias_mostram_acessos_do_mes_atual(self):
        dados = obter_dashboard_estudos(self.session, "estudante-dashboard", self.hoje)
        categorias = {item["categoria"]: item["quantidade"] for item in dados["categorias_mes"]}

        self.assertEqual({"Direito Civil": 2, "Direito Penal": 1}, categorias)
        self.assertEqual({"inicio": "2026-11-01", "fim": "2026-11-02"}, dados["periodo"])
        self.assertEqual(
            0,
            self.session.query(CategoriaAcesso)
            .filter_by(usuario_id=self.estudante.uuid, dia="2026-10-31")
            .count(),
        )

    def test_acesso_a_categoria_conta_uma_vez_por_usuario_categoria_e_dia(self):
        amanha = self.hoje + timedelta(days=1)
        civil_id = self.categorias["Direito Civil"].uuid
        penal_id = self.categorias["Direito Penal"].uuid

        self.assertTrue(registrar_acesso_categoria(self.session, self.estudante.uuid, civil_id, amanha))
        self.assertFalse(registrar_acesso_categoria(self.session, self.estudante.uuid, civil_id, amanha))
        self.assertTrue(registrar_acesso_categoria(self.session, self.estudante.uuid, penal_id, amanha))
        self.assertEqual(
            2,
            self.session.query(CategoriaAcesso)
            .filter_by(usuario_id=self.estudante.uuid, dia=amanha.isoformat())
            .count(),
        )

    def test_dashboard_nao_retorna_dados_de_outro_usuario(self):
        dados = obter_dashboard_estudos(self.session, "outro-estudante-dashboard", self.hoje)

        self.assertEqual({"materias_total": 1}, dados["indicadores"])
        self.assertEqual(
            [{"categoria": "Direito Civil", "quantidade": 1}],
            dados["categorias_mes"],
        )

    def test_rota_retorna_resumo_sem_cache_para_estudante(self):
        resposta = Response()
        dados = api_dashboard_perfil(resposta, self.session, self.estudante)

        self.assertEqual("no-store, max-age=0", resposta.headers["Cache-Control"])
        self.assertEqual(3, dados["indicadores"]["materias_total"])
        self.assertEqual(2, len(dados["categorias_mes"]))

    def test_rota_registra_categoria_e_nao_fica_disponivel_para_admin(self):
        resposta = Response()
        resultado = api_registrar_acesso_categoria(
            RegistroAcessoCategoria(categoria="Direito Civil"),
            resposta,
            self.session,
            self.estudante,
        )
        self.assertIsInstance(resultado["registrado"], bool)
        self.assertEqual("no-store, max-age=0", resposta.headers["Cache-Control"])

        administrador = Usuario(
            uuid="admin-dashboard",
            nome="Administrador",
            email="admin-dashboard@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ADMINISTRADOR,
        )
        with self.assertRaises(HTTPException) as contexto:
            api_registrar_acesso_categoria(
                RegistroAcessoCategoria(categoria="Direito Civil"),
                Response(),
                self.session,
                administrador,
            )
        self.assertEqual(404, contexto.exception.status_code)

    def test_rota_da_dashboard_nao_e_disponivel_para_administrador(self):
        administrador = Usuario(
            uuid="admin-dashboard",
            nome="Administrador",
            email="admin-dashboard@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ADMINISTRADOR,
        )
        with self.assertRaises(HTTPException) as contexto:
            api_dashboard_perfil(Response(), self.session, administrador)
        self.assertEqual(404, contexto.exception.status_code)

    def test_dashboard_aparece_dentro_do_perfil_do_estudante(self):
        resposta = pagina_perfil(self._requisicao_perfil(), self.estudante)
        html = resposta.body.decode("utf-8")

        self.assertIn('id="perfil-dashboard"', html)
        self.assertIn("perfil-dashboard.js?v=20261102-3", html)
        self.assertIn("Matérias consultadas no total", html)
        self.assertIn("Seu histórico de estudos", html)
        self.assertIn("Cada matéria é contada uma vez", html)
        self.assertIn("Categorias mais acessadas no mês", html)
        self.assertIn("dashboard-categorias-barras", html)
        self.assertNotIn("Partidas do JuridLE", html)
        self.assertNotIn("dashboard-categorias-pizza", html)
        self.assertNotIn("dashboard-leituras-diarias", html)

    def test_dashboard_nao_aparece_no_perfil_administrativo(self):
        administrador = Usuario(
            uuid="admin-perfil-dashboard",
            nome="Administrador",
            email="admin-perfil-dashboard@example.invalid",
            senha_hash="hash-de-teste",
            tipo_usuario=TipoUsuario.ADMINISTRADOR,
        )

        resposta = pagina_perfil(self._requisicao_perfil(), administrador)
        html = resposta.body.decode("utf-8")

        self.assertNotIn('id="perfil-dashboard"', html)
        self.assertNotIn("perfil-dashboard.js", html)
        self.assertNotIn("perfil-dashboard.css", html)


if __name__ == "__main__":
    unittest.main()
