import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from fastapi import HTTPException
from pydantic import ValidationError

from routes.glossario import ConsultaProcessoDatajud
from services.datajud import consultar_processo_publico, normalizar_numero_processo


class DataJudTests(unittest.TestCase):
    NUMERO_FORMATADO = "0000832-35.2018.4.01.3202"
    NUMERO_LIMPO = "00008323520184013202"

    def test_normaliza_numero_cnj_formatado_e_limpo(self):
        self.assertEqual(self.NUMERO_LIMPO, normalizar_numero_processo(self.NUMERO_FORMATADO))
        self.assertEqual(self.NUMERO_LIMPO, normalizar_numero_processo(self.NUMERO_LIMPO))

    def test_rejeita_numero_invalido_e_alias_de_tribunal_desconhecido(self):
        with self.assertRaises(HTTPException) as erro_numero:
            consultar_processo_publico("123", "trf1", api_key="chave-teste")
        self.assertEqual(422, erro_numero.exception.status_code)

        with patch("services.datajud.urlopen") as abrir:
            with self.assertRaises(HTTPException) as erro_tribunal:
                consultar_processo_publico(self.NUMERO_FORMATADO, "https://fora-do-cnj", api_key="chave-teste")
        self.assertEqual(422, erro_tribunal.exception.status_code)
        abrir.assert_not_called()

    def test_schema_recusa_campos_extras(self):
        with self.assertRaises(ValidationError):
            ConsultaProcessoDatajud.model_validate({
                "numero_processo": self.NUMERO_FORMATADO,
                "tribunal": "trf1",
                "url": "https://fora-do-cnj",
            })

    def test_glossario_renderiza_formulario_sem_expor_chave(self):
        from routes.glossario import pagina_glossario, router
        from starlette.requests import Request

        request = Request({"type": "http", "method": "GET", "path": "/glossario", "headers": []})
        html = pagina_glossario(request, q="", letra="", origem="", usuario=None).body.decode("utf-8")

        self.assertIn('id="datajud-form"', html)
        self.assertIn('name="numero_processo"', html)
        self.assertIn('value="trf1"', html)
        self.assertIn("/static/js/datajud.js", html)
        self.assertNotIn("DATAJUD_API_KEY", html)
        self.assertIn("CNJ — DataJud", html)
        self.assertTrue(any(route.path == "/api/glossario/datajud" for route in router.routes))

    def test_consulta_mapeia_metadados_sem_devolver_partes(self):
        resposta = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_source": {
                    "numeroProcesso": self.NUMERO_LIMPO,
                    "tribunal": "TRF1",
                    "grau": "G1",
                    "dataAjuizamento": "2018-01-01T00:00:00.000Z",
                    "classe": {"codigo": 1116, "nome": "Execução Fiscal"},
                    "assuntos": [{"nome": "Dívida Ativa"}],
                    "orgaoJulgador": {"nome": "Vara de Execução Fiscal"},
                    "movimentos": [{"nome": "Distribuído", "dataHora": "2018-01-02T00:00:00.000Z"}],
                    "partes": [{"nome": "Pessoa não deve sair na resposta"}],
                }}],
            }
        }

        def abrir(requisicao, timeout):
            self.assertEqual("POST", requisicao.get_method())
            self.assertEqual("APIKey chave-teste", requisicao.get_header("Authorization"))
            self.assertEqual("application/json", requisicao.get_header("Content-type"))
            self.assertEqual(
                self.NUMERO_LIMPO,
                json.loads(requisicao.data)["query"]["match"]["numeroProcesso"],
            )
            self.assertIn("api_publica_trf1/_search", requisicao.full_url)
            self.assertEqual(12, timeout)
            return BytesIO(json.dumps(resposta).encode("utf-8"))

        with patch("services.datajud.urlopen", side_effect=abrir):
            resultado = consultar_processo_publico(self.NUMERO_FORMATADO, "trf1", api_key="chave-teste")

        self.assertTrue(resultado["encontrado"])
        self.assertEqual("Execução Fiscal", resultado["processo"]["classe"])
        self.assertEqual(["Dívida Ativa"], resultado["processo"]["assuntos"])
        self.assertNotIn("partes", resultado["processo"])
        self.assertNotIn("Pessoa não deve sair", json.dumps(resultado, ensure_ascii=False))
        self.assertIn("Conselho Nacional de Justiça", resultado["fonte"])

    def test_consulta_sem_resultado_retorna_estado_vazio(self):
        with patch("services.datajud.urlopen", return_value=BytesIO(b'{"hits":{"total":{"value":0},"hits":[]}}')):
            resultado = consultar_processo_publico(self.NUMERO_FORMATADO, "trf1", api_key="chave-teste")
        self.assertFalse(resultado["encontrado"])
        self.assertIsNone(resultado["processo"])

    def test_erro_do_provedor_nao_vaza_detalhes(self):
        with patch("services.datajud.urlopen", side_effect=URLError("detalhe interno da conexao")):
            with self.assertRaises(HTTPException) as erro:
                consultar_processo_publico(self.NUMERO_FORMATADO, "trf1", api_key="chave-teste")
        self.assertEqual(503, erro.exception.status_code)
        self.assertNotIn("detalhe interno", erro.exception.detail)

    def test_chave_ausente_falha_com_mensagem_controlada(self):
        with patch.dict(os.environ, {"DATAJUD_API_KEY": ""}):
            with self.assertRaises(HTTPException) as erro:
                consultar_processo_publico(self.NUMERO_FORMATADO, "trf1")
        self.assertEqual(503, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
