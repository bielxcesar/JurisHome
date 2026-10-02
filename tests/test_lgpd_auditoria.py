import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from model.models import LogAuditoria, TipoUsuario
from routes.auditoria import listar_logs_auditoria
from services.auditoria import registrar_auditoria


class LgpdAuditoriaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.raiz = Path(__file__).resolve().parents[1]

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_documentos_sao_especificos_e_identificam_responsaveis(self):
        termos = (self.raiz / "templates" / "termos.html").read_text(encoding="utf-8")
        politica = (self.raiz / "templates" / "politica_privacidade.html").read_text(encoding="utf-8")

        self.assertIn("autenticação em duas etapas", termos)
        self.assertIn("canal de feedback", termos)
        self.assertIn("A pesquisa e os filtros", termos)
        self.assertIn("lista não é personalizada", termos)
        self.assertIn("não oferece, nesta versão, telas para gerenciar contas", termos)
        self.assertIn("PostgreSQL", politica)
        self.assertIn("não faz upload por integração Cloudinary", politica)
        self.assertNotIn("Render", politica)
        self.assertIn("Railway", politica)
        self.assertIn("e-MEC", politica)
        self.assertIn("CAU/BR", politica)
        self.assertIn("Configurações do usuário &gt; Privacidade e dados", politica)
        self.assertIn("12 meses", politica)
        self.assertIn("Erick Santos Barbosa", termos)
        self.assertIn("Pedro Henrique Harada Pecegueiro", politica)
        self.assertIn("Gabriel Agustín Fernández Alves", politica)
        self.assertIn("jurishome2026@gmail.com", politica)
        self.assertIn("pelo menos 18 anos", termos)
        self.assertIn("nem verifica essa informação", termos)
        self.assertIn("nem verifica a idade por outro meio", politica)
        self.assertIn("nem usa esse histórico para personalizar o acervo", politica)
        self.assertIn("não grava um histórico de pesquisas em suas tabelas", politica)
        self.assertIn("não roda automaticamente", politica.lower())
        self.assertNotIn("controladores conjuntos", termos)
        self.assertNotIn("recomendações podem considerar", termos)
        self.assertNotIn("Encarregado de Dados (DPO)", politica)
        self.assertIn("não implementa ferramentas próprias de análise", politica)
        self.assertIn("podem mudar depois da publicação", termos)
        self.assertIn("10. Cancelamento da conta", termos)
        self.assertNotIn("protótipo", termos.lower())
        self.assertNotIn("protótipo", politica.lower())
        self.assertIn("acadêmica", termos.lower())
        self.assertIn("SQLite", politica)
        self.assertNotIn("desenvolvimento e testes", politica.lower())
        self.assertNotIn("confirmação do e-mail cadastrado", politica)
        self.assertNotIn("dados sensíveis", termos.lower())
        self.assertNotIn("dados sensíveis", politica.lower())
        self.assertNotIn("PENDENTE DE VALIDAÇÃO", termos)
        self.assertNotIn("PENDENTE DE VALIDAÇÃO", politica)

        estilo = (self.raiz / "static" / "css" / "legal.css").read_text(encoding="utf-8")
        self.assertIn("position: fixed", estilo)
        self.assertIn("right: .85rem", estilo)

    def test_links_legais_estao_presentes_em_todas_as_telas(self):
        telas = (
            "index.html",
            "cadastro.html",
            "2fatores.html",
            "home_Usuario.html",
            "home_Admin.html",
            "confUsuario.html",
            "feedback-suporte.html",
            "admin-feedbacks.html",
            "glossario.html",
            "materia.html",
            "auditoria.html",
            "termos.html",
            "politica_privacidade.html",
        )
        for arquivo in telas:
            conteudo = (self.raiz / "templates" / arquivo).read_text(encoding="utf-8")
            with self.subTest(arquivo=arquivo):
                self.assertIn('{% include "_legal_links.html" %}', conteudo)
                self.assertIn("/static/css/legal.css?v=20260925-3", conteudo)

    def test_documentos_legais_preservam_o_contexto_de_retorno(self):
        for arquivo in ("termos.html", "politica_privacidade.html"):
            conteudo = (self.raiz / "templates" / arquivo).read_text(encoding="utf-8")
            with self.subTest(arquivo=arquivo):
                self.assertEqual(2, conteudo.count("data-legal-return"))
                self.assertIn('{% include "_legal_links.html" %}', conteudo)

        parcial = (self.raiz / "templates" / "_legal_links.html").read_text(encoding="utf-8")
        navegacao = (self.raiz / "static" / "js" / "legal-navigation.js").read_text(encoding="utf-8")
        self.assertIn("legal-navigation.js", parcial)
        self.assertIn("jurishome_legal_return", navegacao)
        self.assertIn("url.hash", navegacao)
        self.assertIn("url.origin !== window.location.origin", navegacao)

    def test_auditoria_reutiliza_navegacao_administrativa(self):
        auditoria = (self.raiz / "templates" / "auditoria.html").read_text(encoding="utf-8")
        feedbacks = (self.raiz / "templates" / "admin-feedbacks.html").read_text(encoding="utf-8")
        self.assertIn('/static/css/homeAdmin.css?v=20260925-1', auditoria)
        self.assertIn('class="navbar audit-navbar"', auditoria)
        self.assertIn('href="/admin/auditoria" class="nav-link active"', auditoria)
        self.assertIn('id="btn-perfil"', auditoria)
        self.assertIn('href="/exibir-mais" class="nav-link"><i class="fa-solid fa-square-plus" aria-hidden="true"></i> Exibir mais', auditoria)
        self.assertIn('href="/exibir-mais" class="nav-link"><i class="fa-solid fa-square-plus" aria-hidden="true"></i> Exibir mais', feedbacks)

    def test_navegacao_dos_perfis_nao_aponta_para_paginas_inexistentes(self):
        telas = {
            "home_Admin.html": ("/home_admin", "/configuracao", "/admin-feedbacks", "/admin/auditoria"),
            "home_Usuario.html": ("/home_usuario", "/configuracoes-usuario", "/glossario?origem=usuario"),
            "feedback-suporte.html": ("/home_usuario", "/configuracoes-usuario#feedback"),
            "materia.html": ("/exibir-mais", "/categorias"),
            "pesquisa.html": ("/exibir-mais", "/categorias"),
        }

        for arquivo, destinos in telas.items():
            conteudo = (self.raiz / "templates" / arquivo).read_text(encoding="utf-8")
            with self.subTest(arquivo=arquivo):
                self.assertNotIn("/static/pages/", conteudo)
                self.assertNotIn('href="#"', conteudo)
                for destino in destinos:
                    self.assertIn(f'href="{destino}"', conteudo)

    def test_home_aponta_para_telas_de_listagem_do_figma(self):
        usuario = (self.raiz / "templates" / "home_Usuario.html").read_text(encoding="utf-8")
        administrador = (self.raiz / "templates" / "home_Admin.html").read_text(encoding="utf-8")
        for conteudo in (usuario, administrador):
            self.assertIn('href="/exibir-mais"', conteudo)
            self.assertIn('href="/categorias"', conteudo)
            self.assertIn("Mais matérias", conteudo)
            self.assertNotIn("Você pode gostar", conteudo)
            self.assertNotIn('id="categorias-home"', conteudo)

        listagem = (self.raiz / "templates" / "listagem_conteudos.html").read_text(encoding="utf-8")
        script = (self.raiz / "static" / "js" / "listagemConteudos.js").read_text(encoding="utf-8")
        self.assertIn('id="ordem-materias"', listagem)
        self.assertIn('id="categoria-materias"', listagem)
        self.assertIn('className = "materia-linha"', script)
        self.assertIn('categoria.toLocaleLowerCase("pt-BR") === "direito trabalhista"', script)
        self.assertNotIn("materia.imagem_miniatura", script)
        for nome in ("homeUsuario.js", "homeAdmin.js"):
            script_home = (self.raiz / "static" / "js" / nome).read_text(encoding="utf-8")
            self.assertNotIn("aplicarImagem", script_home)

    def test_log_remove_campos_sensiveis_e_preserva_rastreabilidade(self):
        usuario = SimpleNamespace(uuid="usr-123", tipo_usuario=TipoUsuario.ADMINISTRADOR)
        registrar_auditoria(
            self.db,
            acao="feedback_status_alterado",
            recurso_tipo="feedback",
            recurso_id="fb-456",
            resultado="sucesso",
            usuario=usuario,
            detalhes={
                "novo_status": "Respondido",
                "senha": "nao-pode-aparecer",
                "token": "nao-pode-aparecer",
                "email_usuario": "nao-pode-aparecer@example.com",
                "mensagem": "conteudo do formulario",
            },
            commit=True,
        )

        registro = self.db.query(LogAuditoria).one()
        detalhes = json.loads(registro.detalhes_json)
        self.assertEqual("usr-123", registro.usuario_id)
        self.assertEqual("administrador", registro.usuario_tipo)
        self.assertEqual("fb-456", registro.recurso_id)
        self.assertEqual({"novo_status": "Respondido"}, detalhes)
        self.assertTrue(registro.correlacao_id)

    def test_listagem_administrativa_filtra_sem_alterar_logs(self):
        registrar_auditoria(
            self.db,
            acao="cadastro",
            recurso_tipo="usuario",
            recurso_id="usr-1",
            resultado="sucesso",
            commit=True,
        )
        registrar_auditoria(
            self.db,
            acao="autenticacao_credenciais",
            recurso_tipo="sessao",
            recurso_id="usr-1",
            resultado="falha",
            commit=True,
        )

        resposta = listar_logs_auditoria(
            busca="usr-1",
            acao=None,
            resultado="falha",
            limite=100,
            db=self.db,
        )
        self.assertEqual(1, resposta["totalExibido"])
        self.assertEqual("autenticacao_credenciais", resposta["itens"][0]["acao"])
        self.assertEqual(2, self.db.query(LogAuditoria).count())


if __name__ == "__main__":
    unittest.main()
