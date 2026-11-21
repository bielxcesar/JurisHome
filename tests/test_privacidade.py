"""Regressões de privacidade com banco isolado e dados fictícios."""

import asyncio
import json
from unittest.mock import patch
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from database import Base
from model.models import (AceiteDocumento, Categoria, Conteudo, ConteudoLeitura,
                          Feedback, FeedbackAtendimento, LogAuditoria, RevisaoLegal,
                          TipoUsuario, Usuario)
from routes.admin import ManutencaoAdministrador, listar_usuarios_filtro, manter_administrador
from routes.feedbacks import _serializar
from routes.perfil import pagina_perfil
from services.administradores import serializar_admin
from services.direitos_titular import (anonimizar_feedbacks_atendimento, anonimizar_feedbacks_legados,
                                     anonimizar_usuario, remover_vinculos_desnecessarios)
from services.leituras import limpar_leituras_antigas
from services.lgpd import historico_aceites, publicar_atualizacao_privacidade, registrar_aceite, revisao_vigente
from services.privacidade import mascarar_email
from services.retencao import aplicar_retencao


class PrivacidadeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.usuario = Usuario(nome="Titular Exemplo", email="titular@example.invalid",
                               tipo_usuario=TipoUsuario.ESTUDANTE, consentimento_lgpd=True,
                               data_consentimento=datetime(2026, 11, 20, 15, 30), versao_termos="2.2")
        self.db.add(self.usuario)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _feedback(self):
        item = FeedbackAtendimento(id="feedback-teste", protocolo="JH-TESTE", usuario_id=self.usuario.uuid,
            usuario_nome=self.usuario.nome, usuario_email=self.usuario.email, tipo="Dúvida", assunto="Assunto",
            mensagem="Mensagem pessoal", historico_json='[{"id":"email@example.invalid"}]')
        self.db.add(item)
        self.db.commit()
        return item

    def test_mascara_na_resposta_administrativa_sem_expor_original(self):
        admin = Usuario(nome="Suporte", email="suporte@example.invalid", tipo_usuario=TipoUsuario.ADMINISTRADOR)
        self.db.add(admin)
        self.db.commit()
        itens = listar_usuarios_filtro(None, self.db, admin, self.db)
        self.assertNotIn(self.usuario.email, json.dumps(itens))
        self.assertEqual("s***@e***", serializar_admin(self.db, admin)["email"])
        feedback = self._feedback()
        self.assertEqual("t***@e***", _serializar(feedback)["usuario"]["email"])
        self.assertEqual(self.usuario.email, _serializar(feedback, incluir_interno=False)["usuario"]["email"])
        self.assertEqual("***", mascarar_email("inválido"))
        self.assertEqual("***", mascarar_email(None))

    def test_root_mantem_email_original_quando_campo_omitido(self):
        root = Usuario(nome="Root", email="root@example.invalid", tipo_usuario=TipoUsuario.ADMINISTRADOR, e_root_admin=True)
        alvo = Usuario(nome="Suporte", email="suporte@example.invalid", tipo_usuario=TipoUsuario.ADMINISTRADOR)
        self.db.add_all([root, alvo])
        self.db.commit()
        resultado = manter_administrador(alvo.uuid, ManutencaoAdministrador(nome="Suporte Alterado", versao=alvo.atualizado_em.isoformat()), self.db, root)
        self.assertEqual("suporte@example.invalid", alvo.email)
        self.assertNotIn(alvo.email, json.dumps(resultado))

    def test_remocao_desvincula_suporte_e_elimina_identificadores_de_logs(self):
        feedback = self._feedback()
        legado = Feedback(usuario_id=self.usuario.uuid, mensagem="Pessoal")
        log = LogAuditoria(usuario_id=self.usuario.uuid, usuario_tipo="estudante", acao="perfil_alterado",
            recurso_tipo="usuario", recurso_id=self.usuario.uuid, resultado="sucesso", correlacao_id="correlacao-original",
            detalhes_json='{"observacao":"email@example.invalid"}')
        self.db.add_all([legado, log])
        self.db.commit()
        identificador = self.usuario.uuid
        remover_vinculos_desnecessarios(self.db, self.usuario)
        anonimizar_feedbacks_atendimento(self.db, identificador)
        anonimizar_feedbacks_legados(self.db, identificador)
        anonimizar_usuario(self.usuario)
        self.db.commit()
        self.assertEqual("titular-removido", feedback.usuario_id)
        self.assertEqual("[]", feedback.historico_json)
        self.assertIsNone(legado.usuario_id)
        self.assertIsNone(log.usuario_id)
        self.assertIsNone(log.recurso_id)
        self.assertEqual("{}", log.detalhes_json)
        self.assertNotEqual("correlacao-original", log.correlacao_id)
        self.assertNotIn(identificador, self.usuario.email)
        self.assertIsNone(self.usuario.foto_perfil)

    def test_retencao_preserva_limite_90_dias_e_apaga_anterior(self):
        hoje = datetime(2026, 11, 20).date()
        categoria = Categoria(nome="Direito Civil")
        self.db.add(categoria)
        self.db.flush()
        conteudo = Conteudo(titulo="Matéria", resumo_home="Resumo", corpo_texto="Texto", categoria_id=categoria.uuid, autor_id=self.usuario.uuid)
        self.db.add(conteudo)
        self.db.flush()
        limite = (hoje - timedelta(days=89)).isoformat()
        self.db.add_all([ConteudoLeitura(usuario_id=self.usuario.uuid, conteudo_id=conteudo.uuid, dia=limite),
                         ConteudoLeitura(usuario_id=self.usuario.uuid, conteudo_id=conteudo.uuid, dia=(hoje - timedelta(days=90)).isoformat())])
        self.db.commit()
        self.assertEqual(1, limpar_leituras_antigas(self.db, hoje))
        self.db.commit()
        self.assertEqual([limite], [item.dia for item in self.db.query(ConteudoLeitura)])

    def test_historico_real_persistente_com_horario_brasilia_e_sem_duplicacao(self):
        registrar_aceite(self.db, self.usuario)
        self.db.commit()
        registrar_aceite(self.db, self.usuario)
        self.usuario.versao_termos = "legal-2"
        self.usuario.data_consentimento = datetime(2026, 11, 21, 15, 30)
        registrar_aceite(self.db, self.usuario)
        self.db.commit()
        historico = historico_aceites(self.db, self.usuario)
        self.assertEqual(["legal-2", "2.2"], [item["versao"] for item in historico])
        self.assertEqual(12, historico[0]["aceito_em"].hour)
        self.assertEqual(2, self.db.query(AceiteDocumento).count())
        request = Request({"type":"http", "method":"GET", "path":"/perfil", "headers":[], "scheme":"http", "server":("testserver",80), "query_string":b""})
        pagina = pagina_perfil(request, self.usuario, self.db).body.decode()
        self.assertIn("21/11/2026 às 12:30:00", pagina)
        self.assertIn("legal-2", pagina)

    def test_descarte_do_historico_de_aceite_apos_encerramento_mais_cinco_anos(self):
        registrar_aceite(self.db, self.usuario)
        anonimizar_usuario(self.usuario)
        self.usuario.token_validos_apos = datetime(2020, 1, 1)
        self.db.commit()
        aplicar_retencao(self.db, self.db, agora=datetime(2026, 11, 20, tzinfo=timezone.utc), executar=True)
        self.assertEqual(0, self.db.query(AceiteDocumento).count())
        self.assertIsNone(self.usuario.data_consentimento)

    def test_rotina_automatica_inicia_e_e_cancelada_no_encerramento(self):
        from services.leituras import ciclo_retencao_metricas
        chamadas = []
        async def executar(funcao):
            chamadas.append(funcao)
        async def conferir():
            with patch("services.leituras.run_in_threadpool", side_effect=executar):
                async with ciclo_retencao_metricas(None):
                    await asyncio.sleep(0)
                    self.assertEqual(1, len(chamadas))
                await asyncio.sleep(0)
                self.assertEqual(1, len(chamadas))
        asyncio.run(conferir())

    def test_sessoes_refresh_presencas_e_desafios_sao_eliminados(self):
        from model.models import SessaoAutenticada, PresencaSessao, RefreshToken, DesafioConsumido, CodigoTotpConsumido
        agora = datetime(2026, 11, 20)
        sessao = SessaoAutenticada(usuario_id=self.usuario.uuid, criada_em=agora, expira_em=agora + timedelta(minutes=15))
        self.db.add(sessao)
        self.db.flush()
        self.db.add_all([PresencaSessao(sessao_id=sessao.id, confirmada_em=agora),
                         RefreshToken(digest="refresh-teste", sessao_id=sessao.id),
                         DesafioConsumido(digest="desafio-teste", usuario_id=self.usuario.uuid, expira_em=agora),
                         CodigoTotpConsumido(usuario_id=self.usuario.uuid, segredo_digest="segredo-teste", intervalo=1)])
        self.db.commit()
        remover_vinculos_desnecessarios(self.db, self.usuario)
        self.db.commit()
        for modelo in (SessaoAutenticada, PresencaSessao, RefreshToken, DesafioConsumido, CodigoTotpConsumido):
            self.assertEqual(0, self.db.query(modelo).count())

    def test_publicacao_preserva_edicao_root_e_nao_duplica_revisao(self):
        self.db.add(RevisaoLegal(anterior="__versao_estatica_inicial__", termos="Termos editados pelo root",
                                politica="Política editada pelo root", publicada_em=datetime(2026,11,19)))
        self.db.commit()
        self.assertTrue(publicar_atualizacao_privacidade(self.db))
        self.assertFalse(publicar_atualizacao_privacidade(self.db))
        atual = revisao_vigente(self.db)
        self.assertIn("Política editada pelo root", atual.politica)
        self.assertIn("Revisão de privacidade de 20/11/2026", atual.politica)
        self.assertEqual("Termos editados pelo root", atual.termos)
        self.assertEqual(2, self.db.query(RevisaoLegal).count())


if __name__ == "__main__":
    unittest.main()
