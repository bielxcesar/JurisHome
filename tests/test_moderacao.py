import unittest
from services.moderacao import validar_atendimento, proteger_texto_legado, proteger_eventos
from routes.feedbacks import FeedbackCriacao, MensagemAdministrativa


class TestesModeracao(unittest.TestCase):
    def test_ofensas_repetidas_e_disfarcadas(self):
        for texto in ("viiaduuuuu", "P0RRA", "seu otário", "caralho"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                validar_atendimento(texto)

    def test_telefones_sem_bloquear_datas_ou_textos_comuns(self):
        for texto in ("(11) 99999-1234", "+55 11 99999 1234", "11999991234", "3333-1234"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                validar_atendimento(texto)
        for texto in ("Computador com problema na discussão", "Acesso em 22/11/2026", "Processo 12345678901234567890"):
            self.assertEqual(texto, validar_atendimento(texto))

    def test_validacao_tambem_nas_respostas_administrativas(self):
        valido = MensagemAdministrativa(mensagem="Resposta adequada ao atendimento", atualizadoEm="2026-11-22T10:00:00+00:00")
        self.assertEqual("Resposta adequada ao atendimento", valido.mensagem)
        with self.assertRaises(ValueError):
            MensagemAdministrativa(mensagem="viiaduuuuu", atualizadoEm="2026-11-22T10:00:00+00:00")
        with self.assertRaises(ValueError):
            FeedbackCriacao(assunto="Problema no acesso", mensagem="Ligue (11) 99999-1234", tipo="Sugestão")

    def test_legado_mascarado_sem_modificar_original(self):
        original = [{"mensagem": "viiaduuuuu", "autor": "Equipe"}]
        seguro = proteger_eventos(original)
        self.assertEqual("viiaduuuuu", original[0]["mensagem"])
        self.assertEqual("[conteúdo ocultado]", seguro[0]["mensagem"])
        self.assertEqual("Equipe", seguro[0]["autor"])
        self.assertEqual("[telefone ocultado]", proteger_texto_legado("11999991234"))
