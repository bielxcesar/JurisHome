import unittest
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class ProcurarInterface(HTMLParser):
    def __init__(self):
        super().__init__()
        self.final = False
        self.regras = False
        self.link_final = None
        self.titulo_regras = False
        self.trecho_regras = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and attrs.get('id') == 'j-final':
            self.final = True
        if tag == 'section' and attrs.get('aria-labelledby') == 'j-regras-titulo':
            self.regras = True
            self.regras_visiveis = 'hidden' not in attrs
        if self.final and tag == 'a':
            self.link_final = attrs.get('href')
        if self.regras and tag == 'h2' and attrs.get('id') == 'j-regras-titulo':
            self.titulo_regras = True

    def handle_endtag(self, tag):
        if tag == 'section':
            self.final = False
            self.regras = False

    def handle_data(self, data):
        if self.regras:
            self.trecho_regras.append(data)


class TesteInterfaceJuridle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        diretorio = Path(__file__).resolve().parents[1] / 'templates'
        cls.templates = Environment(loader=FileSystemLoader(diretorio), autoescape=select_autoescape(['html']))

    def test_regras_visiveis_e_destino_da_home_por_perfil(self):
        for perfil, destino in [('estudante', '/home_usuario'), ('administrador', '/home_admin')]:
            with self.subTest(perfil=perfil):
                html = self.templates.get_template('juridle.html').render(tipo_usuario=perfil)
                parser = ProcurarInterface()
                parser.feed(html)
                self.assertEqual(destino, parser.link_final)
                self.assertTrue(parser.regras_visiveis)
                self.assertTrue(parser.titulo_regras)
                self.assertIn('Regras do jogo', ''.join(parser.trecho_regras))

    def test_texto_da_rotina(self):
        html = self.templates.get_template('conhecimento.html').render(tipo_usuario='estudante')
        self.assertIn('Comece estudando as áreas do Direito, veja termos no glossário, leia uma matéria da área de seu interesse e termine com uma rodada do JuridLE.', html)


if __name__ == '__main__':
    unittest.main()
