import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import seed
from setup_local import preparar_ambiente


class SetupLocalTests(unittest.TestCase):
    def test_cria_env_com_chave_aleatoria_e_nao_substitui_env_existente(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            (raiz / ".env.example").write_text(
                "DATABASE_URL=sqlite:///./juris_home.db\n"
                "JurisHome_senha=__GERAR_CHAVE_LOCAL__\n",
                encoding="utf-8",
            )

            with patch("setup_local.secrets.token_urlsafe", return_value="chave-local-de-teste"):
                self.assertTrue(preparar_ambiente(raiz))

            env = raiz / ".env"
            conteudo = env.read_text(encoding="utf-8")
            self.assertIn("JurisHome_senha=chave-local-de-teste", conteudo)
            self.assertNotIn("__GERAR_CHAVE_LOCAL__", conteudo)

            env.write_text("nao sobrescrever\n", encoding="utf-8")
            self.assertFalse(preparar_ambiente(raiz))
            self.assertEqual("nao sobrescrever\n", env.read_text(encoding="utf-8"))

    def test_seed_recusa_banco_nao_sqlite(self):
        with patch.object(seed, "SQLALCHEMY_DATABASE_URL", "postgresql://localhost/juris_home"):
            with self.assertRaisesRegex(RuntimeError, "somente dados fictícios"):
                seed._validar_bancos_locais()

    def test_conteudo_de_seed_fica_identificado_como_ficticio(self):
        self.assertTrue(all(item["titulo"].startswith("[DEMONSTRAÇÃO]") for item in seed.CONTEUDOS_DEMONSTRACAO))
        self.assertTrue(all("CONTEÚDO FICTÍCIO" in item["corpo_texto"] for item in seed.CONTEUDOS_DEMONSTRACAO))
        self.assertEqual("demo@example.invalid", seed.EMAIL_USUARIO_DEMONSTRACAO)

    def test_seed_nao_regrava_feedback_ja_sanitizado(self):
        demonstracao = seed.FEEDBACKS_DEMONSTRACAO[0]
        feedback = SimpleNamespace(
            **demonstracao,
            usuario_id="usr-demo-local",
            usuario_nome="Usuário fictício de demonstração",
            usuario_email=seed.EMAIL_USUARIO_DEMONSTRACAO,
            respostas_json="[]",
            observacoes_json="[]",
            historico_json=seed._historico_demo(seed.datetime.now(seed.timezone.utc)),
            novo=True,
            arquivado=False,
        )

        class Query:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [feedback]

        class Session:
            def query(self, *_args, **_kwargs):
                return Query()

        self.assertEqual(0, seed._sanitizar_feedbacks_legados(Session()))


if __name__ == "__main__":
    unittest.main()
