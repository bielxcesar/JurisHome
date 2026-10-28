import json
import unittest
from pathlib import Path

from services.glossario import consultar_glossario, normalizar


class GlossarioTests(unittest.TestCase):
    def test_menu_usa_perfil_real_e_preserva_ordem(self):
        from types import SimpleNamespace
        from starlette.requests import Request
        from routes.glossario import pagina_glossario
        from model.models import TipoUsuario

        request = Request({"type": "http", "method": "GET", "path": "/glossario", "headers": []})
        admin = SimpleNamespace(tipo_usuario=TipoUsuario.ADMINISTRADOR)
        html = pagina_glossario(request, q="", letra="", origem="usuario", usuario=admin).body.decode()
        nav = html.split('aria-label="Navegação principal"')[1].split('</nav>')[0]
        nomes = ["Home", "Exibir mais", "Feedbacks", "Auditoria", "Sobre nós", "Categorias", "Pesquisa", "Glossário"]
        self.assertEqual([nav.index(nome) for nome in nomes], sorted(nav.index(nome) for nome in nomes))
        self.assertIn('aria-current="page"', nav)
        self.assertNotIn('Suporte', nav)
        visitante = pagina_glossario(request, q="", letra="", origem="", usuario=None).body.decode()
        self.assertIn('Suporte', visitante)
        self.assertNotIn('href="/admin/auditoria"', visitante)

    def test_busca_ignora_acentos_caixa_e_espacos(self):
        resultado = consultar_glossario("  ACORDAO  ")
        self.assertEqual([t["id"] for t in resultado["itens"]], ["acordao"])
        self.assertEqual(
            consultar_glossario("ônus da prova")["itens"],
            consultar_glossario("ONUS   DA PROVA")["itens"],
        )

    def test_palavras_podem_ocorrer_em_ordem_diferente(self):
        resultado = consultar_glossario("prova onus")
        self.assertEqual([t["id"] for t in resultado["itens"]], ["onus-da-prova"])

    def test_busca_tambem_encontra_definicoes(self):
        self.assertIn("habeas-corpus", [t["id"] for t in consultar_glossario("locomocao")["itens"]])

    def test_letra_combina_com_busca_e_trata_inicial_acentuada(self):
        self.assertEqual(consultar_glossario("", "O")["itens"][0]["id"], "onus-da-prova")
        self.assertEqual(consultar_glossario("acordao", "C")["total"], 0)
        resultado = consultar_glossario("", "c")
        self.assertTrue(resultado["itens"])
        self.assertTrue(all(normalizar(t["termo"]).startswith("c") for t in resultado["itens"]))

    def test_lista_ordenada_e_busca_sem_resultados(self):
        nomes = [normalizar(t["termo"]) for t in consultar_glossario()["itens"]]
        self.assertEqual(nomes, sorted(nomes))
        self.assertEqual(consultar_glossario("zzzinexistente")["total"], 0)
        self.assertEqual(consultar_glossario("   ")["total"], len(nomes))

    def test_catalogo_tem_ids_unicos_exemplos_e_fontes_legais(self):
        arquivo = Path(__file__).resolve().parents[1] / "data" / "glossario.json"
        catalogo = json.loads(arquivo.read_text(encoding="utf-8"))
        termos = catalogo["termos"]
        self.assertEqual(len(termos), len({t["id"] for t in termos}))
        for termo in termos:
            with self.subTest(termo=termo["termo"]):
                self.assertTrue(termo["definicao"].strip())
                self.assertTrue(termo["exemplo"].strip())
                self.assertTrue(termo["referencia"].strip())
                self.assertIn(termo["fonte_id"], catalogo["fontes"])
                self.assertTrue(catalogo["fontes"][termo["fonte_id"]]["url"].startswith("https://www.planalto.gov.br/"))


if __name__ == "__main__":
    unittest.main()
