import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

from services.legislacao_senado import buscar_legislacao


class ConsultaSenadoTests(unittest.TestCase):
    def test_busca_e_detalhes_usam_host_e_parametros_esperados(self):
        lista = {"ListaDocumento": {"documentos": {"documento": [{
            "id": "123", "ementa": "Ementa de exemplo"
        }]}}}
        detalhe = {"DetalheDocumento": {"documentos": {"documento": [{
            "identificacao": {"normaNome": "Norma de exemplo", "urlDocumento": "https://normas.leg.br/exemplo"}
        }]}}}
        requisicoes = []

        def abrir(requisicao, timeout):
            requisicoes.append(requisicao.full_url)
            self.assertEqual(timeout, 12)
            self.assertEqual(urlparse(requisicao.full_url).hostname, "legis.senado.leg.br")
            dados = lista if len(requisicoes) == 1 else detalhe
            return BytesIO(json.dumps(dados).encode("utf-8"))

        with patch("services.legislacao_senado.urlopen", side_effect=abrir):
            resultado = buscar_legislacao("DEL", "123", 1943)

        self.assertEqual(parse_qs(urlparse(requisicoes[0]).query), {"tipo": ["DEL"], "numero": ["123"], "ano": ["1943"]})
        self.assertTrue(requisicoes[1].endswith("/legislacao/123.json"))
        self.assertTrue(resultado["encontrado"])
        self.assertEqual(resultado["norma"]["ementa"], "Ementa de exemplo")
        self.assertEqual(resultado["norma"]["nome"], "Norma de exemplo")
        self.assertEqual(resultado["norma"]["url_documento"], "https://normas.leg.br/exemplo")

    def test_consulta_sem_resultado(self):
        lista = {"ListaDocumento": {"documentos": {"documento": []}}}
        with patch("services.legislacao_senado.urlopen", return_value=BytesIO(json.dumps(lista).encode())):
            self.assertFalse(buscar_legislacao("LEI", "1", 2000)["encontrado"])

    def test_entrada_invalida_nao_faz_requisicao(self):
        with patch("services.legislacao_senado.urlopen") as abrir:
            with self.assertRaises(HTTPException) as erro:
                buscar_legislacao("OUTRO", "123", 2025)
        self.assertEqual(erro.exception.status_code, 422)
        abrir.assert_not_called()

    def test_indisponibilidade_retorna_503_sem_detalhe_interno(self):
        with patch("services.legislacao_senado.urlopen", side_effect=URLError("detalhe interno")), \
             patch("services.legislacao_senado.registrar_falha_operacional"):
            with self.assertRaises(HTTPException) as erro:
                buscar_legislacao("LEI", "1", 2000)
        self.assertEqual(erro.exception.status_code, 503)
        self.assertNotIn("detalhe interno", erro.exception.detail)

    def test_falha_opcional_de_detalhes_preserva_ementa(self):
        lista = {"ListaDocumento": {"documentos": {"documento": [{"id": "123", "ementa": "Ementa"}]}}}
        with patch("services.legislacao_senado.urlopen", side_effect=[BytesIO(json.dumps(lista).encode()), URLError("erro")]), \
             patch("services.legislacao_senado.registrar_falha_operacional"):
            resultado = buscar_legislacao("LEI", "1", 2000)
        self.assertTrue(resultado["encontrado"])
        self.assertEqual(resultado["norma"]["ementa"], "Ementa")
        self.assertEqual(resultado["norma"]["url_documento"], "")


if __name__ == "__main__":
    unittest.main()
