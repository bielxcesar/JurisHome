import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from model.models import FeedbackAtendimento, LogAuditoria, TipoUsuario, Usuario
from services.retencao import aplicar_retencao


class RetencaoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.agora = datetime(2026, 9, 25, tzinfo=timezone.utc)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _feedback(self, identificador, status, dias, email="pessoa@example.com"):
        return FeedbackAtendimento(
            id=identificador,
            protocolo=f"JH-{identificador}",
            usuario_id="usr-1",
            usuario_nome="Pessoa Exemplo",
            usuario_email=email,
            tipo="Dúvida",
            assunto="Assunto identificável",
            mensagem="Mensagem identificável do titular.",
            status=status,
            prioridade="Normal",
            respostas_json='[{"mensagem":"resposta"}]',
            observacoes_json='[{"mensagem":"nota"}]',
            historico_json="[]",
            criado_em=self.agora - timedelta(days=dias + 1),
            atualizado_em=self.agora - timedelta(days=dias),
        )

    def _log(self, acao, dias):
        return LogAuditoria(
            usuario_id="usr-1",
            usuario_tipo="estudante",
            acao=acao,
            recurso_tipo="usuario",
            recurso_id="usr-1",
            resultado="sucesso",
            correlacao_id=f"corr-{acao}-{dias}",
            detalhes_json='{"campo":"valor"}',
            criado_em=self.agora - timedelta(days=dias),
        )

    def test_simulacao_nao_altera_dados(self):
        antigo = self._feedback("old", "Resolvido", 181)
        self.db.add(antigo)
        self.db.commit()
        resultado = aplicar_retencao(self.db, self.db, agora=self.agora, executar=False)
        self.assertEqual(1, resultado["feedbacks_para_anonimizar"])
        self.assertEqual("Pessoa Exemplo", antigo.usuario_nome)
        self.assertEqual("Mensagem identificável do titular.", antigo.mensagem)

    def test_aplicacao_anonimiza_e_minimiza_sem_apagar_rastreabilidade(self):
        antigo = self._feedback("old", "Arquivado", 181)
        recente = self._feedback("new", "Recebido", 400)
        log_antigo = self._log("perfil_alterado", 366)
        log_recente = self._log("cadastro", 100)
        incidente_retido = self._log("incidente_detectado", 730)
        incidente_expirado = self._log("incidente_encerrado", 5 * 365 + 1)
        usuario = Usuario(
            uuid="usr-anonimo",
            nome="Usuário anonimizado",
            email="anonimizado-usr@invalid.local",
            tipo_usuario=TipoUsuario.ESTUDANTE,
            consentimento_lgpd=True,
            data_consentimento=self.agora - timedelta(days=6 * 365),
            versao_termos="1.0",
            token_validos_apos=self.agora - timedelta(days=5 * 365 + 1),
        )
        self.db.add_all([antigo, recente, log_antigo, log_recente, incidente_retido, incidente_expirado, usuario])
        self.db.commit()

        resultado = aplicar_retencao(self.db, self.db, agora=self.agora, executar=True)

        self.assertTrue(resultado["execucao_realizada"])
        self.assertEqual("Usuário anonimizado", antigo.usuario_nome)
        self.assertEqual("JH-old", antigo.protocolo)
        self.assertEqual("Pessoa Exemplo", recente.usuario_nome)
        self.assertIsNone(log_antigo.usuario_id)
        self.assertEqual("{}", log_antigo.detalhes_json)
        self.assertEqual("usr-1", log_recente.usuario_id)
        self.assertEqual("usr-1", incidente_retido.usuario_id)
        self.assertIsNone(incidente_expirado.usuario_id)
        self.assertFalse(usuario.consentimento_lgpd)
        self.assertIsNone(usuario.data_consentimento)
        self.assertIsNone(usuario.versao_termos)
        self.assertEqual(1, self.db.query(LogAuditoria).filter_by(acao="retencao_aplicada").count())


if __name__ == "__main__":
    unittest.main()
