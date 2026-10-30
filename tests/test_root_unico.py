import unittest
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from model.models import Usuario, TipoUsuario, SessaoAutenticada, LogAuditoria
from services.root_unico import garantir_root_unico, corrigir_duplicidade


class RootUnicoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def usuario(self, email, root=False):
        u = Usuario(nome='Administrador de teste', email=email, tipo_usuario=TipoUsuario.ADMINISTRADOR, e_root_admin=root)
        self.db.add(u)
        self.db.commit()
        return u

    def test_banco_rejeita_segundo_root_mas_aceita_varios_suportes(self):
        self.usuario('root@example.test', True)
        suporte = self.usuario('suporte@example.test')
        self.usuario('outro@example.test')
        suporte.e_root_admin = True
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        with self.assertRaises(IntegrityError):
            self.db.execute(text("UPDATE usuarios SET e_root_admin = 1 WHERE email = 'outro@example.test'"))
            self.db.commit()
        self.db.rollback()
        self.db.add(Usuario(nome='Segundo root', email='segundo@example.test', tipo_usuario=TipoUsuario.ADMINISTRADOR, e_root_admin=True))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self.db.query(Usuario).filter_by(e_root_admin=True).count(), 1)

    def test_root_nao_pode_ser_leitor_e_instalacao_e_idempotente(self):
        garantir_root_unico(self.engine)
        garantir_root_unico(self.engine)
        self.db.add(Usuario(nome='Leitor', email='leitor@example.test', tipo_usuario=TipoUsuario.ESTUDANTE, e_root_admin=True))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_corrige_duplicidade_legada_sem_escolher_conta_automaticamente(self):
        self.db.execute(text('DROP INDEX uq_usuarios_root_unico'))
        self.db.commit()
        manter = self.usuario('manter@example.test', True)
        rebaixar = self.usuario('rebaixar@example.test', True)
        from datetime import datetime, timedelta
        self.db.add(SessaoAutenticada(usuario_id=rebaixar.uuid, criada_em=datetime.utcnow(), expira_em=datetime.utcnow()+timedelta(days=1)))
        self.db.commit()
        with self.assertRaises(RuntimeError):
            garantir_root_unico(self.engine)
        with self.assertRaises(ValueError):
            corrigir_duplicidade(self.db, 'nao-existe@example.test')
        self.db.rollback()
        alterados = corrigir_duplicidade(self.db, manter.email)
        self.assertEqual(alterados, [rebaixar.uuid])
        self.db.refresh(rebaixar)
        self.assertFalse(rebaixar.e_root_admin)
        self.assertEqual(rebaixar.tipo_usuario, TipoUsuario.ADMINISTRADOR)
        self.assertIsNotNone(rebaixar.token_validos_apos)
        self.assertTrue(self.db.query(SessaoAutenticada).filter_by(usuario_id=rebaixar.uuid).one().revogada)
        self.assertEqual(self.db.query(LogAuditoria).filter_by(acao='root_duplicado_corrigido').count(), 1)
        self.assertEqual(corrigir_duplicidade(self.db, manter.email), [])
        garantir_root_unico(self.engine)

    def test_script_inicial_nao_cria_outro_root(self):
        import criar_admin
        self.usuario('principal@example.test', True)
        with patch.object(criar_admin, 'engine', self.engine), patch.object(criar_admin, 'SessionLocal', self.Session), patch.object(criar_admin, 'obrigatorio', side_effect=['novo@example.test', 'SenhaSegura123', 'Novo root']):
            self.assertEqual(criar_admin.main(), 0)
        self.assertEqual(self.db.query(Usuario).count(), 2)
        self.assertFalse(self.db.query(Usuario).filter_by(email='novo@example.test').one().e_root_admin)
        self.assertEqual(self.db.query(Usuario).filter_by(e_root_admin=True).count(), 1)

    def test_primeiro_admin_do_script_e_root_e_repetir_nao_altera_conta(self):
        import criar_admin
        with patch.object(criar_admin, 'engine', self.engine), patch.object(criar_admin, 'SessionLocal', self.Session), patch.object(criar_admin, 'obrigatorio', side_effect=['primeiro@example.test', 'SenhaSegura123', 'Primeiro admin']):
            self.assertEqual(criar_admin.main(), 0)
        root = self.db.query(Usuario).one()
        self.assertTrue(root.e_root_admin)
        senha_original = root.senha_hash
        with patch.object(criar_admin, 'engine', self.engine), patch.object(criar_admin, 'SessionLocal', self.Session), patch.object(criar_admin, 'obrigatorio', side_effect=['primeiro@example.test', 'OutraSenha456', 'Outro nome']):
            self.assertEqual(criar_admin.main(), 0)
        self.db.refresh(root)
        self.assertEqual(root.nome, 'Primeiro admin')
        self.assertEqual(root.senha_hash, senha_original)

    def test_duas_criacoes_simultaneas_so_deixam_um_root(self):
        with TemporaryDirectory() as pasta:
            engine = create_engine('sqlite:///' + (Path(pasta)/'roots.db').as_posix(), connect_args={'check_same_thread': False})
            try:
                Base.metadata.create_all(engine)
                fabrica = sessionmaker(bind=engine)
                barreira = Barrier(2)
                def criar(i):
                    with fabrica() as db:
                        barreira.wait(timeout=10)
                        db.add(Usuario(nome='Root de teste', email=f'root{i}@example.test', tipo_usuario=TipoUsuario.ADMINISTRADOR, e_root_admin=True))
                        try:
                            db.commit()
                            return True
                        except IntegrityError:
                            db.rollback()
                            return False
                with ThreadPoolExecutor(max_workers=2) as executor:
                    resultados = list(executor.map(criar, range(2)))
                self.assertEqual(sum(resultados), 1)
                with fabrica() as db:
                    self.assertEqual(db.query(Usuario).filter_by(e_root_admin=True).count(), 1)
            finally:
                engine.dispose()
