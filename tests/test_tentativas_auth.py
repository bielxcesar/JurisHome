import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

os.environ.setdefault('JurisHome_senha','segredo-de-teste-jurishome-com-mais-de-32-bytes')
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from model.models import LimiteAutenticacao
from services import tentativas_auth as limites


def request(ip='198.51.100.10', encaminhado='203.0.113.1'):
    return Request({'type':'http','client':(ip,1234),'headers':[(b'x-forwarded-for',encaminhado.encode())]})


class TentativasPersistentesTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine)
        self.db=self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_seis_falhas_e_oito_minutos_sem_estender_bloqueio(self):
        inicio=datetime(2026,11,6,12)
        with patch.object(limites,'agora',return_value=inicio):
            for _ in range(6):
                baldes=limites.preparar(self.db,request(),'inexistente@example.test')
                limites.falhar(baldes)
                self.db.commit()
            with self.assertRaises(HTTPException) as erro:
                limites.exigir_liberado(baldes)
            self.assertEqual(erro.exception.status_code,429)
            self.assertEqual(erro.exception.headers['Retry-After'],'480')
        with patch.object(limites,'agora',return_value=inicio+timedelta(seconds=60)):
            with self.assertRaises(HTTPException) as erro:
                limites.preparar(self.db,request(),'outra@example.test')
            self.assertEqual(erro.exception.headers['Retry-After'],'420')
            self.db.rollback()
            self.assertEqual(limites.estado_origem(self.db,request())['aguardeSegundos'],420)
        with patch.object(limites,'agora',return_value=inicio+timedelta(seconds=480)):
            baldes=limites.preparar(self.db,request(),'inexistente@example.test')
            self.assertTrue(all(b.falhas==0 for b in baldes))

    def test_trocar_ip_nao_libera_conta_e_cabecalho_nao_troca_origem(self):
        for i in range(6):
            baldes=limites.preparar(self.db,request(ip=f'198.51.100.{i+1}'),'alvo@example.test')
            limites.falhar(baldes)
            self.db.commit()
        with self.assertRaises(HTTPException):
            limites.preparar(self.db,request(ip='203.0.113.100'),'alvo@example.test')
        self.db.rollback()
        for i in range(6):
            baldes=limites.preparar(self.db,request(ip='203.0.113.10',encaminhado=f'192.0.2.{i}'),f'pessoa{i}@example.test')
            limites.falhar(baldes)
            self.db.commit()
        with self.assertRaises(HTTPException):
            limites.preparar(self.db,request(ip='203.0.113.10',encaminhado='192.0.2.200'),'novo@example.test')
        self.db.rollback()
        self.assertTrue(all('example' not in b.chave and '203.' not in b.chave for b in self.db.query(LimiteAutenticacao)))

    def test_contadores_persistem_entre_processos_e_concorrencia_nao_perde_falhas(self):
        with TemporaryDirectory() as pasta:
            endereco='sqlite:///'+(Path(pasta)/'limites.db').as_posix()
            engine=create_engine(endereco,connect_args={'check_same_thread':False})
            Base.metadata.create_all(engine)
            fabrica=sessionmaker(bind=engine)
            barreira=Barrier(6)
            def falhar(_):
                with fabrica() as db:
                    barreira.wait(timeout=10)
                    baldes=limites.preparar(db,request(),'alvo@example.test')
                    limites.falhar(baldes)
                    db.commit()
            try:
                with ThreadPoolExecutor(max_workers=6) as executor:
                    list(executor.map(falhar,range(6)))
                engine.dispose()
                engine=create_engine(endereco)
                with sessionmaker(bind=engine)() as db:
                    self.assertEqual([b.falhas for b in db.query(LimiteAutenticacao)],[6,6])
                    self.assertTrue(limites.estado_origem(db,request())['bloqueado'])
            finally:
                engine.dispose()
