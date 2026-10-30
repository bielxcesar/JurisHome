import unittest
from types import SimpleNamespace
from services.editorial import ConfiguracaoEditorial, ImagemEditorial, credito, inline, montar_editorial


class EditorialTests(unittest.TestCase):
    def test_formatacao_escapa_html_e_nao_cria_links_arbitrarios(self):
        html = str(inline('**forte** _itálico_ ==destaque== <img src=x onerror="alert(1)">'))
        self.assertIn('<strong>forte</strong>', html)
        self.assertIn('<em>itálico</em>', html)
        self.assertIn('<mark>destaque</mark>', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
        self.assertIsNone(credito('javascript:alert(1)')['url'])
        self.assertEqual(credito('https://www.site.test/muito/longo?query=1')['texto'], 'site.test')

    def test_imagens_sao_posicionadas_sem_repetir_texto_e_creditos(self):
        materia = SimpleNamespace(titulo='Teste', corpo_texto='Primeiro\nSegundo', fonte_imagem='',
            imagem_corpo='data:image/png;base64,YQ==', imagem_extra_2=None, imagem_extra_3=None)
        config = ConfiguracaoEditorial(imagens=[ImagemEditorial(fonte='Acervo pessoal', apos_bloco=0)])
        contexto = montar_editorial(materia, config)
        self.assertEqual([b['tipo'] for b in contexto['blocos_editoriais']], ['imagem','paragrafo','paragrafo'])
        self.assertEqual(contexto['blocos_editoriais'][0]['credito']['texto'], 'Acervo pessoal')
        self.assertEqual(str(contexto['blocos_editoriais'][1]['texto']), 'Primeiro')
