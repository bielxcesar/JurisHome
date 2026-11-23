import asyncio
import base64
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

os.environ.setdefault("JurisHome_senha", "segredo-de-teste-jurishome-com-mais-de-32-bytes")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"t" * 32).decode("ascii"))

import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.responses import Response

import auth.security as security
from auth.security import (
    cifrar_segredo_2fa,
    criar_access_token,
    criar_token_2fa_pendente,
    hash_senha,
    verificar_senha,
)
from database import Base, get_db
from feedback_database import get_feedback_db
from model import models  
from model.models import TipoUsuario, Usuario
from routes.auth import (
    Codigo2FA,
    CadastroUsuario,
    Credenciais,
    NovaSenhaRecuperacao,
    alterar_senha_recuperada,
    cadastrar_usuario,
    iniciar_recuperacao_senha,
    validar_recuperacao_senha,
)


class TestesSeguranca(unittest.TestCase):
    def test_sobre_nos_menu_e_equipe_sem_secoes_recolhiveis(self):
        status, _, corpo = self._request('GET', '/sobre-nos')
        self.assertEqual(200, status)
        pagina = corpo.decode()
        for nome in ('Erick Santos Barbosa', 'Gabriel Agustín Fernández Alves', 'Pedro Henrique Harada Pecegueiro'):
            self.assertIn(nome, pagina)
        self.assertNotIn('<details', pagina)
        self.assertIn('href="/sobre-nos" aria-current="page"', pagina)
        self.assertIn('href="/"', pagina)
        self.assertIn('href="mailto:jurishome2026@gmail.com"', pagina)

    def test_validacao_mensagem_novo_acesso_e_revogacao_administrativa(self):
        usuario = self._usuario()
        antigo = criar_access_token(usuario)
        novo = criar_access_token(usuario)
        status, headers, corpo = self._request('GET', '/api/usuarios/me', token=antigo)
        self.assertEqual(401, status)
        self.assertEqual('novo_acesso', headers['x-session-reason'])
        self.assertIn('novo acesso', json.loads(corpo)['detail'])
        self.assertEqual(200, self._request('GET', '/api/usuarios/me', token=novo)[0])
        status, headers, _ = self._request('GET', '/perfil', cookie='jurishome_access_token='+antigo)
        self.assertEqual(303, status)
        self.assertEqual('/?sessao=substituida', headers['location'])
        usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        status, headers, _ = self._request('GET', '/api/usuarios/me', token=antigo)
        self.assertEqual(401, status)
        self.assertNotIn('x-session-reason', headers)

    def test_validacao_email_completo_somente_no_perfil_administrativo(self):
        leitor = self._usuario(email='leitor-contato@example.test')
        suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        self.db.commit()
        token = criar_access_token(suporte)
        status, _, corpo = self._request('GET', '/api/admin/usuarios', token=token)
        self.assertEqual(200, status)
        self.assertNotIn(leitor.email, corpo.decode())
        url = '/admin/usuarios/'+leitor.uuid
        status, headers, corpo = self._request('GET', url, token=token)
        self.assertEqual(200, status)
        self.assertIn(leitor.email, corpo.decode())
        self.assertNotIn('<details', corpo.decode())
        self.assertIn('no-store', headers['cache-control'])
        self.assertEqual(1, self.db.query(models.LogAuditoria).filter_by(acao='dados_usuario_consultados').count())
        self.assertEqual(404, self._request('GET', url, token=criar_access_token(leitor))[0])
        self.assertEqual(404, self._request('GET', url)[0])
        token_root = criar_access_token(root)
        status, _, corpo = self._request('GET', '/admin/administradores/'+suporte.uuid, token=token_root)
        self.assertEqual(200, status)
        self.assertIn(suporte.email, corpo.decode())

    def test_validacao_presenca_avisa_sobre_nova_versao_legal(self):
        from services.lgpd import revisao_vigente, versao_legal
        leitor = self._usuario()
        versao = versao_legal(revisao_vigente(self.db))
        leitor.versao_termos = versao
        self.db.commit()
        token = criar_access_token(leitor)
        cookie = 'jurishome_access_token='+token
        origem = ((b'origin', b'http://testserver'),)
        status, headers, _ = self._request('POST', '/api/auth/presenca', cookie=cookie, extra_headers=origem)
        self.assertEqual(204, status)
        self.assertNotIn('x-legal-acceptance', headers)
        self.db.add(models.RevisaoLegal(anterior=versao, termos='Novo termo', politica='Nova política', publicada_em=datetime.now(timezone.utc).replace(tzinfo=None)))
        self.db.commit()
        status, headers, _ = self._request('POST', '/api/auth/presenca', cookie=cookie, extra_headers=origem)
        self.assertEqual(204, status)
        self.assertEqual('required', headers['x-legal-acceptance'])
        self.assertEqual(428, self._request('GET', '/api/usuarios/me', token=token)[0])

    def test_validacao_interface_recuperacao_e_perfil_sem_historico(self):
        status, _, corpo = self._request('GET', '/problemas-acesso')
        self.assertEqual(200, status)
        self.assertIn('data-password-toggle="reset-2fa-senha"', corpo.decode())
        self.assertNotIn('<details', corpo.decode())
        self.assertIn('access-help-card', corpo.decode())
        self.assertIn('/static/css/problemas-acesso.css?', corpo.decode())
        status, _, corpo = self._request('GET', '/2fatores')
        self.assertEqual(200, status)
        self.assertNotIn('Perdeu o acesso ao autenticador?', corpo.decode())
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        status, _, corpo = self._request('GET', '/perfil', token=criar_access_token(admin))
        self.assertEqual(200, status)
        self.assertNotIn('Histórico de aceite dos documentos', corpo.decode())
        self.assertIn('Versão dos documentos', corpo.decode())

    def test_validacao_recuperacao_limita_envios_e_nao_duplica_pedido(self):
        usuario = self._usuario()
        dados = {'email':usuario.email, 'senha':'SenhaSegura123!'}
        self.assertEqual(200, self._request('POST','/api/solicitar-reset-2fa', dados)[0])
        status, headers, _ = self._request('POST','/api/solicitar-reset-2fa', dados)
        self.assertEqual(429, status)
        self.assertGreater(int(headers['retry-after']), 0)
        with patch('services.limites_operacoes.agora', return_value=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(minutes=2)):
            status, _, corpo = self._request('POST','/api/solicitar-reset-2fa', dados)
        self.assertEqual(200, status)
        self.assertTrue(json.loads(corpo)['em_andamento'])
        self.assertEqual(1, self.db.query(models.FeedbackAtendimento).count())

    def test_cadastro_limite_por_origem_e_penalidade_persistente(self):
        dados = {'nome': 'João', 'sobrenome': 'Silva', 'interesse': 'Direito Civil',
                 'email': 'primeiro@example.test', 'senha': 'NovaSenha!123',
                 'confirmar_senha': 'NovaSenha!123', 'consentimento_lgpd': True}
        from services.lgpd import revisao_vigente, versao_legal
        dados['versao_documentos'] = versao_legal(revisao_vigente(self.db))
        status, _, _ = self._request('POST', '/api/auth/cadastro', dados, cliente='198.51.100.5')
        self.assertEqual(status, 201)

        for tentativa in range(1, 4):
            status, headers, corpo = self._request('POST', '/api/auth/cadastro',
                {**dados, 'email': f'outro{tentativa}@example.test'}, cliente='198.51.100.5')
            self.assertEqual(status, 429)
            if tentativa == 3:
                self.assertGreaterEqual(int(headers['retry-after']), 3599)
                self.assertIn('uma hora', json.loads(corpo)['detail'])
        status, _, _ = self._request('POST', '/api/auth/cadastro',
            {**dados, 'email': 'outra-rede@example.test'}, cliente='198.51.100.6')
        self.assertEqual(status, 201)
        registro = self.db.query(models.LimiteOperacao).filter(models.LimiteOperacao.bloqueado_ate.isnot(None)).one()
        registro.bloqueado_ate = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        registro.proxima_em = registro.bloqueado_ate
        self.db.commit()
        status, _, _ = self._request('POST', '/api/auth/cadastro',
            {**dados, 'email': 'liberado@example.test'}, cliente='198.51.100.5')
        self.assertEqual(status, 201)


    def test_cadastros_simultaneos_nao_contornam_espera(self):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from threading import Barrier
        from fastapi import HTTPException
        from starlette.requests import Request
        from services import limites_operacoes

        with TemporaryDirectory() as pasta:
            engine = create_engine('sqlite:///' + str(Path(pasta) / 'concorrencia.db'), connect_args={'timeout': 10})
            models.LimiteOperacao.__table__.create(engine)
            sessoes = sessionmaker(bind=engine)
            inicio = Barrier(2)
            def tentar():
                with sessoes() as db:
                    request = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [], 'client': ('198.51.100.2', 12)})
                    inicio.wait()
                    try:
                        registro = limites_operacoes.verificar_cadastro(db, request)
                        limites_operacoes.concluir(registro, 5)
                        db.commit()
                        return 201
                    except HTTPException as erro:
                        return erro.status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(lambda _: tentar(), range(2))), [201, 429])
            engine.dispose()

    def test_materia_limite_individual_de_quinze_minutos(self):
        primeiro = self._usuario(TipoUsuario.ADMINISTRADOR)
        segundo = self._usuario(TipoUsuario.ADMINISTRADOR)
        categoria = models.Categoria(nome='Direito Civil')
        self.db.add(categoria)
        self.db.commit()
        dados = {'titulo': 'Matéria de teste', 'corpo_texto': 'Texto de teste',
                 'categoria_id': categoria.uuid, 'aceite_editorial': True, 'versao_termos': '2026-10-30'}
        token1, token2 = criar_access_token(primeiro), criar_access_token(segundo)
        self.assertEqual(self._request('POST', '/criar-materia', dados, token=token1)[0], 200)
        status, headers, _ = self._request('POST', '/criar-materia', dados, token=token1)
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers['retry-after']), 899)
        self.assertEqual(self._request('POST', '/criar-materia', dados, token=token2)[0], 200)
        registro = self.db.query(models.LimiteOperacao).filter_by(chave=__import__('services.tentativas_auth', fromlist=['chave']).chave('operacao-materia', primeiro.uuid)).one()
        registro.proxima_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self._request('POST', '/criar-materia', dados, token=token1)[0], 200)

    def test_pedido_2fa_vai_para_feedback_e_resolucao_exige_nova_configuracao(self):
        leitor = self._usuario(email='leitor-2fa@example.test')
        suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
        dados = {'email': leitor.email, 'senha': 'SenhaSegura123!'}
        self.assertEqual(self._request('POST', '/api/solicitar-reset-2fa', {**dados, 'senha': 'Errada123!'})[0], 401)
        self.assertEqual(self.db.query(models.FeedbackAtendimento).count(), 0)
        status, _, corpo = self._request('POST', '/api/solicitar-reset-2fa', dados)
        self.assertEqual(status, 200)
        self.assertIn('administradores', json.loads(corpo)['mensagem'])
        self.assertEqual(self._request('POST', '/api/solicitar-reset-2fa', dados)[0], 429)
        self.assertEqual(self.db.query(models.FeedbackAtendimento).count(), 1)
        token = criar_access_token(suporte)
        status, _, corpo = self._request('GET', '/api/admin/usuarios', token=token)
        self.assertTrue(next(item for item in json.loads(corpo) if item['uuid'] == leitor.uuid)['solicitou_ajuda'])
        self.assertEqual(self._request('POST', '/api/admin/resetar-2fa/' + leitor.uuid, token=token)[0], 200)
        self.db.expire_all()
        self.assertFalse(self.db.get(Usuario, leitor.uuid).is_2fa_enabled)
        self.assertEqual(self.db.query(models.FeedbackAtendimento).one().status, 'Resolvido')
        status, _, corpo = self._request('POST', '/api/auth/login', dados)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(corpo)['requer_configuracao_2fa'])

    def test_recuperacao_2fa_com_banco_de_feedback_separado(self):
        from routes.auth import PedidoReset2FA, solicitar_reset_2fa
        from routes.admin import listar_usuarios_filtro, resetar_2fa
        from starlette.requests import Request

        feedback_engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        models.FeedbackAtendimento.__table__.create(feedback_engine)
        feedback = sessionmaker(bind=feedback_engine)()
        try:
            leitor = self._usuario(email='separado@example.test')
            suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
            request = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [], 'client': ('198.51.100.9', 12)})
            solicitar_reset_2fa(PedidoReset2FA(email=leitor.email, senha='SenhaSegura123!'),
                                 db=self.db, request=request, feedback_db=feedback)
            self.assertEqual(feedback.query(models.FeedbackAtendimento).count(), 1)
            self.assertEqual(self.db.query(models.FeedbackAtendimento).count(), 0)
            usuarios = listar_usuarios_filtro(tipo=None, db=self.db, usuario_logado=suporte, feedback_db=feedback)
            self.assertTrue(next(u for u in usuarios if u['uuid'] == leitor.uuid)['solicitou_ajuda'])
            resetar_2fa(leitor.uuid, db=self.db, usuario_logado=suporte, feedback_db=feedback)
            self.assertEqual(feedback.query(models.FeedbackAtendimento).one().status, 'Resolvido')
            self.assertFalse(self.db.get(Usuario, leitor.uuid).is_2fa_enabled)
        finally:
            feedback.close()
            feedback_engine.dispose()

    def test_documentacao_exclusiva_do_administrador_principal(self):
        leitor = self._usuario()
        suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        self.db.commit()

        for token in (None, criar_access_token(leitor), criar_access_token(suporte)):
            for caminho in ("/docs", "/openapi.json"):
                with self.subTest(autenticado=token is not None, caminho=caminho):
                    status, _, _ = self._request("GET", caminho, token=token)
                    self.assertEqual(status, 404)

        token = criar_access_token(root)
        status, headers, corpo = self._request("GET", "/docs", token=token)
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["cache-control"])
        self.assertIn(b"/openapi.json", corpo)
        status, headers, corpo = self._request("GET", "/openapi.json", token=token)
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["cache-control"])
        self.assertIn("/api/auth/login", json.loads(corpo)["paths"])
        for caminho in ("/redoc", "/docs/oauth2-redirect"):
            status, _, _ = self._request("GET", caminho, token=token)
            self.assertEqual(status, 404)

    def test_home_curiosidades_respeita_perfil_e_autenticacao(self):
        aluno = self._usuario()
        token = criar_access_token(aluno)
        status, _, corpo = self._request("GET", "/home_usuario", token=token)
        self.assertEqual(status, 200)
        self.assertIn('href="/curiosidades"', corpo.decode())
        self.assertIn('href="/juridle"', corpo.decode())
        self.assertIn("Canto recreativo", corpo.decode())
        self.assertNotIn('href="/nova-materia"', corpo.decode())
        status, _, corpo = self._request("GET", "/juridle", token=token)
        self.assertEqual(status, 200)
        self.assertIn("quatro alternativas", corpo.decode())
        self.assertNotIn('href="/admin/auditoria"', corpo.decode())
        status, _, _ = self._request("GET", "/juridle")
        self.assertNotEqual(status, 200)
        status, _, corpo = self._request("GET", "/curiosidades", token=token)
        self.assertEqual(status, 200)
        self.assertIn("Habeas corpus", corpo.decode())
        self.assertNotIn('href="/admin/auditoria"', corpo.decode())
        status, _, _ = self._request("GET", "/curiosidades")
        self.assertNotEqual(status, 200)

    def test_catalogo_publico_categorias_expoe_somente_uuid_nome(self):
        categoria = models.Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        self.db.add(categoria)
        self.db.commit()
        status, _, corpo = self._request("GET", "/api/categorias")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(corpo), [{"uuid": categoria.uuid, "nome": "Direito Civil"}])

    def test_separacao_das_homes_e_configuracoes_por_perfil(self):
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        for caminho in ('/home_usuario', '/home_Usuario.html', '/templates/home_Usuario.html'):
            status, headers, _ = self._request('GET', caminho, token=token)
            self.assertEqual(status, 404)
            self.assertNotIn('location', headers)
        status, headers, _ = self._request('GET', '/configuracoes-usuario', token=token)
        self.assertEqual(status, 404)
        leitor = self._usuario()
        status, _, _ = self._request('GET', '/home_admin', token=criar_access_token(leitor))
        self.assertEqual(status, 404)

    def test_cadastro_admin_restrito_sem_escalada_ou_senha_na_resposta(self):
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        dados = {'nome': 'Suporte de teste', 'email': 'SUPORTE@example.test', 'senha': 'SenhaSegura123!'}
        status, _, _ = self._request('POST', '/api/admin/criar-admin', dados, token=token)
        self.assertEqual(status, 403)
        admin.e_root_admin = True
        self.db.commit()
        status, _, corpo = self._request('POST', '/api/admin/criar-admin', dados, token=token)
        self.assertEqual(status, 201)
        self.assertNotIn(dados['senha'].encode(), corpo)
        novo = self.db.query(Usuario).filter_by(email='suporte@example.test').one()
        self.assertFalse(novo.e_root_admin)
        self.assertFalse(novo.is_2fa_enabled)
        self.assertTrue(verificar_senha(dados['senha'], novo.senha_hash))
        status, _, _ = self._request('POST', '/api/admin/criar-admin', dados, token=token)
        self.assertEqual(status, 409)
        status, _, _ = self._request('POST', '/api/admin/criar-admin', {**dados, 'e_root_admin': True}, token=token)
        self.assertEqual(status, 422)
        status, _, _ = self._request('POST', '/api/admin/criar-admin', {**dados, 'email': 'invalido'}, token=token)
        self.assertEqual(status, 422)

    def test_juridle_gabarito_privado_retomada_uso_unico_e_rodada_perfeita(self):
        jogador = self._usuario()
        token = criar_access_token(jogador)
        status, _, corpo = self._request('POST', '/api/juridle/rodadas', {}, token=token)
        self.assertEqual(status, 200)
        rodada = json.loads(corpo)['rodada']
        self.assertEqual(set(rodada['pergunta']), {'enunciado', 'definicao', 'opcoes'})
        self.assertEqual(len(rodada['pergunta']['opcoes']), 4)
        status, _, retomada = self._request('POST', '/api/juridle/rodadas', {}, token=token)
        self.assertEqual(json.loads(retomada)['rodada']['uuid'], rodada['uuid'])
        registro = self.db.get(models.JuridleRodada, rodada['uuid'])
        gabarito = json.loads(registro.perguntas_json)
        outro = self._usuario()
        caminho = '/api/juridle/rodadas/' + rodada['uuid'] + '/respostas'
        status, _, _ = self._request('POST', caminho, {'pergunta': 0, 'opcao': 0}, token=criar_access_token(outro))
        self.assertEqual(status, 404)
        status, _, _ = self._request('POST', caminho, {'pergunta': 1, 'opcao': 0}, token=token)
        self.assertEqual(status, 409)
        for i in range(5):
            dados = {'pergunta': i, 'opcao': gabarito[i]['correta']}
            status, _, resposta = self._request('POST', caminho, dados, token=token)
            self.assertEqual(status, 200)
            status, _, repetida = self._request('POST', caminho, dados, token=token)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(resposta)['progresso'], json.loads(repetida)['progresso'])
        final = json.loads(resposta)
        self.assertTrue(final['rodada']['coroa'])
        self.assertEqual(final['progresso']['sequencia'], 5)
        self.assertEqual(final['progresso']['frequencia'], 1)
        self.assertEqual(final['progresso']['coroas'], 1)
        status, _, _ = self._request('POST', caminho, {'pergunta': 0, 'opcao': (gabarito[0]['correta']+1)%4}, token=token)
        self.assertEqual(status, 409)
        status, _, _ = self._request('POST', caminho, {'pergunta': 0, 'opcao': True}, token=token)
        self.assertEqual(status, 422)

    def test_juridle_erro_zera_sequencia_e_rodada_expirada_nao_aceita_resposta(self):
        from services import juridle
        jogador = self._usuario()
        rodada = juridle.iniciar(self.db, jogador.uuid)
        perguntas = json.loads(rodada.perguntas_json)
        juridle.responder(self.db, jogador.uuid, rodada.uuid, 0, perguntas[0]['correta'])
        juridle.responder(self.db, jogador.uuid, rodada.uuid, 1, (perguntas[1]['correta']+1)%4)
        self.assertEqual(juridle.progresso(self.db, jogador.uuid)['sequencia'], 0)
        self.assertEqual(juridle.progresso(self.db, jogador.uuid)['melhorSequencia'], 1)
        rodada.expira_em = juridle.agora() - timedelta(seconds=1)
        self.db.commit()
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as erro:
            juridle.responder(self.db, jogador.uuid, rodada.uuid, 2, 0)
        self.assertEqual(erro.exception.status_code, 409)
        nova = juridle.iniciar(self.db, jogador.uuid)
        self.assertEqual(nova.uuid, rodada.uuid)  # Não libera outra rodada no mesmo dia.

    def test_feedback_complemento_pertence_ao_autor_e_reabre_fila(self):
        leitor = self._usuario()
        token = criar_access_token(leitor)
        dados = {'tipo': 'Sugestão', 'assunto': 'Minha sugestão', 'mensagem': 'Uma melhoria para a plataforma.'}
        status, _, corpo = self._request('POST', '/api/feedbacks', dados, token=token)
        self.assertEqual(status, 201)
        original = json.loads(corpo)
        status, _, duplicado = self._request('POST', '/api/feedbacks', dados, token=token)
        self.assertEqual(json.loads(duplicado)['id'], original['id'])
        caminho = '/api/feedbacks/' + original['id'] + '/mensagens'
        outro = self._usuario()
        status, _, _ = self._request('POST', caminho, {'mensagem': 'Complemento privado', 'atualizadoEm': original['atualizadoEm']}, token=criar_access_token(outro))
        self.assertEqual(status, 404)
        status, _, corpo = self._request('POST', caminho, {'mensagem': 'Complemento do autor', 'atualizadoEm': original['atualizadoEm']}, token=token)
        self.assertEqual(status, 200)
        d = json.loads(corpo)
        self.assertEqual(d['status'], 'Em análise')
        self.assertTrue(d['novo'])
        self.assertNotIn('observacoesInternas', d)
        self.assertEqual(d['respostas'][-1]['papel'], 'leitor')
        self._request('POST', caminho, {'mensagem': 'Complemento do autor', 'atualizadoEm': d['atualizadoEm']}, token=token)
        self.db.expire_all()
        self.assertEqual(len(json.loads(self.db.get(models.FeedbackAtendimento, original['id']).respostas_json)), 1)
        for i in range(4):
            status, _, _ = self._request('POST', '/api/feedbacks', {**dados, 'assunto': f'Sugestão número {i}'}, token=token)
            self.assertEqual(status, 201)
        status, _, _ = self._request('POST', '/api/feedbacks', {**dados, 'assunto': 'Mais uma sugestão'}, token=token)
        self.assertEqual(status, 429)

    def test_perfil_persiste_instituicao_interesse_e_mostra_data_real(self):
        from routes.perfil import atualizar_perfil
        leitor = self._usuario()
        atualizar_perfil(nome='Leitor atualizado', faculdade='Universidade de teste', interesse='Direito Civil', avatar_id='oceano', versao=leitor.atualizado_em.isoformat(), db=self.db, usuario=leitor)
        self.db.refresh(leitor)
        self.assertEqual(leitor.universidade, 'Universidade de teste')
        self.assertEqual(leitor.especialidade_juridica, 'Direito Civil')
        self.assertEqual(leitor.foto_perfil, '/static/images/avatares/oceano.svg')
        status, _, corpo = self._request('GET', '/perfil', token=criar_access_token(leitor))
        self.assertEqual(status, 200)
        self.assertIn(b'Universidade de teste', corpo)
        self.assertNotIn(b'17/12/2025', corpo)

    def test_em_alta_conta_leitor_uma_vez_por_dia_e_nao_conta_admin(self):
        categoria = models.Categoria(nome='Direito Civil')
        autor = self._usuario(TipoUsuario.ADMINISTRADOR)
        self.db.add(categoria)
        self.db.flush()
        materia = models.Conteudo(titulo='Artigo de teste', resumo_home='Resumo de teste.', corpo_texto='Conteúdo de teste.', categoria_id=categoria.uuid,
                                  autor_id=autor.uuid, status=models.StatusConteudo.APROVADO)
        self.db.add(materia)
        self.db.commit()
        token_admin = criar_access_token(autor)
        self._request('GET', '/materia/'+materia.uuid, token=token_admin)
        leitor = self._usuario()
        token = criar_access_token(leitor)
        for _ in range(2):
            status, _, _ = self._request('GET', '/materia/'+materia.uuid, token=token)
            self.assertEqual(status, 200)
        status, _, corpo = self._request('GET', '/api/conteudos/em-alta', token=token)
        self.assertEqual(status, 200)
        lista = json.loads(corpo)
        self.assertEqual(lista[0]['leituras'], 1)
        self.assertNotIn('usuario_id', lista[0])
        status, _, corpo = self._request('GET', '/conhecimento', token=token)
        self.assertEqual(status, 200)
        self.assertNotIn(b'href="/admin/auditoria"', corpo)

    def test_juridle_duas_abas_nao_criam_rodadas_ou_pontos_duplicados(self):
        from concurrent.futures import ThreadPoolExecutor
        from tempfile import TemporaryDirectory
        from threading import Barrier
        from pathlib import Path
        from services import juridle
        with TemporaryDirectory() as pasta:
            engine = create_engine('sqlite:///' + (Path(pasta) / 'concorrencia.db').as_posix(), connect_args={'check_same_thread': False})
            try:
                Base.metadata.create_all(engine)
                fabrica = sessionmaker(bind=engine)
                with fabrica() as db:
                    juridle.garantir_banco_inicial(db)
                with fabrica() as db:
                    u = Usuario(nome='Jogador', email='jogador@example.test', tipo_usuario=TipoUsuario.ESTUDANTE)
                    db.add(u)
                    db.commit()
                    usuario_id = u.uuid
                barreira = Barrier(2)
                def iniciar():
                    with fabrica() as db:
                        barreira.wait(timeout=10)
                        return juridle.iniciar(db, usuario_id).uuid
                with ThreadPoolExecutor(max_workers=2) as executor:
                    ids = list(executor.map(lambda _: iniciar(), range(2)))
                self.assertEqual(ids[0], ids[1])
                with fabrica() as db:
                    rodada = db.get(models.JuridleRodada, ids[0])
                    correta = json.loads(rodada.perguntas_json)[0]['correta']
                barreira = Barrier(2)
                def responder():
                    with fabrica() as db:
                        barreira.wait(timeout=10)
                        return juridle.responder(db, usuario_id, ids[0], 0, correta)[0].respondidas
                with ThreadPoolExecutor(max_workers=2) as executor:
                    contagens = list(executor.map(lambda _: responder(), range(2)))
                self.assertEqual(contagens, [1, 1])
                with fabrica() as db:
                    self.assertEqual(juridle.progresso(db, usuario_id)['acertos'], 1)
            finally:
                engine.dispose()

    def test_juridle_frequencia_dias_consecutivos_e_nivel_sem_ranking(self):
        from services import juridle
        jogador = self._usuario()
        hoje = datetime.now(juridle.FUSO).date()
        for dias in (3, 1, 0):
            data = datetime.combine(hoje - timedelta(days=dias), datetime.min.time()).replace(hour=12, tzinfo=juridle.FUSO).astimezone(timezone.utc).replace(tzinfo=None)
            self.db.add(models.JuridleRodada(usuario_id=jogador.uuid, perguntas_json='[]', respostas_json=json.dumps([{'acertou': True}]*5),
                                           respondidas=5, criada_em=data, expira_em=data+timedelta(days=1), concluida_em=data))
        self.db.commit()
        progresso = juridle.progresso(self.db, jogador.uuid)
        self.assertEqual(progresso['frequencia'], 2)
        self.assertEqual(progresso['nivel'], 2)
        self.assertEqual(progresso['coroas'], 3)
        self.assertEqual(progresso['acertos'], 15)

    def test_manutencao_admin_exclusiva_root_e_conta_principal_protegida(self):
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        alvo = self._usuario(TipoUsuario.ADMINISTRADOR)
        leitor = self._usuario()
        self.db.commit()
        token_root = criar_access_token(root)
        caminho = '/api/admin/administradores/' + alvo.uuid
        for pessoa in (alvo, leitor):
            token = criar_access_token(pessoa)
            for metodo in ('GET', 'PUT', 'DELETE'):
                status, _, _ = self._request(metodo, caminho, {} if metodo != 'GET' else None, token=token)
                self.assertEqual(status, 403)
            status, _, _ = self._request('GET', '/admin/administradores/'+alvo.uuid, token=token)
            self.assertEqual(status, 404)
        status, _, _ = self._request('GET', '/api/admin/administradores/'+root.uuid, token=token_root)
        self.assertEqual(status, 403)
        status, _, _ = self._request('DELETE', '/api/admin/administradores/'+root.uuid, {'nome_confirmacao': root.nome}, token=token_root)
        self.assertEqual(status, 403)
        status, _, _ = self._request('GET', '/api/admin/administradores/'+leitor.uuid, token=token_root)
        self.assertEqual(status, 404)
        status, headers, corpo = self._request('GET', caminho, token=token_root)
        self.assertEqual(status, 200)
        self.assertIn('no-store', headers['cache-control'])
        self.assertNotIn('senha_hash', json.loads(corpo))
        self.assertNotIn('totp_secret', json.loads(corpo))
        status, _, corpo = self._request('GET', '/admin/administradores/'+alvo.uuid, token=token_root)
        self.assertEqual(status, 200)
        self.assertIn(b'admin-perfil-form', corpo)

    def test_editar_admin_preserva_seguranca_e_revoga_sessoes_quando_solicitado(self):
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        alvo = self._usuario(TipoUsuario.ADMINISTRADOR)
        self.db.commit()
        token_root, token_alvo = criar_access_token(root), criar_access_token(alvo)
        caminho = '/api/admin/administradores/'+alvo.uuid
        _, _, corpo = self._request('GET', caminho, token=token_root)
        atual = json.loads(corpo)
        antiga_senha, antigo_totp = alvo.senha_hash, alvo.totp_secret
        dados = {'nome': 'Nome atualizado', 'email': alvo.email, 'versao': atual['versao']}
        status, _, corpo = self._request('PUT', caminho, dados, token=token_root)
        self.assertEqual(status, 200)
        self.db.expire_all()
        self.assertEqual(alvo.senha_hash, antiga_senha)
        self.assertEqual(alvo.totp_secret, antigo_totp)
        status, _, _ = self._request('PUT', caminho, dados, token=token_root)
        self.assertEqual(status, 409)
        novo = json.loads(corpo)['administrador']
        dados.update(versao=novo['versao'], email='NOVO_ADMIN@example.test', nova_senha='NovaSenhaSegura123!', resetar_2fa=True)
        status, _, corpo = self._request('PUT', caminho, dados, token=token_root)
        self.assertEqual(status, 200)
        self.db.expire_all()
        self.assertEqual(alvo.email, 'novo_admin@example.test')
        self.assertTrue(verificar_senha('NovaSenhaSegura123!', alvo.senha_hash))
        self.assertIsNone(alvo.totp_secret)
        self.assertFalse(alvo.is_2fa_enabled)
        self.assertEqual(json.loads(corpo)['administrador']['sessoesAtivas'], 0)
        status, _, _ = self._request('GET', '/api/usuarios/me', token=token_alvo)
        self.assertEqual(status, 401)
        status, _, _ = self._request('GET', '/api/usuarios/me', token=token_root)
        self.assertEqual(status, 200)
        logs = self.db.query(models.LogAuditoria).filter_by(acao='administrador_atualizado').all()
        self.assertEqual(len(logs), 2)
        self.assertNotIn('NovaSenhaSegura123!', ''.join(l.detalhes_json for l in logs))

    def test_manutencao_admin_rejeita_email_duplicado_e_elevacao_de_permissao(self):
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        alvo = self._usuario(TipoUsuario.ADMINISTRADOR)
        self.db.commit()
        token = criar_access_token(root)
        caminho = '/api/admin/administradores/'+alvo.uuid
        _, _, corpo = self._request('GET', caminho, token=token)
        dados = {'nome': alvo.nome, 'email': root.email, 'versao': json.loads(corpo)['versao']}
        status, _, _ = self._request('PUT', caminho, dados, token=token)
        self.assertEqual(status, 409)
        status, _, _ = self._request('PUT', caminho, {**dados, 'email': alvo.email, 'e_root_admin': True}, token=token)
        self.assertEqual(status, 422)
        status, _, _ = self._request('PUT', caminho, {**dados, 'email': alvo.email, 'nova_senha': '12345678'}, token=token)
        self.assertEqual(status, 422)
        self.db.refresh(alvo)
        self.assertFalse(alvo.e_root_admin)

    def test_excluir_admin_exige_nome_e_preserva_materias_sem_acesso(self):
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        alvo = self._usuario(TipoUsuario.ADMINISTRADOR)
        alvo.nome = 'JOAO VINICIOS'
        categoria = models.Categoria(nome='Direito Civil')
        self.db.add(categoria)
        self.db.flush()
        materia = models.Conteudo(titulo='Matéria preservada', resumo_home='Resumo preservado', corpo_texto='Texto preservado',
                                  categoria_id=categoria.uuid, autor_id=alvo.uuid,
                                  status=models.StatusConteudo.APROVADO)
        self.db.add(materia)
        self.db.commit()
        alvo_id, materia_id = alvo.uuid, materia.uuid
        token_root, token_alvo = criar_access_token(root), criar_access_token(alvo)
        caminho = '/api/admin/administradores/'+alvo.uuid
        status, _, _ = self._request('DELETE', caminho, {'nome_confirmacao': 'joao vinicios'}, token=token_root)
        self.assertEqual(status, 422)
        self.assertIsNone(self.db.get(models.AdministradorExcluido, alvo_id))
        status, _, _ = self._request('DELETE', caminho, {'nome_confirmacao': 'JOAO VINICIOS'}, token=token_root)
        self.assertEqual(status, 200)
        self.db.expire_all()
        self.assertIsNotNone(self.db.get(models.AdministradorExcluido, alvo_id))
        removido = self.db.get(Usuario, alvo_id)
        self.assertIsNone(removido.senha_hash)
        self.assertIsNone(removido.totp_secret)
        self.assertEqual(self.db.get(models.Conteudo, materia_id).autor_id, alvo_id)
        status, _, corpo = self._request('GET', '/api/admin/usuarios', token=token_root)
        self.assertNotIn(alvo_id, [u['uuid'] for u in json.loads(corpo)])
        status, _, _ = self._request('GET', '/api/usuarios/me', token=token_alvo)
        self.assertEqual(status, 401)
        status, _, _ = self._request('GET', caminho, token=token_root)
        self.assertEqual(status, 404)
        log = self.db.query(models.LogAuditoria).filter_by(acao='administrador_excluido').one()
        self.assertEqual(log.usuario_id, root.uuid)
        self.assertEqual(log.recurso_id, alvo_id)

    def test_acesso_root_bloqueado_se_banco_legado_contiver_duplicidade(self):
        from sqlalchemy import text
        self.db.execute(text('DROP INDEX uq_usuarios_root_unico'))
        self.db.commit()
        primeiro = self._usuario(TipoUsuario.ADMINISTRADOR)
        segundo = self._usuario(TipoUsuario.ADMINISTRADOR)
        primeiro.e_root_admin = segundo.e_root_admin = True
        self.db.commit()
        status, _, _ = self._request('GET', '/api/usuarios/me', token=criar_access_token(primeiro))
        self.assertEqual(status, 403)

    def test_hsts_usa_dominio_publico_https_mesmo_atras_do_proxy(self):
        cabecalho = "strict-transport-security"
        with patch.dict(os.environ, {"PUBLIC_ORIGIN": "https://testserver"}):
            for caminho, esperado in (("/", 200), ("/endereco-inexistente-hsts", 404)):
                status, headers, _ = self._request("GET", caminho)
                self.assertEqual(esperado, status)
                self.assertEqual("max-age=31536000", headers[cabecalho])
        for origem in ("", "http://testserver", "https://outro.example"):
            with patch.dict(os.environ, {"PUBLIC_ORIGIN": origem}):
                _, headers, _ = self._request(
                    "GET", "/", extra_headers=((b"x-forwarded-proto", b"https"),)
                )
                self.assertNotIn(cabecalho, headers)

    def test_erros_html_explica_codigos_e_nao_expoe_detalhes(self):
        status, headers, corpo = self._request('GET', '/endereco-que-nao-existe')
        self.assertEqual(status, 404)
        self.assertIn('text/html', headers['content-type'])
        self.assertIn('no-store', headers['cache-control'])
        self.assertIn('Não encontramos esta página', corpo.decode())
        for codigo in (400, 404, 405, 422, 429, 500, 502, 503, 504, 505):
            status, headers, corpo = self._request('GET', f'/erro/{codigo}')
            self.assertEqual(status, codigo)
            self.assertIn('O que você pode fazer', corpo.decode())
            self.assertNotIn(b'Traceback', corpo)
        status, _, _ = self._request('GET', '/erro/200')
        self.assertEqual(status, 404)
        status, headers, corpo = self._request('GET', '/api/endereco-inexistente')
        self.assertEqual(status, 404)
        self.assertIn('application/json', headers['content-type'])
        self.assertIn('detail', json.loads(corpo))

    def test_falha_inesperada_recebe_pagina_500_ou_json_sem_vazar_erro(self):
        from fastapi import APIRouter
        roteador = APIRouter()
        @roteador.get('/_teste-falha-interna')
        @roteador.get('/api/_teste-falha-interna')
        def falhar():
            raise RuntimeError('senha=SEGREDO_DO_TESTE SQL SELECT interno')
        self.app.include_router(roteador)
        try:
            for caminho in ('/_teste-falha-interna', '/api/_teste-falha-interna'):
                status, headers, corpo = self._request('GET', caminho, suprimir_erro_interno=True)
                self.assertEqual(status, 500)
                self.assertIn('no-store', headers['cache-control'])
                self.assertNotIn(b'SEGREDO_DO_TESTE', corpo)
                self.assertNotIn(b'SELECT', corpo)
                self.assertNotIn(b'RuntimeError', corpo)
                self.assertIn('x-correlation-id', headers)
                if caminho.startswith('/api/'):
                    self.assertIn('application/json', headers['content-type'])
                    self.assertIn('referencia', json.loads(corpo))
                else:
                    self.assertIn('text/html', headers['content-type'])
                    self.assertIn(b'error-title', corpo)
        finally:
            self.app.router.routes[:] = [r for r in self.app.router.routes if getattr(r, 'path', '') not in {'/_teste-falha-interna', '/api/_teste-falha-interna'}]

    def test_editor_etapas_persiste_formatacao_creditos_e_titulo_home(self):
        from io import BytesIO
        from PIL import Image
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        categoria = models.Categoria(nome='Direito Civil')
        self.db.add(categoria)
        self.db.commit()
        arquivo = BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(arquivo, 'PNG')
        imagem = 'data:image/png;base64,' + base64.b64encode(arquivo.getvalue()).decode()
        fonte_longa = 'https://www.exemplo.test/imagens/' + 'caminho-'*30 + '?origem=arquivo'
        dados = {'titulo': 'Título de leitura', 'corpo_texto': '## Uma seção\nTexto **importante** e _explicação_.\n> Uma citação\n- Um item\n<script>alert(1)</script>',
                 'categoria_id': categoria.uuid, 'imagem_miniatura': imagem,
                 'imagem_corpo': imagem, 'fonte_imagem': fonte_longa,
                 'editorial': {'titulo_home': 'Chamada na Home', 'formatado': True, 'alinhamento': 'justificado',
                               'capa_legenda': 'Legenda da capa', 'imagens': [{'fonte': fonte_longa, 'legenda': 'Imagem de apoio',
                                'alt': 'Uma ilustração de teste', 'apos_bloco': 2, 'largura': 'normal'}]}}
        status, _, preview = self._request('POST', '/api/admin/materias/preview', dados, token=token)
        self.assertEqual(status, 200)
        self.assertIn(b'<strong>importante</strong>', preview)
        self.assertIn(b'&lt;script&gt;', preview)
        self.assertNotIn(b'<script>alert', preview)
        self.assertEqual(self.db.query(models.Conteudo).count(), 0)
        for aceite in ({}, {'aceite_editorial': False, 'versao_termos': '2026-10-30'}, {'aceite_editorial': True, 'versao_termos': 'antiga'}, {'aceite_editorial': 'true', 'versao_termos': '2026-10-30'}):
            status, _, _ = self._request('POST', '/criar-materia', {**dados, **aceite}, token=token)
            self.assertEqual(status, 422)
        self.assertEqual(self.db.query(models.Conteudo).count(), 0)
        dados.update(aceite_editorial=True, versao_termos='2026-10-30')
        status, _, _ = self._request('POST', '/criar-materia', dados, token=token)
        self.assertEqual(status, 200)
        registro = self.db.query(models.LogAuditoria).filter_by(acao='aceite_editorial').one()
        self.assertEqual(registro.usuario_id, admin.uuid)
        self.assertEqual(json.loads(registro.detalhes_json)['versao_termos'], '2026-10-30')
        materia = self.db.query(models.Conteudo).filter_by(titulo='Título de leitura').one()
        self.assertEqual(materia.editorial.titulo_home, 'Chamada na Home')
        config = json.loads(materia.editorial.configuracao_json)
        self.assertEqual(config['imagens'][0]['fonte'], fonte_longa)
        status, _, html = self._request('GET', '/materia/'+materia.uuid, token=token)
        self.assertEqual(status, 200)
        self.assertIn(b'Imagem de apoio', html)
        self.assertIn(b'>exemplo.test', html)
        self.assertIn(('href="'+fonte_longa+'"').encode(), html)
        self.assertIn(b'materia-image-normal', html)
        self.assertIn(b'<blockquote>', html)
        materia.status = models.StatusConteudo.APROVADO
        self.db.commit()
        status, _, corpo = self._request('GET', '/api/conteudos')
        self.assertEqual(json.loads(corpo)[0]['titulo'], 'Chamada na Home')
        invalidos = {**dados, 'editorial': {**dados['editorial'], 'imagens': [{'fonte': ''}]}}
        status, _, _ = self._request('POST', '/criar-materia', invalidos, token=token)
        self.assertEqual(status, 422)

    def test_juridle_uma_rodada_diaria_inclusive_admin_e_sem_reinicio(self):
        from services import juridle
        for papel in (TipoUsuario.ESTUDANTE, TipoUsuario.ADMINISTRADOR):
            jogador = self._usuario(papel)
            token = criar_access_token(jogador)
            status, _, corpo = self._request('POST', '/api/juridle/rodadas', {}, token=token)
            self.assertEqual(status, 200)
            rodada = json.loads(corpo)['rodada']
            registro = self.db.get(models.JuridleRodada, rodada['uuid'])
            gabarito = json.loads(registro.perguntas_json)
            for i in range(5):
                juridle.responder(self.db, jogador.uuid, registro.uuid, i, gabarito[i]['correta'])
            for _ in range(3):
                status, _, corpo = self._request('POST', '/api/juridle/rodadas', {}, token=token)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(corpo)['rodada']['uuid'], registro.uuid)
                self.assertTrue(json.loads(corpo)['rodada']['concluida'])
            self.assertEqual(self.db.query(models.JuridleRodada).filter_by(usuario_id=jogador.uuid).count(), 1)
            self.assertEqual(self.db.query(models.JuridleDia).filter_by(usuario_id=jogador.uuid).count(), 1)

    def test_juridle_trinta_dias_150_itens_sem_repetir_e_retorno_no_31(self):
        from services import juridle
        for i in range(125):
            self.db.add(models.JuridleQuestao(enunciado=f'Questão de teste {i}', area='Teste', opcoes_json='["A","B","C","D"]',
                correta=0, explicacao='Explicação fictícia para teste automatizado.', fonte_url='https://example.test',
                status='aprovada', criada_em=juridle.agora(), atualizada_em=juridle.agora()))
        self.db.commit()
        jogador = self._usuario()
        inicio = datetime(2026, 10, 1, 12)
        usados, primeira = set(), set()
        for dia in range(30):
            with patch('services.juridle.agora', return_value=inicio + timedelta(days=dia)):
                rodada = juridle.iniciar(self.db, jogador.uuid)
                ids = {q['questaoId'] for q in json.loads(rodada.perguntas_json)}
                self.assertEqual(len(ids), 5)
                self.assertFalse(ids & usados)
                usados.update(ids)
                if dia == 0:
                    primeira = ids
        self.assertEqual(len(usados), 150)
        with patch('services.juridle.agora', return_value=inicio + timedelta(days=30)):
            rodada = juridle.iniciar(self.db, jogador.uuid)
            self.assertEqual({q['questaoId'] for q in json.loads(rodada.perguntas_json)}, primeira)

    def test_juridle_brasilia_meia_noite_renova_sem_responder_ontem(self):
        from services import juridle
        jogador = self._usuario()
        with patch('services.juridle.agora', return_value=datetime(2026, 11, 6, 2, 59)):
            antiga = juridle.iniciar(self.db, jogador.uuid)
            self.assertEqual(antiga.expira_em, datetime(2026, 11, 6, 3))
        with patch('services.juridle.agora', return_value=datetime(2026, 11, 6, 3)):
            nova = juridle.iniciar(self.db, jogador.uuid)
            self.assertNotEqual(antiga.uuid, nova.uuid)
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as erro:
                juridle.responder(self.db, jogador.uuid, antiga.uuid, 0, 0)
            self.assertEqual(erro.exception.status_code, 409)

    def test_juridle_rodada_legada_hoje_nao_libera_novo_sorteio(self):
        from services import juridle
        jogador = self._usuario()
        antiga = models.JuridleRodada(usuario_id=jogador.uuid, perguntas_json='[]', respostas_json='[]',
            respondidas=5, criada_em=juridle.agora(), expira_em=juridle.agora()+timedelta(days=1), concluida_em=juridle.agora())
        self.db.add(antiga)
        self.db.commit()
        self.assertEqual(juridle.iniciar(self.db, jogador.uuid).uuid, antiga.uuid)
        self.assertEqual(self.db.query(models.JuridleRodada).count(), 1)

    def test_juridle_falta_questoes_nao_gasta_dia_nem_usa_pendentes(self):
        from services import juridle
        from fastapi import HTTPException
        jogador = self._usuario()
        self.db.query(models.JuridleQuestao).update({'status': 'pendente'})
        self.db.commit()
        with self.assertRaises(HTTPException) as erro:
            juridle.iniciar(self.db, jogador.uuid)
        self.assertEqual(erro.exception.status_code, 409)
        self.assertEqual(self.db.query(models.JuridleDia).count(), 0)
        self.db.rollback()
        self.db.query(models.JuridleQuestao).update({'status': 'aprovada'})
        self.db.commit()
        self.assertEqual(juridle.iniciar(self.db, jogador.uuid).respondidas, 0)

    def test_juridle_seed_idempotente_nao_reaprova_arquivadas(self):
        from services import juridle
        q = self.db.query(models.JuridleQuestao).first()
        q.status = 'arquivada'
        self.db.commit()
        juridle.garantir_banco_inicial(self.db)
        self.assertEqual(self.db.query(models.JuridleQuestao).count(), 25)
        self.assertEqual(self.db.get(models.JuridleQuestao, q.uuid).status, 'arquivada')

    def test_juridle_banco_restrito_revisao_root_e_versao(self):
        leitor, admin, outro, root = self._usuario(), self._usuario(TipoUsuario.ADMINISTRADOR), self._usuario(TipoUsuario.ADMINISTRADOR), self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        self.db.commit()
        dados = {'enunciado': 'Qual alternativa atende ao cenário apresentado?', 'area': 'Teste', 'correta': 'Correta de teste',
            'erradas': ['Errada um', 'Errada dois', 'Errada três'], 'explicacao': 'Explicação fictícia da questão usada neste teste.', 'fonte_url': 'https://example.test/fonte'}
        status, _, _ = self._request('POST', '/api/juridle/questoes', dados, token=criar_access_token(leitor))
        self.assertEqual(status, 404)
        status, _, _ = self._request('GET', '/juridle/ampliar', token=criar_access_token(leitor))
        self.assertEqual(status, 404)
        status, _, corpo = self._request('POST', '/api/juridle/questoes', dados, token=criar_access_token(admin))
        self.assertEqual(status, 201)
        q = json.loads(corpo)
        self.assertEqual(q['status'], 'pendente')
        token_root = criar_access_token(root)
        status, _, corpo = self._request('GET', '/admin/tabela-noticias', token=token_root)
        self.assertEqual(200, status)
        self.assertIn(b'href="/juridle/ampliar">Revisar', corpo)
        status, _, corpo = self._request('GET', '/juridle/ampliar', token=token_root)
        self.assertEqual(200, status)
        self.assertIn(b'id="b-tab-lista" role="tab" aria-selected="true"', corpo)
        self.assertIn(b'<option value="pendente" selected>', corpo)
        status, _, corpo = self._request('GET', '/api/juridle/questoes?status=pendente', token=token_root)
        self.assertEqual(200, status)
        self.assertEqual([q['uuid']], [item['uuid'] for item in json.loads(corpo)['itens']])
        status, _, corpo = self._request('GET', '/juridle/ampliar', token=criar_access_token(admin))
        self.assertEqual(200, status)
        self.assertIn(b'id="b-tab-criar" role="tab" aria-selected="true"', corpo)
        caminho = '/api/juridle/questoes/' + q['uuid']
        status, _, _ = self._request('GET', caminho, token=criar_access_token(outro))
        self.assertEqual(status, 404)
        status, _, _ = self._request('POST', caminho+'/revisao', {'decisao': 'aprovar', 'versao': 1}, token=criar_access_token(admin))
        self.assertEqual(status, 403)
        status, _, _ = self._request('POST', caminho+'/revisao', {'decisao': 'aprovar', 'versao': 1}, token=criar_access_token(root))
        self.assertEqual(status, 200)
        status, _, _ = self._request('POST', caminho+'/revisao', {'decisao': 'rejeitar', 'versao': 1, 'motivo': 'Teste de versão antiga'}, token=criar_access_token(root))
        self.assertEqual(status, 409)
        status, _, _ = self._request('POST', caminho+'/revisao', {'decisao': 'arquivar', 'versao': 2, 'motivo': 'Conteúdo em revisão'}, token=criar_access_token(root))
        self.assertEqual(status, 200)
        self.assertEqual(self.db.get(models.JuridleQuestao, q['uuid']).status, 'arquivada')
        self.assertEqual(self.db.query(models.LogAuditoria).filter_by(acao='juridle_questao_revisada').count(), 2)
        status, _, corpo = self._request('GET', '/api/juridle/questoes', token=criar_access_token(admin))
        self.assertEqual(json.loads(corpo)['total'], 1)

    def test_juridle_questao_imagem_opcional_validacao_e_gabarito_privado(self):
        from io import BytesIO
        from PIL import Image
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        dados = {'enunciado': 'Qual é a alternativa correta nesta pergunta de teste?', 'correta': 'Alternativa correta',
            'erradas': ['Alternativa incorreta 1', 'Alternativa incorreta 2', 'Alternativa incorreta 3'],
            'explicacao': 'Explicação fictícia para testar o cadastro.', 'fonte_url': 'https://example.test/fonte'}
        for extras in ({'enunciado': '<img src=x onerror=alert(1)> Pergunta de teste'},
                       {'explicacao': '<script>alert(1)</script>'}, {'erradas': ['<b>B</b>', 'C', 'D']},
                       {'correta': {'texto': 'Resposta'}}, {'fonte_url': ''},
                       {'erradas': ['Alternativa correta','B','C']}, {'erradas': ['B',' B ','C']},
                       {'fonte_url': 'javascript:alert(1)'}, {'status': 'aprovada'}, {'correta': True}, {'imagem': 'data:image/svg+xml;base64,PHN2Zz4='}):
            status, _, _ = self._request('POST', '/api/juridle/questoes', {**dados, **extras}, token=token)
            self.assertEqual(status, 422)
        foto = BytesIO()
        Image.new('RGB', (10,10), 'blue').save(foto, 'PNG')
        imagem = 'data:image/png;base64,'+base64.b64encode(foto.getvalue()).decode()
        status, _, _ = self._request('POST', '/api/juridle/questoes', {**dados,'imagem':imagem}, token=token)
        self.assertEqual(status, 422)
        status, _, corpo = self._request('POST', '/api/juridle/questoes', {**dados,'imagem':imagem,'imagem_alt':'Ilustração','imagem_credito':'Acervo de teste'}, token=token)
        self.assertEqual(status, 201)
        q = self.db.get(models.JuridleQuestao, json.loads(corpo)['uuid'])
        self.assertTrue(q.imagem.startswith('data:image/jpeg;base64,'))
        self.db.query(models.JuridleQuestao).update({'status': 'arquivada'})
        q.status = 'aprovada'
        self.db.commit()
        # Quatro outras questões permitem o sorteio de cinco, incluindo a ilustrada.
        outras = self.db.query(models.JuridleQuestao).filter(models.JuridleQuestao.uuid != q.uuid).limit(4).all()
        for outra in outras:
            outra.status = 'aprovada'
        self.db.commit()
        status, _, corpo = self._request('POST', '/api/juridle/rodadas', {}, token=token)
        self.assertEqual(status, 200)
        self.assertNotIn('correta', json.loads(corpo)['rodada']['pergunta'])
        self.assertNotIn('explicacao', json.loads(corpo)['rodada']['pergunta'])
        rodada = self.db.get(models.JuridleRodada, json.loads(corpo)['rodada']['uuid'])
        self.assertTrue(any(p.get('imagem') for p in json.loads(rodada.perguntas_json)))


    def test_auditoria_limita_seis_logs_e_pagina_sem_repetir(self):
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        for i in range(13):
            self.db.add(models.LogAuditoria(acao='teste_seis', recurso_tipo='teste', resultado='sucesso', usuario_tipo='administrador', correlacao_id=str(uuid.uuid4())))
        self.db.commit()
        status, _, corpo = self._request('GET', '/api/admin/auditoria?acao=teste_seis', token=token)
        self.assertEqual(status, 200)
        primeira = json.loads(corpo)
        self.assertEqual(primeira['limite'], 6)
        self.assertEqual(primeira['total'], 13)
        self.assertEqual(len(primeira['itens']), 6)
        ids = {i['id'] for i in primeira['itens']}
        for deslocamento, quantidade in ((6, 6), (12, 1)):
            status, _, corpo = self._request('GET', f"/api/admin/auditoria?acao=teste_seis&deslocamento={deslocamento}&ate_id={primeira['ateId']}", token=token)
            atual = json.loads(corpo)
            self.assertEqual(status, 200)
            self.assertEqual(len(atual['itens']), quantidade)
            self.assertFalse(ids & {i['id'] for i in atual['itens']})
            ids.update(i['id'] for i in atual['itens'])
        self.assertFalse(atual['temProxima'])
        status, _, _ = self._request('GET', '/api/admin/auditoria?limite=7', token=token)
        self.assertEqual(status, 422)

    def test_glossario_paginado_busca_e_pagina_invalida(self):
        status, _, corpo = self._request('GET', '/api/glossario')
        self.assertEqual(status, 200)
        primeira = json.loads(corpo)
        self.assertEqual(len(primeira['itens']), 6)
        status, _, corpo = self._request('GET', '/api/glossario?pagina=2')
        segunda = json.loads(corpo)
        self.assertEqual(len(segunda['itens']), 6)
        self.assertFalse({i['id'] for i in primeira['itens']} & {i['id'] for i in segunda['itens']})
        status, _, corpo = self._request('GET', '/api/glossario?q=acordao&pagina=99')
        filtrada = json.loads(corpo)
        self.assertEqual(filtrada['pagina'], 1)
        self.assertEqual(filtrada['itens'][0]['id'], 'acordao')
        status, _, _ = self._request('GET', '/glossario?pagina=0')
        self.assertEqual(status, 422)

    def test_cadastro_novo_guarda_interesse_limita_campos_e_nao_reflete_senha(self):
        dados = {'nome':'João','sobrenome':'da Silva','interesse':'Direito Civil','email':'joao.teste+estudo@example.test',
            'senha':'NovaSenha!123','confirmar_senha':'NovaSenha!123','consentimento_lgpd':True,'versao_documentos':'2.2'}
        for extras in ({'nome': {'$ne': None}}, {'nome':'<script>alert(1)</script>'}, {'nome':'A'*41},
                       {'sobrenome':'S'*51}, {'interesse':'Área inventada'}, {'senha':'NovaSenha123'},
                       {'senha':'A1!'+'x'*23}, {'e_root_admin':True}):
            status, _, corpo = self._request('POST','/api/auth/cadastro',{**dados,**extras})
            self.assertEqual(status, 422)
            self.assertNotIn(b'NovaSenha!123', corpo)
            self.assertNotIn(b'"input"', corpo)
        status, _, _ = self._request('POST','/api/auth/cadastro',dados)
        self.assertEqual(status, 201)
        usuario = self.db.query(Usuario).filter_by(email=dados['email']).one()
        self.assertEqual(usuario.nome, 'João da Silva')
        self.assertEqual(usuario.especialidade_juridica,'Direito Civil')
        self.assertFalse(usuario.e_root_admin)
        self.assertEqual(usuario.tipo_usuario,TipoUsuario.ESTUDANTE)

    def test_interesse_mostra_so_publicadas_da_area_e_sem_cache(self):
        usuario=self._usuario()
        usuario.especialidade_juridica='Direito Civil'
        civil=models.Categoria(nome='Direito Civil')
        penal=models.Categoria(nome='Direito Penal')
        self.db.add_all([civil,penal]);self.db.flush()
        for indice in range(6):
            self.db.add(models.Conteudo(titulo=f'Civil {indice}', resumo_home='Resumo', corpo_texto='Texto de teste',categoria_id=civil.uuid,
                autor_id=usuario.uuid, status=models.StatusConteudo.APROVADO))
        self.db.add(models.Conteudo(titulo='Pendente',resumo_home='Resumo',corpo_texto='Texto',categoria_id=civil.uuid,autor_id=usuario.uuid, status=models.StatusConteudo.EM_ANALISE))
        self.db.add(models.Conteudo(titulo='Penal',resumo_home='Resumo',corpo_texto='Texto',categoria_id=penal.uuid,autor_id=usuario.uuid, status=models.StatusConteudo.APROVADO))
        self.db.commit()
        status,headers,corpo=self._request('GET','/api/conteudos/interesse',token=criar_access_token(usuario))
        self.assertEqual(status,200)
        self.assertIn('no-store',headers['cache-control'])
        dados=json.loads(corpo)
        self.assertEqual(dados['area'],'Direito Civil')
        self.assertEqual(len(dados['itens']),4)
        self.assertTrue(all(i['titulo'].startswith('Civil ') for i in dados['itens']))

    def test_busca_sql_e_curingas_sao_tratados_como_dados(self):
        usuario=self._usuario()
        categoria=models.Categoria(nome='Direito Civil');self.db.add(categoria);self.db.flush()
        for titulo in ('Publicação comum','Desconto 10% no contrato','Exemplo_com_subtraço'):
            self.db.add(models.Conteudo(titulo=titulo,resumo_home='Resumo',corpo_texto='Texto',categoria_id=categoria.uuid,autor_id=usuario.uuid, status=models.StatusConteudo.APROVADO))
        self.db.commit()
        for termo,esperado in (("' OR 1=1 --",0),('%',1),('_',1)):
            status,_,corpo=self._request('GET','/api/conteudos?'+urlencode({'busca':termo}))
            self.assertEqual(status,200)
            self.assertEqual(len(json.loads(corpo)),esperado)
        for caminho in ('/api/conteudos?busca=%7B%22x%22%3A1%7D','/api/glossario?q=%3Cscript%3E','/api/conteudos?busca='+'a'*81):
            status,_,_=self._request('GET',caminho)
            self.assertEqual(status,422)
        self.assertEqual(self.db.query(Usuario).count(),1)
        self.assertEqual(self.db.query(models.Conteudo).count(),3)

    def test_login_legado_continua_validando_senha_anterior(self):
        usuario=self._usuario()
        usuario.senha_hash=hash_senha('SenhaAntiga123')
        self.db.commit()
        status,_,corpo=self._request('POST','/api/auth/login',{'email':usuario.email,'senha':'SenhaAntiga123'})
        self.assertEqual(status,200)
        self.assertTrue(json.loads(corpo)['requer_2fa'])

    def test_login_seis_falhas_ip_timer_persistente_e_reset_2fa_sem_bypass(self):
        for i in range(6):
            status,headers,_=self._request('POST','/api/auth/login',{'email':f'naoexiste{i}@example.test','senha':'Errada!123'},cliente='198.51.100.10',extra_headers=((b'x-forwarded-for',f'203.0.113.{i}'.encode()),))
            self.assertEqual(status,429 if i==5 else 401)
        self.assertGreater(int(headers['retry-after']),470)
        status,_,corpo=self._request('GET','/api/auth/limite',cliente='198.51.100.10')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(corpo)['bloqueado'])
        status,_,_=self._request('POST','/api/solicitar-reset-2fa',{'email':'outra@example.test','senha':'Errada!123'},cliente='198.51.100.10')
        self.assertEqual(status,429)
        status,_,corpo=self._request('GET','/api/auth/limite',cliente='198.51.100.11')
        self.assertFalse(json.loads(corpo)['bloqueado'])
        status,_,_=self._request('POST','/api/auth/login',{'email':'naoexiste5@example.test','senha':'Errada!123'},cliente='198.51.100.11')
        self.assertEqual(status,401)  # Só uma falha nesta conta, bloqueio anterior era da origem.

    def test_perfil_seguranca_exibe_registros_reais(self):
        from services.lgpd import revisao_vigente, versao_legal

        usuario = self._usuario(TipoUsuario.ADMINISTRADOR)
        versao = versao_legal(revisao_vigente(self.db))
        usuario.consentimento_lgpd = False
        usuario.versao_termos = "antiga"
        usuario.data_consentimento = None
        self.db.commit()
        token = criar_access_token(usuario)
        status, _, corpo = self._request("GET", "/perfil", token=token)
        self.assertEqual(303, status)
        self.assertEqual(428, self._request("GET", "/api/usuarios/me", token=token)[0])

        usuario.consentimento_lgpd = True
        usuario.versao_termos = versao
        usuario.data_consentimento = datetime(2026, 11, 20, 12)
        self.db.commit()
        status, _, corpo = self._request("GET", "/perfil", token=token)
        self.assertEqual(200, status)
        self.assertIn("Confirmação atualizada", corpo.decode())
        self.assertIn("Confirmado em 20/11/2026", corpo.decode())
        self.assertIn("Ativa no autenticador", corpo.decode())

    def test_curadoria_materia_devolve_corrige_reenvia_e_aprova(self):
        autor = self._usuario(TipoUsuario.ADMINISTRADOR)
        outro = self._usuario(TipoUsuario.ADMINISTRADOR)
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        categoria = models.Categoria(nome="Direito Civil")
        self.db.add(categoria)
        self.db.flush()
        materia = models.Conteudo(
            titulo="Matéria para revisão", resumo_home="Resumo da revisão", corpo_texto="Texto completo para análise.",
            categoria_id=categoria.uuid, autor_id=autor.uuid,
            fonte_original="https://example.com/fonte", status=models.StatusConteudo.EM_ANALISE,
        )
        self.db.add(materia)
        self.db.commit()
        token_autor = criar_access_token(autor)
        token_outro = criar_access_token(outro)
        token_root = criar_access_token(root)
        api = "/api/admin/materias/" + materia.uuid
        pagina = "/admin/materias/" + materia.uuid + "/revisao"
        status, _, corpo = self._request("GET", pagina, token=token_root)
        self.assertEqual(200, status)
        self.assertIn("Texto completo para análise.", corpo.decode())
        self.assertIn("Consultar fonte original", corpo.decode())
        self.assertEqual(404, self._request("GET", pagina, token=token_outro)[0])
        self.assertEqual(403, self._request("POST", api + "/curadoria", {
            "versao": 0, "decisao": "aprovar",
        }, token=token_autor)[0])
        status, _, _ = self._request("POST", api + "/curadoria", {
            "versao": 0, "decisao": "devolver", "orientacoes": "Corrija o segundo parágrafo e confira a fonte.",
        }, token=token_root)
        self.assertEqual(200, status)
        self.assertEqual(409, self._request("POST", api + "/curadoria", {
            "versao": 0, "decisao": "aprovar",
        }, token=token_root)[0])
        status, _, corpo = self._request("GET", api + "/edicao", token=token_autor)
        self.assertEqual(200, status)
        dados = json.loads(corpo)
        self.assertEqual(1, dados["versao"])
        self.assertIn("segundo parágrafo", dados["orientacoes"])
        self.assertEqual(404, self._request("GET", api + "/edicao", token=token_outro)[0])
        reenvio = {
            "titulo": "Texto corrigido", "corpo_texto": "Segundo parágrafo corrigido.",
            "categoria_id": categoria.uuid, "fonte_original": "https://example.com/fonte",
            "versao": 1, "aceite_editorial": True, "versao_termos": "2026-10-30",
            "editorial": {"titulo_home": "Chamada corrigida", "formatado": True},
        }
        self.assertEqual(200, self._request("PUT", api + "/reenviar", reenvio, token=token_autor)[0])
        self.assertEqual(409, self._request("PUT", api + "/reenviar", reenvio, token=token_autor)[0])
        self.assertEqual(200, self._request("POST", api + "/curadoria", {
            "versao": 2, "decisao": "aprovar",
        }, token=token_root)[0])
        self.db.expire_all()
        self.assertEqual(models.StatusConteudo.APROVADO, materia.status)
        self.assertEqual("Texto corrigido", materia.titulo)
        self.assertEqual("Chamada corrigida", materia.editorial.titulo_home)

    def test_atividade_renova_mesma_sessao_apos_15_minutos_do_login(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        sid = security._decodificar_token(token)["sid"]
        sessao = self.db.get(models.SessaoAutenticada, sid)
        sessao.criada_em -= timedelta(minutes=30)
        sessao.expira_em = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=45)
        self.db.commit()
        status, headers, _ = self._request("POST", "/api/auth/presenca", {"atividade": True},
            cookie="jurishome_access_token="+token, extra_headers=((b"origin", b"http://testserver"),))
        self.assertEqual(204, status)
        self.db.refresh(sessao)
        restante = (sessao.expira_em - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()
        self.assertGreater(restante, 880)
        self.assertLessEqual(restante, 900)
        self.assertIn("HttpOnly", headers["set-cookie"])
        from http.cookies import SimpleCookie
        cookies = SimpleCookie()
        cookies.load(headers["set-cookie"])
        novo = cookies["jurishome_access_token"].value
        self.assertEqual(sid, security._decodificar_token(novo)["sid"])
        self.assertEqual(200, self._request("GET", "/api/usuarios/me", token=novo)[0])
        self.assertEqual(1, self.db.query(models.SessaoAutenticada).filter_by(usuario_id=usuario.uuid).count())

    def test_presenca_sem_atividade_nao_prolonga_prazo(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        sid = security._decodificar_token(token)["sid"]
        sessao = self.db.get(models.SessaoAutenticada, sid)
        sessao.expira_em = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=3)
        self.db.commit()
        prazo = sessao.expira_em
        for dados in (None, {"atividade": False}):
            status, headers, _ = self._request("POST", "/api/auth/presenca", dados,
                cookie="jurishome_access_token="+token, extra_headers=((b"origin", b"http://testserver"),))
            self.assertEqual(204, status)
            self.assertNotIn("set-cookie", headers)
            self.db.refresh(sessao)
            self.assertEqual(prazo, sessao.expira_em)

    def test_atividade_nao_reativa_sessao_expirada_ou_substituida(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        sid = security._decodificar_token(token)["sid"]
        sessao = self.db.get(models.SessaoAutenticada, sid)
        sessao.expira_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        self.db.commit()
        prazo = sessao.expira_em
        self.assertEqual(401, self._request("POST", "/api/auth/presenca", {"atividade": True},
            cookie="jurishome_access_token="+token, extra_headers=((b"origin", b"http://testserver"),))[0])
        self.db.refresh(sessao)
        self.assertEqual(prazo, sessao.expira_em)
        primeiro = criar_access_token(usuario)
        criar_access_token(usuario)
        status, headers, _ = self._request("POST", "/api/auth/presenca", {"atividade": True},
            cookie="jurishome_access_token="+primeiro, extra_headers=((b"origin", b"http://testserver"),))
        self.assertEqual(401, status)
        self.assertEqual("novo_acesso", headers["x-session-reason"])

    def test_atividade_exige_autenticacao_origem_e_booleano(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        cookie = "jurishome_access_token="+token
        self.assertEqual(401, self._request("POST", "/api/auth/presenca", {"atividade": True},
            extra_headers=((b"origin", b"http://testserver"),))[0])
        self.assertEqual(403, self._request("POST", "/api/auth/presenca", {"atividade": True}, cookie=cookie,
            extra_headers=((b"origin", b"https://outro.example"),))[0])
        self.assertEqual(422, self._request("POST", "/api/auth/presenca", {"atividade": "sim"}, cookie=cookie,
            extra_headers=((b"origin", b"http://testserver"),))[0])

    def test_aba_pausada_por_dois_minutos_pode_voltar_dentro_do_prazo(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        sid = security._decodificar_token(token)["sid"]
        presenca = self.db.get(models.PresencaSessao, sid)
        presenca.confirmada_em -= timedelta(minutes=3)
        self.db.commit()
        self.assertEqual(204, self._request("POST", "/api/auth/presenca", {"atividade": True},
            cookie="jurishome_access_token="+token, extra_headers=((b"origin", b"http://testserver"),))[0])

    def test_presenca_expirada_nao_pode_ser_reativada(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        sid = security._decodificar_token(token)["sid"]
        cookie = "jurishome_access_token=" + token
        status, _, _ = self._request(
            "POST", "/api/auth/presenca", cookie=cookie,
            extra_headers=((b"origin", b"http://testserver"),),
        )
        self.assertEqual(204, status)
        presenca = self.db.get(models.PresencaSessao, sid)
        presenca.confirmada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=security.PRESENCA_SESSAO_SEGUNDOS + 1)
        self.db.commit()
        status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
        self.assertEqual(401, status)
        status, _, _ = self._request(
            "POST", "/api/auth/presenca", cookie=cookie,
            extra_headers=((b"origin", b"http://testserver"),),
        )
        self.assertEqual(401, status)

    def test_novo_login_revoga_sessao_anterior(self):
        from services.lgpd import revisao_vigente, versao_legal

        usuario = self._usuario()
        usuario.consentimento_lgpd = True
        usuario.versao_termos = versao_legal(revisao_vigente(self.db))
        self.db.commit()
        primeiro = criar_access_token(usuario)
        primeiro_id = security._decodificar_token(primeiro)["sid"]
        segundo = criar_access_token(usuario)
        segundo_id = security._decodificar_token(segundo)["sid"]
        self.db.expire_all()
        self.assertTrue(self.db.get(models.SessaoAutenticada, primeiro_id).revogada)
        self.assertFalse(self.db.get(models.SessaoAutenticada, segundo_id).revogada)
        status, _, _ = self._request("GET", "/api/usuarios/me", token=primeiro)
        self.assertEqual(401, status)
        status, _, _ = self._request("GET", "/api/usuarios/me", token=segundo)
        self.assertEqual(200, status)

    def test_cookie_sessao_sem_persistencia_e_limitado_a_15_minutos(self):
        from http.cookies import SimpleCookie
        import pyotp
        from routes.auth import Codigo2FA,validar_2fa
        from auth.security import criar_token_2fa_pendente,decifrar_segredo_2fa
        for lembrar in (False,True):
            usuario=self._usuario()
            response=Response()
            codigo=pyotp.TOTP(decifrar_segredo_2fa(usuario.totp_secret)).now()
            validar_2fa(Codigo2FA(desafio_token=criar_token_2fa_pendente(usuario),codigo=codigo,lembrar_conectado=lembrar),response,self.db)
            cookies=SimpleCookie()
            for valor in response.headers.getlist('set-cookie'):
                cookies.load(valor)
            acesso=cookies['jurishome_access_token']
            sessao=self.db.get(models.SessaoAutenticada,security._decodificar_token(acesso.value)['sid'])
            self.assertEqual(acesso['max-age'], '')
            self.assertEqual(acesso['expires'], '')
            self.assertEqual(acesso['httponly'],True)
            refresh=cookies['jurishome_refresh_token']
            self.assertEqual(refresh['max-age'], '0')
            self.assertLessEqual((sessao.expira_em-sessao.criada_em).total_seconds(), 900)

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.secret_patch = patch(
            "auth.security.SECRET_KEY",
            "security-test-signing-key-with-at-least-32-bytes",
        )
        cls.secret_patch.start()
        from main import app

        cls.app = app

    @classmethod
    def tearDownClass(cls):
        cls.secret_patch.stop()
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        from services.glossario import instalar_catalogo_inicial
        instalar_catalogo_inicial(self.engine)
        self.db = self.Session()
        from services.juridle import garantir_banco_inicial
        garantir_banco_inicial(self.db)

    def tearDown(self):
        self.db.close()

    def test_polimento_revogar_aceite_todos_perfis(self):
        for papel, root in ((TipoUsuario.ESTUDANTE, False), (TipoUsuario.ADMINISTRADOR, False), (TipoUsuario.ADMINISTRADOR, True)):
            pessoa = self._usuario(papel)
            pessoa.e_root_admin = root
            self.db.commit()
            versao = pessoa.versao_termos
            token = criar_access_token(pessoa)
            url = "/api/usuarios/me/aceite"
            self.assertEqual(400, self._request("DELETE", url, {"senha": "errada", "confirmacao": "REVOGAR"}, token=token)[0])
            self.assertTrue(pessoa.consentimento_lgpd)
            self.assertEqual(200, self._request("DELETE", url, {"senha": "SenhaSegura123!", "confirmacao": "REVOGAR"}, token=token)[0])
            self.db.refresh(pessoa)
            self.assertFalse(pessoa.consentimento_lgpd)
            self.assertEqual(versao, pessoa.versao_termos)
            self.assertEqual(401, self._request("GET", "/api/usuarios/me", token=token)[0])
            novo = criar_access_token(pessoa)
            self.assertEqual(428, self._request("GET", "/api/usuarios/me", token=novo)[0])

    def test_polimento_suporte_mantem_leitor_sem_elevar_permissoes(self):
        suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
        leitor = self._usuario()
        token = criar_access_token(suporte)
        antigo = criar_access_token(leitor)
        chamado = models.FeedbackAtendimento(id="chamado-polimento", protocolo="POLIMENTO-TESTE", usuario_id=leitor.uuid,
            usuario_nome=leitor.nome, usuario_email=leitor.email, tipo="Recuperacao 2FA", assunto="Recuperar autenticador",
            mensagem="Solicitação de recuperação do autenticador.")
        self.db.add(chamado)
        self.db.commit()
        url = "/api/admin/leitores/" + leitor.uuid
        dados = {"nome": "Nome corrigido", "versao": leitor.atualizado_em.isoformat(), "resetar_2fa": True}
        self.assertEqual(403, self._request("PUT", url, dados, token=antigo)[0])
        status, _, corpo = self._request("GET", "/admin/usuarios/" + leitor.uuid, token=token)
        self.assertEqual(200, status)
        self.assertIn(url, corpo.decode())
        self.assertEqual(200, self._request("PUT", url, dados, token=token)[0])
        self.db.refresh(leitor)
        self.db.refresh(chamado)
        self.assertEqual("Resolvido", chamado.status)
        self.assertFalse(leitor.is_2fa_enabled)
        self.assertIsNone(leitor.totp_secret)
        self.assertEqual(401, self._request("GET", "/api/usuarios/me", token=antigo)[0])
        self.assertEqual(409, self._request("PUT", url, dados, token=token)[0])
        self.assertEqual(404, self._request("PUT", "/api/admin/leitores/" + suporte.uuid, dados, token=token)[0])
        dados["tipo_usuario"] = "administrador"
        self.assertEqual(422, self._request("PUT", url, dados, token=token)[0])

    def test_polimento_atualizacao_termos_bloqueia_admin_e_root_logados(self):
        for root in (False, True):
            pessoa = self._usuario(TipoUsuario.ADMINISTRADOR)
            pessoa.e_root_admin = root
            self.db.commit()
            token = criar_access_token(pessoa)
            self.db.add(models.RevisaoLegal(anterior=pessoa.versao_termos, termos="Novo termo", politica="Nova política", publicada_em=datetime.now(timezone.utc).replace(tzinfo=None)))
            self.db.commit()
            origem = ((b"origin", b"http://testserver"),)
            status, headers, _ = self._request("POST", "/api/auth/presenca", cookie="jurishome_access_token="+token, extra_headers=origem)
            self.assertEqual(204, status)
            self.assertEqual("required", headers["x-legal-acceptance"])
            self.assertEqual(428, self._request("GET", "/api/usuarios/me", token=token)[0])

    def _usuario(self, papel=TipoUsuario.ESTUDANTE, email=None):
        usuario = Usuario(
            uuid=str(uuid.uuid4()),
            nome="Conta de teste",
            email=email or f"{uuid.uuid4().hex}@example.test",
            senha_hash=hash_senha("SenhaSegura123!"),
            tipo_usuario=papel,
            totp_secret=cifrar_segredo_2fa("JBSWY3DPEHPK3PXP"),
            is_2fa_enabled=True,
        )
        self.db.add(usuario)
        from services.lgpd import revisao_vigente, versao_legal
        usuario.consentimento_lgpd = True
        usuario.versao_termos = versao_legal(revisao_vigente(self.db))
        self.db.commit()
        return usuario

    def test_documentos_legais_publicacao_root_e_novo_aceite(self):
        from fastapi.testclient import TestClient
        from services.lgpd import texto_inicial

        leitor = self._usuario()
        leitor.consentimento_lgpd = True
        leitor.versao_termos = "2.2"
        suporte = self._usuario(TipoUsuario.ADMINISTRADOR)
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        self.db.commit()
        headers_root = {"Authorization": f"Bearer {criar_access_token(root)}"}
        headers_leitor = {"Authorization": f"Bearer {criar_access_token(leitor)}"}
        headers_suporte = {"Authorization": f"Bearer {criar_access_token(suporte)}"}
        editor = "/perfil/documentos-legais"
        aceite = "/aceitar-documentos"
        publicacao = {"versao": "2.2", "texto": "Novo texto do termo & referência.", "confirmar": "sim"}

        with patch.dict(self.app.dependency_overrides, {get_db: self._banco_teste}):
            client = TestClient(self.app, follow_redirects=False)
            self.assertEqual(200, client.get("/api/usuarios/me", headers=headers_leitor).status_code)
            self.assertEqual(404, client.get(editor, headers=headers_suporte).status_code)
            self.assertEqual(404, client.post(editor + "/termos", headers=headers_suporte, data=publicacao).status_code)
            inicial = client.get(editor, headers=headers_root)
            self.assertEqual(200, inicial.status_code)
            self.assertIn("Objeto e finalidade", inicial.text)
            igual = dict(publicacao, texto=texto_inicial("termos").replace("\n", "\r\n"))
            self.assertEqual(200, client.post(editor + "/termos", headers=headers_root, data=igual).status_code)
            invalido = dict(publicacao, texto="<script>texto</script>")
            self.assertEqual(422, client.post(editor + "/termos", headers=headers_root, data=invalido).status_code)

            publicado = client.post(editor + "/termos", headers=headers_root, data=publicacao)
            self.assertEqual(303, publicado.status_code)
            self.assertEqual("/perfil/documentos-legais?tipo=termos&publicada=1", publicado.headers["location"])
            self.assertIn("Novo texto do termo &amp; referência.", client.get("/termos-de-aceite").text)
            self.assertNotIn("Novo texto do termo", client.get("/politica-de-privacidade").text)

            self.assertEqual(428, client.get("/api/usuarios/me", headers=headers_leitor).status_code)
            self.assertEqual(aceite, client.get("/home_usuario", headers=headers_leitor).headers["location"])
            pagina = client.get(aceite, headers=headers_leitor)
            self.assertIn("legal-2", pagina.text)
            self.assertIn("Novo texto do termo &amp; referência.", pagina.text)
            self.assertIn('class="acceptance-reader"', pagina.text)
            self.assertIn('name="aceite" value="sim" disabled required', pagina.text)
            confirmacao = {"versao": "legal-2", "aceite": "sim", "ciencia": "sim"}
            self.assertEqual(401, client.post(aceite, data=confirmacao).status_code)
            self.assertEqual(409, client.post(aceite, headers=headers_leitor, data=dict(confirmacao, versao="2.2")).status_code)
            self.assertEqual(422, client.post(aceite, headers=headers_leitor, data={"versao": "legal-2", "aceite": "sim"}).status_code)
            self.assertEqual(422, client.post(aceite, headers=headers_leitor, data=confirmacao).status_code)
            def comprovantes(headers):
                return {"leitura_"+tipo: client.post('/api/legal/documentos/'+tipo+'/visualizacao', headers=headers, data={"versao":"legal-2"}).json()["comprovante"] for tipo in ("termos", "privacidade")}
            leituras = comprovantes(headers_leitor)
            self.assertEqual(422, client.post(aceite, headers=headers_root, data={**confirmacao, **leituras}).status_code)
            self.assertEqual(422, client.post(aceite, headers=headers_leitor, data={**confirmacao, **leituras, "leitura_termos":"adulterado"}).status_code)
            confirmacao.update(leituras)
            self.assertEqual(303, client.post(aceite, headers=headers_leitor, data=confirmacao).status_code)
            self.assertEqual(200, client.get("/api/usuarios/me", headers=headers_leitor).status_code)

            self.assertEqual(303, client.post(aceite, headers=headers_root, data={**confirmacao, **comprovantes(headers_root)}).status_code)
            self.assertEqual(409, client.post(editor + "/privacidade", headers=headers_root, data=publicacao).status_code)
            politica = dict(publicacao, versao="legal-2", texto="Política atualizada para teste.")
            self.assertEqual(303, client.post(editor + "/privacidade", headers=headers_root, data=politica).status_code)
            self.assertIn("Política atualizada para teste.", client.get("/politica-de-privacidade").text)
            self.assertIn("Novo texto do termo", client.get("/termos-de-aceite").text)
            self.assertEqual(428, client.get("/api/usuarios/me", headers=headers_leitor).status_code)
            self.assertEqual(409, client.post('/api/legal/documentos/termos/visualizacao', headers=headers_leitor, data={"versao":"legal-2"}).status_code)
            self.assertEqual(422, client.post(aceite, headers=headers_leitor, data={**confirmacao, "versao":"legal-3"}).status_code)

        self.db.expire_all()
        self.assertEqual("legal-2", leitor.versao_termos)
        self.assertIsNotNone(leitor.data_consentimento)
        self.assertEqual(3, self.db.query(models.RevisaoLegal).count())

    def _banco_teste(self):
        sessao = self.Session()
        try:
            yield sessao
        finally:
            sessao.close()

    def _request(self, method, path, data=None, token=None, cookie=None, extra_headers=(), suprimir_erro_interno=False, cliente="testclient"):
        overrides_anteriores = self.app.dependency_overrides.copy()
        self.app.dependency_overrides[get_db] = self._banco_teste
        self.app.dependency_overrides[get_feedback_db] = self._banco_teste

        corpo = json.dumps(data).encode("utf-8") if data is not None else b""
        cabecalhos = [(b"host", b"testserver"), (b"accept", b"text/html")]
        cabecalhos.extend(extra_headers)
        if data is not None:
            cabecalhos.append((b"content-type", b"application/json"))
        if token:
            cabecalhos.append((b"authorization", f"Bearer {token}".encode("ascii")))
        if cookie:
            cabecalhos.append((b"cookie", cookie.encode("ascii")))
        mensagens = []

        async def receber():
            return {"type": "http.request", "body": corpo, "more_body": False}

        async def enviar(mensagem):
            mensagens.append(mensagem)

        url = urlsplit(path)
        escopo = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode("ascii"),
            "query_string": url.query.encode("ascii"),
            "root_path": "",
            "headers": cabecalhos,
            "client": (cliente, 1234),
            "server": ("testserver", 80),
        }
        try:
            try:
                asyncio.run(self.app(escopo, receber, enviar))
            except Exception:
                if not suprimir_erro_interno:
                    raise
        finally:
            self.app.dependency_overrides.clear()
            self.app.dependency_overrides.update(overrides_anteriores)

        inicio = next(item for item in mensagens if item["type"] == "http.response.start")
        corpo_resposta = b"".join(
            item.get("body", b"")
            for item in mensagens
            if item["type"] == "http.response.body"
        )
        headers = {
            chave.decode("latin1").lower(): valor.decode("latin1")
            for chave, valor in inicio["headers"]
        }
        return inicio["status"], headers, corpo_resposta

    def test_rotas_administrativas_rejeitam_sessao_ausente(self):
        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
        ):
            with self.subTest(caminho=caminho):
                status, headers, _ = self._request("GET", caminho)
                self.assertEqual(404, status)
                self.assertIn(b'error-title', self._request('GET', caminho)[2])

        for caminho in ("/api/admin/auditoria", "/api/admin/feedbacks"):
            with self.subTest(caminho=caminho):
                status, _, _ = self._request("GET", caminho)
                self.assertEqual(401, status)

    def test_escrita_rejeita_origem_externa_inclusive_no_login(self):
        for origem in (b"https://malicioso.test", b"http://testserver.malicioso.test", b"null"):
            with self.subTest(origem=origem):
                status, _, _ = self._request(
                    "POST", "/api/auth/login",
                    {"email": "pessoa@example.test", "senha": "Senha123"},
                    extra_headers=((b"origin", origem),),
                )
                self.assertEqual(403, status)

    def test_logout_revoga_token_copiado(self):
        usuario = self._usuario()
        token = criar_access_token(usuario)
        status, _, _ = self._request("POST", "/api/auth/logout", token=token)
        self.assertEqual(204, status)
        status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
        self.assertEqual(401, status)

    def test_cookie_exige_origem_em_operacoes_de_escrita(self):
        usuario = self._usuario()
        cookie = f"jurishome_access_token={criar_access_token(usuario)}"
        status, _, _ = self._request("POST", "/api/auth/logout", cookie=cookie)
        self.assertEqual(403, status)
        status, _, _ = self._request(
            "POST", "/api/auth/logout", cookie=cookie,
            extra_headers=((b"origin", b"http://testserver"),),
        )
        self.assertEqual(204, status)

    def test_perfil_rejeita_avatar_invalido_e_versao_antiga(self):
        from fastapi import HTTPException
        from routes.perfil import atualizar_perfil

        usuario = self._usuario()
        with self.assertRaises(HTTPException) as avatar_invalido:
            atualizar_perfil(nome=usuario.nome, faculdade=None, interesse=None, avatar_id="externo.svg",
                             versao=usuario.atualizado_em.isoformat(), db=self.db, usuario=usuario)
        self.assertEqual(422, avatar_invalido.exception.status_code)

        versao_antiga = usuario.atualizado_em.isoformat()
        atualizar_perfil(nome="Nome atualizado", faculdade=None, interesse=None, avatar_id="aurora",
                         versao=versao_antiga, db=self.db, usuario=usuario)
        with self.assertRaises(HTTPException) as conflito:
            atualizar_perfil(nome="Nome sobrescrito", faculdade=None, interesse=None, avatar_id="oceano",
                             versao=versao_antiga, db=self.db, usuario=usuario)
        self.assertEqual(409, conflito.exception.status_code)
        self.db.refresh(usuario)
        self.assertEqual("Nome atualizado", usuario.nome)

    def test_materia_base64_so_aparece_apos_aprovacao_do_root(self):
        from io import BytesIO
        from PIL import Image
        from model.models import Categoria, Conteudo
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        self.db.add(categoria)
        self.db.commit()
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        saida = BytesIO()
        Image.new("RGB", (12, 8), "red").save(saida, format="PNG")
        imagem = "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")
        status, _, _ = self._request("POST", "/criar-materia", {
            "aceite_editorial": True, "versao_termos": "2026-10-30", "titulo": "Matéria Base64", "corpo_texto": "Texto da matéria.",
            "categoria_id": categoria.uuid,
            "imagem_miniatura": imagem, "imagem_corpo": imagem,
        }, token=token)
        self.assertEqual(200, status)
        materia = self.db.query(Conteudo).filter_by(titulo="Matéria Base64").one()
        self.assertTrue(materia.imagem_miniatura.startswith("data:image/jpeg;base64,"))
        status, _, corpo = self._request("GET", "/api/conteudos")
        self.assertEqual([], json.loads(corpo))
        status, _, _ = self._request("PUT", f"/aprovar-materia/{materia.uuid}", token=token)
        self.assertEqual(404, status)
        root = self._usuario(TipoUsuario.ADMINISTRADOR)
        root.e_root_admin = True
        self.db.commit()
        status, _, _ = self._request("POST", f"/api/admin/materias/{materia.uuid}/curadoria", token=criar_access_token(root), data={"versao": 0, "decisao": "aprovar"})
        self.assertEqual(200, status)
        status, _, corpo = self._request("GET", "/api/conteudos")
        self.assertEqual(["Matéria Base64"], [item["titulo"] for item in json.loads(corpo)])

    def test_materia_rejeita_categoria_inexistente_e_imagem_disfarcada(self):
        from model.models import Categoria
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        dados = {"titulo": "Teste", "corpo_texto": "Texto", "categoria_id": "inexistente"}
        status, _, _ = self._request("POST", "/criar-materia", dados, token=token)
        self.assertEqual(422, status)
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Teste imagem")
        self.db.add(categoria)
        self.db.commit()
        dados["categoria_id"] = categoria.uuid
        for imagem in ("data:image/svg+xml;base64,PHN2Zz4=", "data:image/jpeg;base64,PGh0bWw+", 'https://exemplo.test/" onerror="alert(1)'):
            with self.subTest(imagem=imagem):
                status, _, _ = self._request("POST", "/criar-materia", {**dados, "imagem_miniatura": imagem}, token=token)
                self.assertEqual(422, status)

    def test_usuario_consulta_somente_seus_feedbacks_sem_observacoes_internas(self):
        primeiro = self._usuario()
        segundo = self._usuario()
        token_primeiro = criar_access_token(primeiro)
        token_segundo = criar_access_token(segundo)
        criados = []
        for token in (token_primeiro, token_segundo):
            status, _, corpo = self._request("POST", "/api/feedbacks", {
                "tipo": "Dúvida", "assunto": "Dúvida de acesso", "mensagem": "Como consultar as minhas respostas?",
            }, token=token)
            self.assertEqual(201, status)
            criados.append(json.loads(corpo))
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token_admin = criar_access_token(admin)
        status, _, corpo_admin = self._request("POST", f"/api/admin/feedbacks/{criados[0]['id']}/respostas", {"mensagem": "Você pode consultar em Meus atendimentos.", "atualizadoEm": criados[0]["atualizadoEm"]}, token=token_admin)
        self.assertEqual(200, status)
        versao_atual = json.loads(corpo_admin)["atualizadoEm"]
        status, _, _ = self._request("POST", f"/api/admin/feedbacks/{criados[0]['id']}/observacoes", {"mensagem": "Anotação exclusiva da equipe.", "atualizadoEm": versao_atual}, token=token_admin)
        self.assertEqual(200, status)
        status, _, corpo = self._request("GET", "/api/feedbacks/me", token=token_primeiro)
        self.assertEqual(200, status)
        registros = json.loads(corpo)
        self.assertEqual([criados[0]["id"]], [registro["id"] for registro in registros])
        self.assertEqual(1, len(registros[0]["respostas"]))
        self.assertNotIn("observacoesInternas", registros[0])
        self.assertNotIn("Anotação exclusiva", corpo.decode("utf-8"))
        self.assertTrue(all(item["visibilidade"] != "interna" for item in registros[0]["historico"]))
        status, _, _ = self._request("GET", f"/api/admin/feedbacks/{criados[1]['id']}", token=token_primeiro)
        self.assertEqual(403, status)

    def test_auditoria_paginada_snapshot_privacidade_e_periodo(self):
        from model.models import LogAuditoria
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        for indice in range(3):
            self.db.add(LogAuditoria(acao="teste_consulta", recurso_tipo="teste", recurso_id=str(indice), usuario_tipo="administrador", resultado="sucesso", correlacao_id=str(uuid.uuid4()), detalhes_json=json.dumps({"motivo": "teste", "token_legado": "nao-exibir", "lista": [{"senha": "nao-exibir"}]}), criado_em=datetime(2026,10,20,12,indice)))
        self.db.commit()
        status, headers, corpo = self._request("GET", "/api/admin/auditoria?limite=2", token=token)
        self.assertEqual(200, status)
        self.assertIn("no-store", headers["cache-control"])
        dados = json.loads(corpo)
        self.assertEqual(3, dados["total"])
        self.assertEqual(2, len(dados["itens"]))
        self.assertTrue(dados["temProxima"])
        self.assertNotIn("nao-exibir", corpo.decode())
        self.db.add(LogAuditoria(acao="nova_acao", recurso_tipo="teste", usuario_tipo="administrador", resultado="falha", correlacao_id=str(uuid.uuid4())))
        self.db.commit()
        status, _, corpo = self._request("GET", f"/api/admin/auditoria?limite=2&deslocamento=2&ate_id={dados['ateId']}", token=token)
        pagina = json.loads(corpo)
        self.assertEqual(3, pagina["total"])
        self.assertEqual(1, len(pagina["itens"]))
        self.assertNotIn(pagina["itens"][0]["id"], [item["id"] for item in dados["itens"]])
        self.assertFalse(pagina["temProxima"])
        periodo = urlencode({"inicio": "2026-10-20T00:00:00-03:00", "fim": "2026-10-21T00:00:00-03:00"})
        status, _, corpo = self._request("GET", f"/api/admin/auditoria?{periodo}", token=token)
        self.assertEqual(200, status)
        self.assertEqual(3, json.loads(corpo)["total"])
        status, _, _ = self._request("GET", "/api/admin/auditoria?inicio=2026-10-21T00:00:00Z&fim=2026-10-20T00:00:00Z", token=token)
        self.assertEqual(422, status)

    def test_auditoria_identifica_admin_entre_dependencia_e_endpoint(self):
        from model.models import LogAuditoria
        aluno = self._usuario()
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        status, _, corpo = self._request("POST", "/api/feedbacks", {"tipo": "Dúvida", "assunto": "Teste do responsável", "mensagem": "Mensagem de teste para validar a auditoria."}, token=criar_access_token(aluno))
        self.assertEqual(201, status)
        feedback = json.loads(corpo)
        status, _, _ = self._request("POST", f"/api/admin/feedbacks/{feedback['id']}/respostas", {"mensagem": "Resposta administrativa.", "atualizadoEm": feedback["atualizadoEm"]}, token=criar_access_token(admin))
        self.assertEqual(200, status)
        self.db.expire_all()
        registro = self.db.query(LogAuditoria).filter_by(acao="feedback_respondido").one()
        self.assertEqual(admin.uuid, registro.usuario_id)
        self.assertEqual("administrador", registro.usuario_tipo)

    def test_materia_renderiza_texto_seguro_base64_e_menu_por_perfil(self):
        from io import BytesIO
        from PIL import Image
        from model.models import Categoria, Conteudo, StatusConteudo
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        estudante = self._usuario()
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        self.db.add(categoria)
        self.db.flush()
        imagem = BytesIO()
        Image.new("RGB", (20, 10), "gold").save(imagem, format="JPEG")
        base64_imagem = "data:image/jpeg;base64," + base64.b64encode(imagem.getvalue()).decode("ascii")
        materia = Conteudo(titulo="Matéria para leitura segura", resumo_home="Resumo de teste", corpo_texto='<script>alert("teste")</script>\n' + 'texto' * 250,
            categoria_id=categoria.uuid, autor_id=admin.uuid, status=StatusConteudo.EM_ANALISE,
            imagem_miniatura=base64_imagem, imagem_corpo=base64_imagem, fonte_original="javascript:alert(1)")
        self.db.add(materia)
        self.db.commit()
        caminho = f"/materia/{materia.uuid}"
        token_admin = criar_access_token(admin)
        token_estudante = criar_access_token(estudante)
        status, _, corpo = self._request("GET", caminho, token=token_admin)
        self.assertEqual(200, status)
        html = corpo.decode("utf-8")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn('javascript:alert', html)
        self.assertIn(base64_imagem, html)
        self.assertIn('href="/admin-feedbacks"', html)
        self.assertIn('href="/admin/auditoria"', html)
        self.assertNotIn('Favoritos', html)
        self.assertNotIn('>Salvar<', html)
        status, _, _ = self._request("GET", caminho, token=token_estudante)
        self.assertEqual(404, status)
        materia.status = StatusConteudo.APROVADO
        self.db.commit()
        status, _, corpo = self._request("GET", caminho, token=token_estudante)
        self.assertEqual(200, status)
        self.assertNotIn(b'href="/admin/auditoria"', corpo)
        self.assertIn(b'configuracoes-usuario#feedback', corpo)

    def test_catalogo_idempotente_preserva_aliases_e_renderiza_opcoes(self):
        from model.models import Categoria
        from services.categorias import garantir_categorias, CATALOGO
        existente = Categoria(uuid=str(uuid.uuid4()), nome="Direito do Trabalho")
        self.db.add(existente)
        self.db.commit()
        self.assertEqual(len(CATALOGO) - 1, garantir_categorias(self.db))
        self.assertEqual(0, garantir_categorias(self.db))
        self.assertEqual(len(CATALOGO), self.db.query(Categoria).count())
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        status, _, corpo = self._request("GET", "/nova-materia", token=criar_access_token(admin))
        self.assertEqual(200, status)
        html = corpo.decode()
        self.assertNotIn("Direito do Consumidor", html)
        self.assertIn("Direito Penal (Criminal)", html)
        self.assertIn(existente.uuid, html)
        self.assertIn('id="categorias-tags"', html)
        self.assertIn('CLT', html)
        self.assertNotIn('value="ID_DIREITO_', html)

    def test_tags_salvas_pelo_servidor_e_atualizadas_com_a_categoria(self):
        from model.models import Categoria, Conteudo
        from services.categorias import garantir_categorias
        garantir_categorias(self.db)
        trabalhista = self.db.query(Categoria).filter_by(nome="Direito Trabalhista").one()
        civil = self.db.query(Categoria).filter_by(nome="Direito Civil").one()
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        status, _, _ = self._request("POST", "/criar-materia", {"aceite_editorial": True, "versao_termos": "2026-10-30", "titulo": "Tags por categoria", "corpo_texto": "Texto da matéria para teste.", "categoria_id": trabalhista.uuid, "tags": "clt, Trabalho, bolsa de estudo"}, token=token)
        self.assertEqual(200, status)
        self.db.expire_all()
        materia = self.db.query(Conteudo).filter_by(titulo="Tags por categoria").one()
        tags = materia.tags.split(", ")
        self.assertEqual(1, sum(tag.casefold() == "clt" for tag in tags))
        self.assertIn("emprego", tags)
        status, _, corpo = self._request("GET", f"/materia/{materia.uuid}", token=token)
        self.assertEqual(200, status)
        self.assertIn(b'Tags da mat', corpo)
        self.assertIn(b'>CLT</span>', corpo)
        status, _, _ = self._request("PUT", f"/editar-materia/{materia.uuid}", {"categoria_id": civil.uuid, "versao": 0}, token=token)
        self.assertEqual(200, status)
        self.db.refresh(materia)
        self.assertIn("Código Civil", materia.tags)
        self.assertIn("bolsa de estudo", materia.tags)
        self.assertNotIn("CLT", materia.tags)

    def test_materia_rejeita_edicao_e_exclusao_com_versao_antiga(self):
        from model.models import Categoria, Conteudo, CuradoriaMateria

        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        materia = Conteudo(titulo="Matéria concorrente", resumo_home="Resumo", corpo_texto="Texto original",
                           categoria_id=categoria.uuid, autor_id=admin.uuid)
        self.db.add_all([categoria, materia])
        self.db.flush()
        self.db.add(CuradoriaMateria(conteudo_id=materia.uuid, versao=2, orientacoes=""))
        self.db.commit()
        token = criar_access_token(admin)

        status, _, corpo = self._request("GET", "/admin/tabela-noticias", token=token)
        self.assertEqual(200, status)
        self.assertIn(b'data-versao="2"', corpo)

        status, _, _ = self._request("PUT", f"/editar-materia/{materia.uuid}",
                                     {"titulo": "Título desatualizado", "versao": 1}, token=token)
        self.assertEqual(409, status)
        status, _, _ = self._request("DELETE", f"/deletar-materia/{materia.uuid}?versao=1", token=token)
        self.assertEqual(409, status)
        self.db.expire_all()
        self.assertEqual("Matéria concorrente", self.db.get(Conteudo, materia.uuid).titulo)

    def test_corrige_apenas_vinculo_de_categoria_de_exemplo_conhecido(self):
        from model.models import Conteudo, Categoria
        from services.categorias import garantir_categorias, corrigir_vinculos_legados
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        garantir_categorias(self.db)
        materia = Conteudo(titulo="Matéria antiga", resumo_home="Resumo", corpo_texto="Texto", categoria_id="ID_DIREITO_PENAL", autor_id=admin.uuid)
        self.db.add(materia)
        self.db.commit()
        self.assertEqual(1, corrigir_vinculos_legados(self.db))
        self.assertEqual(0, corrigir_vinculos_legados(self.db))
        self.db.refresh(materia)
        self.assertEqual("Direito Penal", self.db.get(Categoria, materia.categoria_id).nome)
        self.assertIn("criminal", materia.tags)

    def test_estudante_autenticado_nao_acessa_telas_nem_apis_admin(self):
        estudante = self._usuario()
        token = criar_access_token(estudante)

        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
            "/api/admin/auditoria",
            "/api/admin/feedbacks",
        ):
            with self.subTest(caminho=caminho):
                status, _, corpo = self._request("GET", caminho, token=token)
                self.assertEqual(403 if caminho.startswith("/api/") else 404, status, corpo.decode("utf-8", errors="replace"))

    def test_administrador_autenticado_acessa_rotas_admin(self):
        administrador = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(administrador)

        for caminho in (
            "/home_admin",
            "/configuracao",
            "/admin-feedbacks",
            "/admin/auditoria",
            "/api/admin/auditoria",
            "/api/admin/feedbacks",
        ):
            with self.subTest(caminho=caminho):
                status, _, corpo = self._request("GET", caminho, token=token)
                self.assertEqual(200, status, corpo.decode("utf-8", errors="replace"))

    def test_token_adulterado_expirado_e_de_2fa_nao_autentica(self):
        usuario = self._usuario()
        agora = datetime.now(timezone.utc)
        tokens_invalidos = (
            "nao.e.um.jwt",
            criar_token_2fa_pendente(usuario),
            jwt.encode(
                {
                    "sub": usuario.uuid,
                    "tipo": "acesso",
                    "iat": agora - timedelta(hours=2),
                    "exp": agora - timedelta(hours=1),
                },
                security.SECRET_KEY,
                algorithm="HS256",
            ),
            jwt.encode(
                {
                    "sub": usuario.uuid,
                    "tipo": "acesso",
                    "iat": agora,
                    "exp": agora + timedelta(minutes=5),
                },
                "another-security-test-key-with-at-least-32-bytes",
                algorithm="HS256",
            ),
        )

        for token in tokens_invalidos:
            with self.subTest(token=token[:12]):
                status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
                self.assertEqual(401, status)

    def test_tokens_exigem_campos_obrigatorios_e_datas_numericas_validas(self):
        usuario = self._usuario()
        agora = datetime.now(timezone.utc).timestamp()
        base = {"sub": usuario.uuid, "tipo": "acesso", "iat": agora, "exp": agora + 300}
        casos = []
        for campo in ("sub", "tipo", "iat", "exp"):
            casos.append({chave: valor for chave, valor in base.items() if chave != campo})
        for campo in ("iat", "exp"):
            for valor in (True, "123", float("nan"), float("inf"), -1e30):
                casos.append({**base, campo: valor})
        casos.append({**base, "sub": ""})
        casos.append({**base, "iat": agora - 10, "exp": agora - 20})
        for payload in casos:
            with self.subTest(payload=payload):
                token = jwt.encode(payload, security.SECRET_KEY, algorithm="HS256")
                status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
                self.assertEqual(401, status)

    def test_desafios_tambem_exigem_expiracao(self):
        decodificadores = (
            ("2fa_pendente", security.decodificar_token_2fa_pendente),
            ("2fa_configuracao", security.decodificar_token_configuracao_2fa),
            ("recuperacao_senha", security.decodificar_token_recuperacao_senha),
            ("nova_senha", security.decodificar_token_nova_senha),
        )
        for tipo, decodificar in decodificadores:
            with self.subTest(tipo=tipo):
                token = jwt.encode({"sub": "conta-teste", "tipo": tipo, "iat": datetime.now(timezone.utc)}, security.SECRET_KEY, algorithm="HS256")
                with self.assertRaises(ValueError):
                    decodificar(token)

    def test_hash_ausente_nao_provoca_erro_interno(self):
        self.assertFalse(verificar_senha("Senha123", None))
        self.assertFalse(verificar_senha(None, "hash"))

    def test_desafio_2fa_consumido_nao_pode_ser_reutilizado(self):
        import pyotp
        from routes.auth import validar_2fa
        usuario = self._usuario()
        desafio = criar_token_2fa_pendente(usuario)
        dados = Codigo2FA(desafio_token=desafio, codigo=pyotp.TOTP("JBSWY3DPEHPK3PXP").now())
        self.assertTrue(validar_2fa(dados, Response(), self.db)["autenticado"])
        with self.assertRaises(Exception) as contexto:
            validar_2fa(dados, Response(), self.db)
        self.assertEqual(401, contexto.exception.status_code)
        self.db.rollback()

    def test_mesmo_totp_nao_funciona_em_outro_desafio(self):
        import pyotp
        from routes.auth import validar_2fa
        usuario = self._usuario()
        codigo = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
        for indice in range(2):
            dados = Codigo2FA(desafio_token=criar_token_2fa_pendente(usuario), codigo=codigo)
            if indice == 0:
                validar_2fa(dados, Response(), self.db)
            else:
                with self.assertRaises(Exception) as contexto:
                    validar_2fa(dados, Response(), self.db)
                self.assertEqual(401, contexto.exception.status_code)
                self.db.rollback()

    def test_desafio_anterior_a_revogacao_nao_emite_sessao(self):
        import pyotp
        from routes.auth import validar_2fa
        usuario = self._usuario()
        desafio = criar_token_2fa_pendente(usuario)
        usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        with self.assertRaises(Exception) as contexto:
            validar_2fa(Codigo2FA(desafio_token=desafio, codigo=pyotp.TOTP("JBSWY3DPEHPK3PXP").now()), Response(), self.db)
        self.assertEqual(401, contexto.exception.status_code)
        self.db.rollback()

    def _sessao_renovavel(self):
        from auth.sessions import criar_refresh
        usuario = self._usuario()
        acesso = criar_access_token(usuario, lembrar_conectado=True)
        sid = security._decodificar_token(acesso)["sid"]
        refresh = criar_refresh(self.db, sid)
        self.db.commit()
        return usuario, acesso, refresh, sid

    def test_lembrar_conectado_limita_access_token_a_15_minutos(self):
        _, acesso, _, _ = self._sessao_renovavel()
        payload = security._decodificar_token(acesso)
        self.assertLessEqual(payload["exp"] - payload["iat"], 900)

    def test_refresh_rota_e_reutilizacao_revoga_toda_a_sessao(self):
        from auth.sessions import renovar_sessao
        from model.models import SessaoAutenticada
        _, acesso, antigo, sid = self._sessao_renovavel()
        prazo_original = self.db.get(SessaoAutenticada, sid).expira_em
        novo_acesso, novo_refresh, restante = renovar_sessao(self.db, antigo)
        self.assertEqual(prazo_original, self.db.get(SessaoAutenticada, sid).expira_em)
        self.assertLessEqual(restante, 900)
        self.assertLessEqual(
            security._decodificar_token(novo_acesso)["exp"],
            prazo_original.replace(tzinfo=timezone.utc).timestamp(),
        )
        self.assertNotEqual(antigo, novo_refresh)
        self.assertEqual(sid, security._decodificar_token(novo_acesso)["sid"])
        self.assertLessEqual((self.db.get(SessaoAutenticada, sid).expira_em - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds(), 900)
        with self.assertRaises(Exception) as contexto:
            renovar_sessao(self.db, antigo)
        self.assertEqual(401, contexto.exception.status_code)
        self.assertTrue(self.db.get(SessaoAutenticada, sid).revogada)
        for token in (acesso, novo_acesso):
            status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
            self.assertEqual(401, status)
        with self.assertRaises(Exception):
            renovar_sessao(self.db, novo_refresh)

    def test_sessao_persistente_reabre_inicio_ate_expirar(self):
        usuario, acesso, refresh, sid = self._sessao_renovavel()
        cookies = f"jurishome_access_token={acesso}; jurishome_refresh_token={refresh}"
        status, headers, _ = self._request("GET", "/", cookie=cookies)
        self.assertEqual(303, status)
        destino = "/home_admin" if usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR else "/home_usuario"
        self.assertEqual(destino, headers["location"])

        self.db.get(models.SessaoAutenticada, sid).expira_em = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(seconds=1)
        self.db.commit()
        status, _, _ = self._request("GET", "/", cookie=cookies)
        self.assertEqual(200, status)

    def test_sessao_inativa_nao_pode_ser_renovada(self):
        from fastapi import HTTPException
        from auth.sessions import renovar_sessao

        _, acesso, refresh, sid = self._sessao_renovavel()
        sessao = self.db.get(models.SessaoAutenticada, sid)
        sessao.criada_em -= timedelta(minutes=16)
        sessao.expira_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        self.db.commit()

        status, _, _ = self._request("GET", "/api/usuarios/me", token=acesso)
        self.assertEqual(401, status)
        with self.assertRaises(HTTPException) as contexto:
            renovar_sessao(self.db, refresh)
        self.assertEqual(401, contexto.exception.status_code)

    def test_refresh_exige_origem_e_cookie_http_only(self):
        _, _, refresh, _ = self._sessao_renovavel()
        cookie = f"jurishome_refresh_token={refresh}"
        status, _, _ = self._request("POST", "/api/auth/refresh", cookie=cookie)
        self.assertEqual(403, status)
        status, headers, _ = self._request("POST", "/api/auth/refresh", cookie=cookie, extra_headers=((b"origin", b"http://testserver"),))
        self.assertEqual(200, status)
        self.assertIn("HttpOnly", headers["set-cookie"])
        self.assertIn("SameSite=strict", headers["set-cookie"])

    def test_refresh_expirado_ou_revogado_pela_senha_falha(self):
        from auth.sessions import renovar_sessao
        from model.models import SessaoAutenticada
        usuario, _, refresh, sid = self._sessao_renovavel()
        usuario.token_validos_apos = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        with self.assertRaises(Exception) as contexto:
            renovar_sessao(self.db, refresh)
        self.assertEqual(401, contexto.exception.status_code)
        self.db.rollback()
        usuario.token_validos_apos = None
        self.db.get(SessaoAutenticada, sid).expira_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        self.db.commit()
        with self.assertRaises(Exception) as contexto:
            renovar_sessao(self.db, refresh)
        self.assertEqual(401, contexto.exception.status_code)

    def test_logout_com_access_expirado_revoga_refresh(self):
        from auth.sessions import renovar_sessao
        _, _, refresh, _ = self._sessao_renovavel()
        status, _, _ = self._request("POST", "/api/auth/logout", cookie=f"jurishome_refresh_token={refresh}", extra_headers=((b"origin", b"http://testserver"),))
        self.assertEqual(204, status)
        with self.assertRaises(Exception) as contexto:
            renovar_sessao(self.db, refresh)
        self.assertEqual(401, contexto.exception.status_code)

    def test_pagina_protegida_renova_sessao_sem_aceitar_redirecionamento_externo(self):
        _, _, refresh, _ = self._sessao_renovavel()
        status, headers, _ = self._request("GET", "/home_usuario", cookie=f"jurishome_refresh_token={refresh}")
        self.assertEqual(303, status)
        self.assertTrue(headers["location"].startswith("/renovar-sessao?destino="))
        status, _, corpo = self._request("GET", "/renovar-sessao?destino=https%3A%2F%2Fmalicioso.test")
        self.assertEqual(200, status)
        self.assertNotIn(b"malicioso.test", corpo)
        self.assertIn(b"/home_usuario", corpo)

    def test_chave_totp_independe_da_chave_jwt_e_rotacao_preserva_dados(self):
        from cryptography.fernet import Fernet
        anterior = Fernet.generate_key().decode("ascii")
        nova = Fernet.generate_key().decode("ascii")
        with patch.dict(os.environ, {"TOTP_ENCRYPTION_KEY": anterior, "TOTP_PREVIOUS_KEYS": "", "TOTP_LEGACY_JWT_KEY": ""}):
            cifrado = security.cifrar_segredo_2fa("JBSWY3DPEHPK3PXP")
        with patch.dict(os.environ, {"TOTP_ENCRYPTION_KEY": nova, "TOTP_PREVIOUS_KEYS": anterior, "TOTP_LEGACY_JWT_KEY": ""}), patch.object(security, "SECRET_KEY", "outra-chave-jwt-independente-com-32-bytes"):
            self.assertEqual("JBSWY3DPEHPK3PXP", security.decifrar_segredo_2fa(cifrado))
        with patch.dict(os.environ, {"TOTP_ENCRYPTION_KEY": nova, "TOTP_PREVIOUS_KEYS": "", "TOTP_LEGACY_JWT_KEY": ""}):
            with self.assertRaises(ValueError):
                security.decifrar_segredo_2fa(cifrado)

    def test_consumo_concorrente_so_autoriza_uma_tentativa(self):
        import tempfile
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from threading import Barrier
        from fastapi import HTTPException
        from auth.sessions import consumir_desafio
        from model.models import DesafioConsumido
        with tempfile.TemporaryDirectory() as pasta:
            engine = create_engine("sqlite:///" + (Path(pasta) / "concorrencia.db").as_posix(), connect_args={"check_same_thread": False})
            Base.metadata.create_all(engine)
            Fabrica = sessionmaker(bind=engine)
            with Fabrica() as db:
                usuario = Usuario(uuid=str(uuid.uuid4()), nome="Teste concorrente", email="concorrente@example.test", tipo_usuario=TipoUsuario.ESTUDANTE)
                db.add(usuario)
                db.commit()
                usuario_id = usuario.uuid
                token = criar_token_2fa_pendente(usuario)
            barreira = Barrier(2)
            def tentar(_):
                with Fabrica() as db:
                    usuario = db.get(Usuario, usuario_id)
                    barreira.wait(timeout=10)
                    try:
                        consumir_desafio(db, token, usuario, "2fa_pendente")
                        db.commit()
                        return 200
                    except HTTPException as erro:
                        db.rollback()
                        return erro.status_code
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    self.assertEqual([200, 401], sorted(executor.map(tentar, range(2))))
                with Fabrica() as db:
                    self.assertEqual(1, db.query(DesafioConsumido).count())
            finally:
                engine.dispose()

    def test_falha_na_recifragem_nao_altera_registros(self):
        from cryptography.fernet import Fernet, MultiFernet, InvalidToken
        from migrar_seguranca import recifrar
        usuario = self._usuario()
        original = usuario.totp_secret
        chave = security._chaves_2fa()[0]
        invalido = Usuario(uuid=str(uuid.uuid4()), nome="Cifra inválida", email="cifra@example.test", totp_secret="invalido", tipo_usuario=TipoUsuario.ESTUDANTE)
        self.db.add(invalido)
        self.db.commit()
        with self.assertRaises(InvalidToken):
            recifrar(self.db, MultiFernet([chave]), Fernet(Fernet.generate_key()))
        self.db.rollback()
        self.assertEqual(original, self.db.get(Usuario, usuario.uuid).totp_secret)
        self.db.delete(invalido)
        self.db.commit()
        nova = Fernet(Fernet.generate_key())
        self.assertEqual(1, recifrar(self.db, MultiFernet([chave]), nova))
        self.db.commit()
        self.assertEqual(b"JBSWY3DPEHPK3PXP", nova.decrypt(usuario.totp_secret.encode("ascii")))

    def test_rollback_preserva_desafio_para_nova_tentativa(self):
        from auth.sessions import consumir_desafio
        usuario = self._usuario()
        token = criar_token_2fa_pendente(usuario)
        consumir_desafio(self.db, token, usuario, "2fa_pendente")
        self.db.rollback()
        consumir_desafio(self.db, token, usuario, "2fa_pendente")
        self.db.commit()

    def test_cookie_de_sessao_e_http_only_com_same_site_e_secure_configuravel(self):
        from routes.auth import _salvar_cookie_de_sessao

        resposta = Response()
        with patch.dict(os.environ, {"COOKIE_SECURE": "true"}):
            _salvar_cookie_de_sessao(resposta, "token-teste")

        cookie = resposta.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("secure", cookie)
        self.assertIn("path=/", cookie)
        self.assertNotIn("max-age", cookie)

    def test_respostas_tem_headers_basicos_e_endpoints_auth_nao_sao_cacheaveis(self):
        status, headers, _ = self._request("GET", "/")
        self.assertEqual(200, status)
        self.assertEqual("nosniff", headers["x-content-type-options"])
        self.assertEqual("DENY", headers["x-frame-options"])
        self.assertEqual("strict-origin-when-cross-origin", headers["referrer-policy"])
        self.assertEqual("camera=(), geolocation=(), microphone=()", headers["permissions-policy"])

        status, headers, _ = self._request(
            "POST",
            "/api/auth/recuperacao/iniciar",
            {"email": "pessoa@example.test"},
        )
        self.assertEqual(200, status)
        self.assertEqual("no-store, max-age=0", headers["cache-control"])
        self.assertEqual("no-cache", headers["pragma"])

    def test_senha_nao_e_armazenada_em_texto_e_limite_bcrypt_em_bytes(self):
        senha = "SenhaSegura123!"
        senha_hash = hash_senha(senha)
        self.assertNotEqual(senha, senha_hash)
        self.assertTrue(verificar_senha(senha, senha_hash))
        self.assertFalse(verificar_senha("senha incorreta", senha_hash))
        self.assertFalse(verificar_senha("a" * 73, senha_hash))

    def test_cadastro_publico_nao_permite_autopromocao_para_admin(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CadastroUsuario.model_validate({'nome':'Conta','sobrenome':'Teste','interesse':'Direito Civil',
                'email':'autopromocao@example.test','senha':'SenhaSegura123!','confirmar_senha':'SenhaSegura123!',
                'consentimento_lgpd':True,'tipo_usuario':'administrador','e_root_admin':True})
        self.assertIsNone(self.db.query(Usuario).filter_by(email='autopromocao@example.test').first())

    def test_login_nao_revela_se_email_existe(self):
        self._usuario(email="existente@example.test")
        respostas = []
        for email in ("inexistente@example.test", "existente@example.test"):
            status, _, corpo = self._request(
                "POST",
                "/api/auth/login",
                {"email": email, "senha": "SenhaErrada123"},
            )
            respostas.append((status, json.loads(corpo)["detail"]))
        self.assertEqual(respostas[0], respostas[1])

    def test_busca_de_conteudo_nao_interpreta_entrada_como_sql(self):
        from model.models import Categoria, Conteudo, StatusConteudo

        autor = self._usuario()
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        self.db.add(categoria)
        self.db.flush()
        self.db.add(
            Conteudo(
                titulo="Conteúdo público aprovado",
                resumo_home="Resumo de teste suficientemente longo.",
                corpo_texto="Texto de teste.",
                status=StatusConteudo.APROVADO,
                categoria_id=categoria.uuid,
                autor_id=autor.uuid,
            )
        )
        self.db.add(
            Conteudo(
                titulo="Conteúdo ainda não aprovado",
                resumo_home="Este conteúdo deve permanecer privado.",
                corpo_texto="Texto reservado.",
                status=StatusConteudo.EM_ANALISE,
                categoria_id=categoria.uuid,
                autor_id=autor.uuid,
            )
        )
        self.db.commit()

        status, _, corpo = self._request("GET", "/api/conteudos")
        self.assertEqual(200, status)
        publico = json.loads(corpo)
        self.assertEqual(["Conteúdo público aprovado"], [item["titulo"] for item in publico])

        injecao = urlencode({"busca": "' OR 1=1 --"})
        status, _, corpo = self._request("GET", f"/api/conteudos?{injecao}")
        self.assertEqual(200, status)
        self.assertEqual([], json.loads(corpo))

    def test_recuperacao_exige_email_e_codigo_totp_e_token_nao_pode_ser_reutilizado(self):
        import pyotp

        from routes.auth import decifrar_segredo_2fa

        segredo = pyotp.random_base32()
        usuario = Usuario(
            uuid=str(uuid.uuid4()),
            nome="Conta para recuperação",
            email="recuperacao@example.test",
            senha_hash=hash_senha("SenhaSegura123!"),
            tipo_usuario=TipoUsuario.ESTUDANTE,
            totp_secret=cifrar_segredo_2fa(segredo),
            is_2fa_enabled=True,
        )
        self.db.add(usuario)
        self.db.commit()

        from routes.auth import ConfirmacaoRecuperacaoSenha, InicioRecuperacaoSenha

        desafio = iniciar_recuperacao_senha(InicioRecuperacaoSenha(email=usuario.email))["desafio_token"]
        with self.assertRaises(Exception) as contexto:
            validar_recuperacao_senha(
                ConfirmacaoRecuperacaoSenha(
                    email=usuario.email,
                    desafio_token=desafio,
                    codigo="000000" if pyotp.TOTP(segredo).now() != "000000" else "999999",
                ),
                self.db,
            )
        self.assertEqual(401, contexto.exception.status_code)

        codigo = pyotp.TOTP(decifrar_segredo_2fa(usuario.totp_secret)).now()
        autorizado = validar_recuperacao_senha(
            ConfirmacaoRecuperacaoSenha(
                email=usuario.email,
                desafio_token=desafio,
                codigo=codigo,
            ),
            self.db,
        )
        dados_nova_senha = NovaSenhaRecuperacao(
            token_redefinicao=autorizado["token_redefinicao"],
            nova_senha="NovaSenha!456",
            confirmar_senha="NovaSenha!456",
        )
        self.assertIn("sucesso", alterar_senha_recuperada(dados_nova_senha, self.db)["mensagem"].lower())
        self.assertTrue(verificar_senha("NovaSenha!456", usuario.senha_hash))

        with self.assertRaises(Exception) as contexto:
            alterar_senha_recuperada(dados_nova_senha, self.db)
        self.assertEqual(401, contexto.exception.status_code)


if __name__ == "__main__":
    unittest.main()
