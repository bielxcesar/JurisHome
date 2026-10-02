import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from model.models import Categoria, Conteudo, StatusConteudo, TipoFonte, TipoUsuario, Usuario
from routes.conteudos import buscar_conteudos


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
                imagem_miniatura=None,
            )
        )
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_materia_sem_imagem_nao_retorna_url_inexistente(self):
        resposta = buscar_conteudos(db=self.session)

        self.assertEqual(1, len(resposta))
        self.assertIsNone(resposta[0]["imagem_miniatura"])
