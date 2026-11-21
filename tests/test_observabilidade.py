"""Garante contexto útil nos logs operacionais sem reproduzir dados do pedido."""

import json
import logging
import asyncio
from io import StringIO
from types import SimpleNamespace
import unittest

from starlette.requests import Request

from services.logs_operacionais import (
    FormatadorJSONOperacional,
    definir_correlacao_operacional,
    processar_requisicao_com_log,
    registrar_falha_operacional,
    registrar_log_requisicao,
    restaurar_correlacao_operacional,
)


class LogsOperacionaisTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("jurishome")
        self.handlers_anteriores = self.logger.handlers[:]
        self.nivel_anterior = self.logger.level
        self.propagacao_anterior = self.logger.propagate
        self.saida = StringIO()
        self.handler = logging.StreamHandler(self.saida)
        self.handler.setFormatter(FormatadorJSONOperacional())
        self.logger.handlers = [self.handler]
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def tearDown(self):
        self.logger.handlers = self.handlers_anteriores
        self.logger.setLevel(self.nivel_anterior)
        self.logger.propagate = self.propagacao_anterior
        self.saida.close()

    def _request(self, method="GET", route="/glossario"):
        request = Request({
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/glossario",
            "raw_path": b"/glossario",
            "query_string": b"email=estudante%40exemplo.invalid&token=nao-registrar",
            "root_path": "",
            "headers": [(b"cookie", b"jurishome_access_token=segredo-nao-registrar")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        })
        request.scope["route"] = SimpleNamespace(path=route)
        request.state.correlacao_id = "bb4a3b32-902f-49aa-9782-1d902cdbcb11"
        return request

    def test_requisicao_registra_rota_modelo_duracao_status_e_correlacao_sem_query_ou_cookie(self):
        registrar_log_requisicao(
            self._request(), status=200, duracao_ms=14.257
        )
        linha = self.saida.getvalue().strip()
        evento = json.loads(linha)

        self.assertEqual("http_request", evento["message"])
        self.assertEqual("jurishome.http", evento["component"])
        self.assertEqual("GET", evento["method"])
        self.assertEqual("/glossario", evento["route"])
        self.assertEqual(200, evento["http_status"])
        self.assertEqual(14.26, evento["duration_ms"])
        self.assertEqual("bb4a3b32-902f-49aa-9782-1d902cdbcb11", evento["correlation_id"])
        self.assertTrue(evento["timestamp"].endswith("Z"))
        self.assertNotIn("email=", linha)
        self.assertNotIn("estudante@", linha)
        self.assertNotIn("token=", linha)
        self.assertNotIn("segredo-nao-registrar", linha)

    def test_rota_nao_encontrada_nao_registra_caminho_literal(self):
        request = self._request(route=None)
        request.scope.pop("route")
        request.scope["path"] = "/usuarios/estudante@example.invalid"
        registrar_log_requisicao(request, status=404, duracao_ms=2)
        evento = json.loads(self.saida.getvalue().strip())

        self.assertEqual("<unmatched>", evento["route"])
        self.assertNotIn("estudante@example.invalid", self.saida.getvalue())

    def test_falha_registra_tipo_e_localizacao_sem_mensagem_da_excecao(self):
        try:
            raise RuntimeError("e-mail=estudante@example.invalid senha=nao-registrar")
        except RuntimeError as erro:
            registrar_falha_operacional(
                componente="retencao.metricas",
                operacao="limpeza_diaria",
                erro=erro,
            )

        evento = json.loads(self.saida.getvalue().strip())
        self.assertEqual("operation_failed", evento["message"])
        self.assertEqual("jurishome.retencao.metricas", evento["component"])
        self.assertEqual("RuntimeError", evento["exception_type"])
        self.assertEqual("limpeza_diaria", evento["operation"])
        self.assertTrue(evento["stack"])
        self.assertNotIn("estudante@example.invalid", self.saida.getvalue())
        self.assertNotIn("nao-registrar", self.saida.getvalue())

    def test_falha_de_integracao_reaproveita_correlacao_da_requisicao(self):
        identificador = "5d9df82a-b6cc-4d41-96c8-621f58cb8651"
        try:
            raise TimeoutError("não registrar detalhes da conexão")
        except TimeoutError as erro:
            token = definir_correlacao_operacional(identificador)
            try:
                registrar_falha_operacional(
                    componente="integracao.senado",
                    operacao="consulta_legislacao",
                    erro=erro,
                )
            finally:
                restaurar_correlacao_operacional(token)

        evento = json.loads(self.saida.getvalue().strip())
        self.assertEqual(identificador, evento["correlation_id"])
        self.assertEqual("TimeoutError", evento["exception_type"])
        self.assertNotIn("conexão", self.saida.getvalue())

    def test_falha_inesperada_retorna_500_seguro_sem_repassar_excecao(self):
        request = self._request(route="/materias")
        request.scope["path"] = "/materias"
        request.state.correlacao_id = "8e4679c1-4419-48ef-af1d-ae2a5936ad32"
        segredo = "senha=nao-registrar token=nao-expor"

        async def falhar(_request):
            raise RuntimeError(segredo)

        resposta = asyncio.run(processar_requisicao_com_log(request, falhar))
        evento = json.loads(self.saida.getvalue().strip())

        self.assertEqual(500, resposta.status_code)
        self.assertEqual("8e4679c1-4419-48ef-af1d-ae2a5936ad32", resposta.headers["X-Correlation-ID"])
        self.assertEqual("http_request", evento["message"])
        self.assertEqual("RuntimeError", evento["exception_type"])
        self.assertEqual(500, evento["http_status"])
        self.assertNotIn(segredo, self.saida.getvalue())
        self.assertNotIn(segredo, resposta.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
