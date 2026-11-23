import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

CAMINHO = Path(__file__).resolve().parents[1] / 'scripts' / 'usuarios_ficticios.py'
spec = importlib.util.spec_from_file_location('gerador_ficticio', CAMINHO)
gerador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gerador)


class GeradorFicticiosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destino = Path(self.tmp.name) / 'teste.sqlite3'
        self.patch_destino = patch.object(gerador, 'DESTINO', self.destino)
        self.patch_destino.start()
        self.addCleanup(self.patch_destino.stop)
        self.env = patch.dict(os.environ, {'JURISHOME_TEST_MODE': '1', 'DATABASE_URL': 'sqlite://', 'FEEDBACK_DATABASE_URL': 'sqlite://', 'JurisHome_senha': 'chave-ficticia-de-testes-com-mais-de-32-bytes'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch.object(gerador, 'dotenv_values', return_value={})
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def test_bloqueia_producao_railway_e_banco_remoto(self):
        for chave, valor in [('APP_ENV', 'production'), ('RAILWAY_ENVIRONMENT', 'test'), ('DATABASE_URL', 'postgresql://example.invalid/db')]:
            with self.subTest(chave=chave), patch.dict(os.environ, {chave: valor}):
                with self.assertRaises(RuntimeError):
                    gerador.verificar_ambiente()
        self.assertFalse(self.destino.exists())

    def test_banco_preexistente_sem_marcador_nao_e_alterado(self):
        self.destino.write_bytes(b'outro arquivo')
        with self.assertRaises(Exception):
            gerador.abrir()
        self.assertEqual(self.destino.read_bytes(), b'outro arquivo')

    def test_senhas_diferentes_e_validas(self):
        from services.validacao import nova_senha
        primeira = gerador.senha_para('frase ficticia longa', 1)
        segunda = gerador.senha_para('frase ficticia longa', 2)
        self.assertNotEqual(primeira, segunda)
        self.assertEqual(nova_senha(primeira), primeira)

    def test_criacao_idempotente_e_remocao_somente_rastreados(self):
        # Hash simplificado apenas neste teste; o programa real usa bcrypt do projeto.
        from auth import security
        with patch.object(security, 'hash_senha', side_effect=lambda senha: 'hash-teste-' + senha[-8:]):
            self.assertEqual(gerador.criar('frase ficticia longa'), 100)
            self.assertEqual(gerador.criar('frase ficticia longa'), 0)
        engine = gerador.abrir()
        with engine.begin() as con:
            self.assertEqual(con.execute(text('SELECT COUNT(*) FROM usuarios')).scalar_one(), 100)
            self.assertEqual(con.execute(text('SELECT COUNT(*) FROM usuarios WHERE email LIKE :dominio'), {'dominio': '%@example.invalid'}).scalar_one(), 100)
            self.assertEqual(con.execute(text('SELECT COUNT(*) FROM usuarios WHERE is_2fa_enabled = 1')).scalar_one(), 0)
            con.execute(text("INSERT INTO usuarios (uuid, nome, email, tipo_usuario, e_root_admin, is_2fa_enabled, tentativas_login_falhas, consentimento_lgpd, criado_em, atualizado_em) VALUES ('outro', 'Outro Usuario', 'outro@example.invalid', 'estudante', 0, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        engine.dispose()
        self.assertEqual(gerador.remover(), 100)
        engine = gerador.abrir()
        with engine.connect() as con:
            self.assertEqual(con.execute(text('SELECT COUNT(*) FROM usuarios')).scalar_one(), 1)
        engine.dispose()


if __name__ == '__main__':
    unittest.main()
