import json
from datetime import datetime

import model.models  # Força o carregamento dos modelos no Base metadata
from model.models import (
    Usuario,
    Categoria,
    Conteudo,
    FeedbackAtendimento,
    StatusConteudo,
    TipoFonte,
    TipoUsuario,
)
from database import engine, Base, SessionLocal
from feedback_database import FeedbackSessionLocal, criar_tabela_feedback

# Cria as tabelas atualizadas no SQLite
Base.metadata.create_all(bind=engine)
criar_tabela_feedback()

db = SessionLocal()
feedback_db = FeedbackSessionLocal()

try:
    # 1. Garante que existe um usuário autor e uma categoria
    autor = db.query(Usuario).first()
    if not autor:
        autor = Usuario(
            nome="Redação JurisHome",
            email="redacao@jurishome.com",
            tipo_usuario=TipoUsuario.ADMINISTRADOR,
            e_root_admin=True
        )
        db.add(autor)
        db.flush()

    categoria = db.query(Categoria).filter(Categoria.nome == "Direito Trabalhista").first()
    if not categoria:
        categoria = Categoria(nome="Direito Trabalhista", descricao="Notícias sobre legislação do trabalho")
        db.add(categoria)
        db.flush()

    # 2. Notícia 1 (Destaque Principal / Carrossel)
    n1 = Conteudo(
        titulo="O que muda no pagamento de horas extras para quem trabalha em regime de home office? Entenda",
        sub_titulo="Tribunal Superior do Trabalho fixa novos entendimentos sobre controle de jornada remota.",
        resumo_home="Com as atualizações na legislação, empresas e funcionários buscam entender como funciona o controle de ponto à distância.",
        corpo_texto="A regulamentação do trabalho remoto passou por novas interpretações nos tribunais regionais...",
        fonte_original="https://exemplo.com/materia-1",
        tags="home office, horas extras, CLT, direito trabalhista",
        imagem_miniatura="https://images.unsplash.com/photo-1584438784894-089d6a62b8fa?w=600&auto=format&fit=crop",
        imagem_corpo="https://images.unsplash.com/photo-1584438784894-089d6a62b8fa?w=1200&auto=format&fit=crop",
        fonte_imagem="Unsplash / Banco de Imagens",
        tipo_fonte=TipoFonte.ACORDAO,
        status=StatusConteudo.APROVADO,
        categoria_id=categoria.uuid,
        autor_id=autor.uuid
    )

    # 3. Notícia 2 (Card Superior Direito)
    n2 = Conteudo(
        titulo="Justiça reverte justa causa de funcionária demitida após discussão no refeitorio da empresa; VÍDEO",
        sub_titulo="Decisão considerou que a punição foi desproporcional ao incidente ocorrido.",
        resumo_home="Decisão considerou a medida desproporcional por ausência de histórico de advertências prévias.",
        corpo_texto="Uma decisão recente da Justiça do Trabalho reverteu a demissão por justa causa de uma colaboradora...",
        fonte_original="https://exemplo.com/materia-2",
        tags="justa causa, demissão, justa causa revertida, tribunais",
        imagem_miniatura="https://images.unsplash.com/photo-1450133064473-71024230f91b?w=600&auto=format&fit=crop",
        imagem_corpo="https://images.unsplash.com/photo-1450133064473-71024230f91b?w=1200&auto=format&fit=crop",
        fonte_imagem="Unsplash / Banco de Imagens",
        tipo_fonte=TipoFonte.ACORDAO,
        status=StatusConteudo.APROVADO,
        categoria_id=categoria.uuid,
        autor_id=autor.uuid
    )

    # 4. Notícia 3 (Card Inferior Direito)
    n3 = Conteudo(
        titulo="Empresa é condenada a pagar indenização após chefe cobrar metas de madrugada pelo WhatsApp",
        sub_titulo="Mensagens fora do horário de expediente configuraram dano moral e assédio.",
        resumo_home="Juízo considerou que mensagens fora do expediente configuram violação ao direito de desconexão.",
        corpo_texto="Enviar mensagens exigindo relatórios de madrugada gera indenização por danos morais...",
        fonte_original="https://exemplo.com/materia-3",
        tags="whatsapp, assedio moral, desconexão, metas",
        imagem_miniatura="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=600&auto=format&fit=crop",
        imagem_corpo="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1200&auto=format&fit=crop",
        fonte_imagem="Unsplash / Banco de Imagens",
        tipo_fonte=TipoFonte.LEGISLACAO,
        status=StatusConteudo.APROVADO,
        categoria_id=categoria.uuid,
        autor_id=autor.uuid
    )

    conteudos_demo = [n1, n2, n3]
    fontes_demo = [conteudo.fonte_original for conteudo in conteudos_demo]
    fontes_existentes = {
        fonte
        for (fonte,) in db.query(Conteudo.fonte_original)
        .filter(Conteudo.fonte_original.in_(fontes_demo))
        .all()
    }
    novos_conteudos = [
        conteudo
        for conteudo in conteudos_demo
        if conteudo.fonte_original not in fontes_existentes
    ]

    db.add_all(novos_conteudos)

    feedbacks_demo = [
        FeedbackAtendimento(
            id="fb-demo-001",
            protocolo="JH-20260911-1042",
            usuario_id="usr-erick",
            usuario_nome="Erick Santos",
            usuario_email="erick.santos@aluno.umc.br",
            tipo="Sugestão",
            assunto="Filtro por tribunal na pesquisa",
            mensagem="Podiam colocar filtros por tribunal e período na pesquisa? Isso ajudaria bastante.",
            avaliacao=5,
            status="Recebido",
            prioridade="Normal",
            respostas_json="[]",
            observacoes_json="[]",
            historico_json=json.dumps([
                {
                    "id": "hist-demo-001",
                    "tipo": "criacao",
                    "autor": "Erick Santos",
                    "descricao": "Feedback enviado.",
                    "criadoEm": "2026-09-11T09:14:00-03:00",
                    "visibilidade": "publica",
                }
            ], ensure_ascii=False),
            novo=True,
            arquivado=False,
            criado_em=datetime.fromisoformat("2026-09-11T09:14:00-03:00"),
            atualizado_em=datetime.fromisoformat("2026-09-11T09:14:00-03:00"),
        ),
        FeedbackAtendimento(
            id="fb-demo-002",
            protocolo="JH-20260909-0837",
            usuario_id="usr-pedro",
            usuario_nome="Pedro Henrique",
            usuario_email="pedro.henrique@aluno.umc.br",
            tipo="Dificuldade de acesso",
            assunto="Não consigo acessar pelo celular",
            mensagem="No celular, depois que digito o código de verificação, o sistema volta para a tela de login.",
            avaliacao=None,
            status="Em análise",
            prioridade="Alta",
            respostas_json="[]",
            observacoes_json="[]",
            historico_json=json.dumps([
                {
                    "id": "hist-demo-002-a",
                    "tipo": "criacao",
                    "autor": "Pedro Henrique",
                    "descricao": "Feedback enviado.",
                    "criadoEm": "2026-09-09T18:22:00-03:00",
                    "visibilidade": "publica",
                },
                {
                    "id": "hist-demo-002-b",
                    "tipo": "status",
                    "autor": "Equipe JurisHome",
                    "descricao": "Estamos verificando o problema de acesso.",
                    "criadoEm": "2026-09-10T08:37:00-03:00",
                    "visibilidade": "publica",
                },
            ], ensure_ascii=False),
            novo=False,
            arquivado=False,
            criado_em=datetime.fromisoformat("2026-09-09T18:22:00-03:00"),
            atualizado_em=datetime.fromisoformat("2026-09-10T08:37:00-03:00"),
        ),
    ]
    ids_feedback_demo = [feedback.id for feedback in feedbacks_demo]
    ids_feedback_existentes = {
        feedback_id
        for (feedback_id,) in feedback_db.query(FeedbackAtendimento.id)
        .filter(FeedbackAtendimento.id.in_(ids_feedback_demo))
        .all()
    }
    novos_feedbacks = [
        feedback for feedback in feedbacks_demo if feedback.id not in ids_feedback_existentes
    ]
    feedback_db.add_all(novos_feedbacks)
    db.commit()
    feedback_db.commit()
    print(f"{len(novos_conteudos)} conteúdo(s) de demonstração criado(s).")
    print(f"{len(novos_feedbacks)} feedback(s) de demonstração criado(s).")

except Exception as e:
    db.rollback()
    feedback_db.rollback()
    print(f"Erro ao popular o banco de dados: {e}")

finally:
    db.close()
    feedback_db.close()
