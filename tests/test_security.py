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
        dados = {'nome': 'Suporte de teste', 'email': 'SUPORTE@example.test', 'senha': 'SenhaSegura123'}
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
        self.assertNotEqual(nova.uuid, rodada.uuid)

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
        status, _, _ = self._request('POST', caminho, {'mensagem': 'Complemento privado'}, token=criar_access_token(outro))
        self.assertEqual(status, 404)
        status, _, corpo = self._request('POST', caminho, {'mensagem': 'Complemento do autor'}, token=token)
        self.assertEqual(status, 200)
        d = json.loads(corpo)
        self.assertEqual(d['status'], 'Em análise')
        self.assertTrue(d['novo'])
        self.assertNotIn('observacoesInternas', d)
        self.assertEqual(d['respostas'][-1]['papel'], 'leitor')
        self._request('POST', caminho, {'mensagem': 'Complemento do autor'}, token=token)
        self.db.expire_all()
        self.assertEqual(len(json.loads(self.db.get(models.FeedbackAtendimento, original['id']).respostas_json)), 1)
        for i in range(4):
            status, _, _ = self._request('POST', '/api/feedbacks', {**dados, 'assunto': f'Sugestão número {i}'}, token=token)
            self.assertEqual(status, 201)
        status, _, _ = self._request('POST', '/api/feedbacks', {**dados, 'assunto': 'Mais uma sugestão'}, token=token)
        self.assertEqual(status, 429)

    def test_perfil_persiste_instituicao_interesse_e_mostra_data_real(self):
        from routes.paginas import atualizar_perfil
        leitor = self._usuario()
        atualizar_perfil(nome='Leitor atualizado', faculdade='Universidade de teste', interesse='Direito Civil', foto=None, db=self.db, usuario=leitor)
        self.db.refresh(leitor)
        self.assertEqual(leitor.universidade, 'Universidade de teste')
        self.assertEqual(leitor.especialidade_juridica, 'Direito Civil')
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
                                  autor_id=autor.uuid, tipo_fonte=models.TipoFonte.DOUTRINA, status=models.StatusConteudo.APROVADO)
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
        dados.update(versao=novo['versao'], email='NOVO_ADMIN@example.test', nova_senha='NovaSenhaSegura123', resetar_2fa=True)
        status, _, corpo = self._request('PUT', caminho, dados, token=token_root)
        self.assertEqual(status, 200)
        self.db.expire_all()
        self.assertEqual(alvo.email, 'novo_admin@example.test')
        self.assertTrue(verificar_senha('NovaSenhaSegura123', alvo.senha_hash))
        self.assertIsNone(alvo.totp_secret)
        self.assertFalse(alvo.is_2fa_enabled)
        self.assertEqual(json.loads(corpo)['administrador']['sessoesAtivas'], 0)
        status, _, _ = self._request('GET', '/api/usuarios/me', token=token_alvo)
        self.assertEqual(status, 401)
        status, _, _ = self._request('GET', '/api/usuarios/me', token=token_root)
        self.assertEqual(status, 200)
        logs = self.db.query(models.LogAuditoria).filter_by(acao='administrador_atualizado').all()
        self.assertEqual(len(logs), 2)
        self.assertNotIn('NovaSenhaSegura123', ''.join(l.detalhes_json for l in logs))

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
                                  categoria_id=categoria.uuid, autor_id=alvo.uuid, tipo_fonte=models.TipoFonte.DOUTRINA,
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
                 'categoria_id': categoria.uuid, 'tipo_fonte': 'doutrina', 'imagem_miniatura': imagem,
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
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _usuario(self, papel=TipoUsuario.ESTUDANTE, email=None):
        usuario = Usuario(
            uuid=str(uuid.uuid4()),
            nome="Conta de teste",
            email=email or f"{uuid.uuid4().hex}@example.test",
            senha_hash=hash_senha("SenhaSegura123"),
            tipo_usuario=papel,
            totp_secret=cifrar_segredo_2fa("JBSWY3DPEHPK3PXP"),
            is_2fa_enabled=True,
        )
        self.db.add(usuario)
        self.db.commit()
        return usuario

    def _banco_teste(self):
        sessao = self.Session()
        try:
            yield sessao
        finally:
            sessao.close()

    def _request(self, method, path, data=None, token=None, cookie=None, extra_headers=(), suprimir_erro_interno=False):
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
            "client": ("testclient", 1234),
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

    def test_upload_rejeita_html_disfarcado_e_arquivo_grande(self):
        from io import BytesIO
        from fastapi import HTTPException, UploadFile
        from routes.paginas import atualizar_perfil

        usuario = self._usuario()
        for dados, esperado in ((b"<script>alert(1)</script>", 422), (b"x" * (2 * 1024 * 1024 + 1), 413)):
            with self.subTest(esperado=esperado):
                with self.assertRaises(HTTPException) as contexto:
                    atualizar_perfil(nome="Nome válido", faculdade=None, interesse=None, foto=UploadFile(filename="foto.jpg", file=BytesIO(dados)), db=self.db, usuario=usuario)
                self.assertEqual(esperado, contexto.exception.status_code)

    def test_materia_base64_so_aparece_apos_aprovacao_do_root(self):
        from io import BytesIO
        from PIL import Image
        from model.models import Categoria, Conteudo
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito de teste")
        self.db.add(categoria)
        self.db.commit()
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        saida = BytesIO()
        Image.new("RGB", (12, 8), "red").save(saida, format="PNG")
        imagem = "data:image/png;base64," + base64.b64encode(saida.getvalue()).decode("ascii")
        status, _, _ = self._request("POST", "/criar-materia", {
            "aceite_editorial": True, "versao_termos": "2026-10-30", "titulo": "Matéria Base64", "corpo_texto": "Texto da matéria.",
            "categoria_id": categoria.uuid, "tipo_fonte": "legislacao",
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
        status, _, _ = self._request("PUT", f"/aprovar-materia/{materia.uuid}", token=criar_access_token(root))
        self.assertEqual(200, status)
        status, _, corpo = self._request("GET", "/api/conteudos")
        self.assertEqual(["Matéria Base64"], [item["titulo"] for item in json.loads(corpo)])

    def test_materia_rejeita_categoria_inexistente_e_imagem_disfarcada(self):
        from model.models import Categoria
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        dados = {"titulo": "Teste", "corpo_texto": "Texto", "categoria_id": "inexistente", "tipo_fonte": "doutrina"}
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
        status, _, _ = self._request("POST", f"/api/admin/feedbacks/{criados[0]['id']}/respostas", {"mensagem": "Você pode consultar em Meus atendimentos."}, token=token_admin)
        self.assertEqual(200, status)
        status, _, _ = self._request("POST", f"/api/admin/feedbacks/{criados[0]['id']}/observacoes", {"mensagem": "Anotação exclusiva da equipe."}, token=token_admin)
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
        status, _, _ = self._request("POST", f"/api/admin/feedbacks/{feedback['id']}/respostas", {"mensagem": "Resposta administrativa."}, token=criar_access_token(admin))
        self.assertEqual(200, status)
        self.db.expire_all()
        registro = self.db.query(LogAuditoria).filter_by(acao="feedback_respondido").one()
        self.assertEqual(admin.uuid, registro.usuario_id)
        self.assertEqual("administrador", registro.usuario_tipo)

    def test_materia_renderiza_texto_seguro_base64_e_menu_por_perfil(self):
        from io import BytesIO
        from PIL import Image
        from model.models import Categoria, Conteudo, TipoFonte, StatusConteudo
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        estudante = self._usuario()
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Direito Civil")
        self.db.add(categoria)
        self.db.flush()
        imagem = BytesIO()
        Image.new("RGB", (20, 10), "gold").save(imagem, format="JPEG")
        base64_imagem = "data:image/jpeg;base64," + base64.b64encode(imagem.getvalue()).decode("ascii")
        materia = Conteudo(titulo="Matéria para leitura segura", resumo_home="Resumo de teste", corpo_texto='<script>alert("teste")</script>\n' + 'texto' * 250,
            categoria_id=categoria.uuid, autor_id=admin.uuid, tipo_fonte=TipoFonte.DOUTRINA, status=StatusConteudo.EM_ANALISE,
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
        self.assertIn("Direito do Consumidor", html)
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
        consumidor = self.db.query(Categoria).filter_by(nome="Direito do Consumidor").one()
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        token = criar_access_token(admin)
        status, _, _ = self._request("POST", "/criar-materia", {"aceite_editorial": True, "versao_termos": "2026-10-30", "titulo": "Tags por categoria", "corpo_texto": "Texto da matéria para teste.", "categoria_id": trabalhista.uuid, "tipo_fonte": "legislacao", "tags": "clt, Trabalho, bolsa de estudo"}, token=token)
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
        status, _, _ = self._request("PUT", f"/editar-materia/{materia.uuid}", {"categoria_id": consumidor.uuid}, token=token)
        self.assertEqual(200, status)
        self.db.refresh(materia)
        self.assertIn("CDC", materia.tags)
        self.assertIn("bolsa de estudo", materia.tags)
        self.assertNotIn("CLT", materia.tags)

    def test_corrige_apenas_vinculo_de_categoria_de_exemplo_conhecido(self):
        from model.models import Conteudo, TipoFonte, Categoria
        from services.categorias import garantir_categorias, corrigir_vinculos_legados
        admin = self._usuario(TipoUsuario.ADMINISTRADOR)
        garantir_categorias(self.db)
        materia = Conteudo(titulo="Matéria antiga", resumo_home="Resumo", corpo_texto="Texto", categoria_id="ID_DIREITO_PENAL", autor_id=admin.uuid, tipo_fonte=TipoFonte.DOUTRINA)
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

    def test_lembrar_conectado_nao_alonga_access_token(self):
        _, acesso, _, _ = self._sessao_renovavel()
        payload = security._decodificar_token(acesso)
        self.assertLessEqual(payload["exp"] - payload["iat"], 1800)

    def test_refresh_rota_e_reutilizacao_revoga_toda_a_sessao(self):
        from auth.sessions import renovar_sessao
        from model.models import SessaoAutenticada
        _, acesso, antigo, sid = self._sessao_renovavel()
        novo_acesso, novo_refresh, _ = renovar_sessao(self.db, antigo)
        self.assertNotEqual(antigo, novo_refresh)
        self.assertEqual(sid, security._decodificar_token(novo_acesso)["sid"])
        self.assertLessEqual((self.db.get(SessaoAutenticada, sid).expira_em - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds(), 14 * 86400)
        with self.assertRaises(Exception) as contexto:
            renovar_sessao(self.db, antigo)
        self.assertEqual(401, contexto.exception.status_code)
        self.assertTrue(self.db.get(SessaoAutenticada, sid).revogada)
        for token in (acesso, novo_acesso):
            status, _, _ = self._request("GET", "/api/usuarios/me", token=token)
            self.assertEqual(401, status)
        with self.assertRaises(Exception):
            renovar_sessao(self.db, novo_refresh)

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
        self.assertIn("max-age=1800", cookie)

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
        senha = "SenhaSegura123"
        senha_hash = hash_senha(senha)
        self.assertNotEqual(senha, senha_hash)
        self.assertTrue(verificar_senha(senha, senha_hash))
        self.assertFalse(verificar_senha("senha incorreta", senha_hash))
        self.assertFalse(verificar_senha("a" * 73, senha_hash))

    def test_cadastro_publico_nao_permite_autopromocao_para_admin(self):
        dados = CadastroUsuario.model_validate(
            {
                "nome": "Conta sem privilégios",
                "email": "autopromocao@example.test",
                "senha": "SenhaSegura123",
                "confirmar_senha": "SenhaSegura123",
                "consentimento_lgpd": True,
                "tipo_usuario": "administrador",
                "e_root_admin": True,
            }
        )
        asyncio.run(cadastrar_usuario(dados, Response(), self.db))
        usuario = self.db.query(Usuario).filter_by(email=dados.email).one()
        self.assertEqual(TipoUsuario.ESTUDANTE, usuario.tipo_usuario)
        self.assertFalse(usuario.e_root_admin)

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
        from model.models import Categoria, Conteudo, StatusConteudo, TipoFonte

        autor = self._usuario()
        categoria = Categoria(uuid=str(uuid.uuid4()), nome="Teste SQL")
        self.db.add(categoria)
        self.db.flush()
        self.db.add(
            Conteudo(
                titulo="Conteúdo público aprovado",
                resumo_home="Resumo de teste suficientemente longo.",
                corpo_texto="Texto de teste.",
                tipo_fonte=TipoFonte.ACORDAO,
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
                tipo_fonte=TipoFonte.ACORDAO,
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
            senha_hash=hash_senha("SenhaSegura123"),
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
