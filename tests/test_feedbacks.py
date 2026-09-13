import unittest

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from routes.feedbacks import (
    AlteracaoStatus,
    FeedbackCriacao,
    MensagemAdministrativa,
    alterar_status,
    criar_feedback,
    listar_feedbacks,
    responder_feedback,
)


class FeedbackApiTests(unittest.TestCase):
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

    def test_feedback_do_usuario_aparece_para_o_admin(self):
        criado = criar_feedback(
            FeedbackCriacao(
                tipo="Sugestão",
                assunto="Melhoria na pesquisa",
                mensagem="Seria útil filtrar os resultados por tribunal.",
                avaliacao=5,
            ),
            self.db,
        )
        self.assertTrue(criado["protocolo"].startswith("JH-"))
        self.assertNotIn("observacoesInternas", criado)

        registros = listar_feedbacks(self.db)
        self.assertEqual(1, len(registros))
        self.assertEqual(criado["id"], registros[0]["id"])
        self.assertEqual("Melhoria na pesquisa", registros[0]["assunto"])

    def test_admin_atualiza_e_responde_feedback(self):
        criado = criar_feedback(
            FeedbackCriacao(
                tipo="Dúvida",
                assunto="Dúvida sobre acesso",
                mensagem="Como posso acessar o glossário jurídico?",
            ),
            self.db,
        )

        atualizado = alterar_status(
            criado["id"],
            AlteracaoStatus(status="Em análise"),
            self.db,
        )
        self.assertEqual("Em análise", atualizado["status"])

        respondido = responder_feedback(
            criado["id"],
            MensagemAdministrativa(mensagem="O glossário está disponível no menu superior."),
            self.db,
        )
        self.assertEqual("Respondido", respondido["status"])
        self.assertEqual(1, len(respondido["respostas"]))

    def test_api_rejeita_dados_invalidos(self):
        with self.assertRaises(ValidationError):
            FeedbackCriacao(tipo="Inexistente", assunto="Oi", mensagem="Curta")

        with self.assertRaises(ValidationError):
            FeedbackCriacao(tipo="Dúvida", assunto="     ", mensagem="          ")


if __name__ == "__main__":
    unittest.main()
