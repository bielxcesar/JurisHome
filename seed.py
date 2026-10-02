import json
import sys
from datetime import datetime, timezone

import model.models
from database import Base, SQLALCHEMY_DATABASE_URL, SessionLocal, engine
from feedback_database import (
    FEEDBACK_DATABASE_URL,
    FeedbackSessionLocal,
    criar_tabela_feedback,
)
from model.models import (
    Categoria,
    Conteudo,
    FeedbackAtendimento,
    StatusConteudo,
    TipoFonte,
    TipoUsuario,
    Usuario,
)


AVISO_DEMONSTRACAO = (
    "CONTEÚDO FICTÍCIO PARA DEMONSTRAÇÃO. Não representa notícia, lei, decisão judicial, "
    "fonte oficial ou orientação jurídica. Use somente para testar a aplicação.\n\n"
)

CONTEUDOS_DEMONSTRACAO = (
    {
        "titulo": "[DEMONSTRAÇÃO] Caso didático sobre jornada de trabalho",
        "sub_titulo": "Registro fictício para testar a leitura de uma matéria.",
        "resumo_home": "Exemplo local fictício; não é notícia ou entendimento jurídico real.",
        "corpo_texto": AVISO_DEMONSTRACAO + "Texto de exemplo para demonstrar a página de matéria.",
        "tags": "demonstração, jornada de trabalho",
        "tipo_fonte": TipoFonte.DOUTRINA,
    },
    {
        "titulo": "[DEMONSTRAÇÃO] Exemplo de organização por categoria",
        "sub_titulo": "Registro fictício para testar filtros e listagens.",
        "resumo_home": "Exemplo local fictício para demonstrar a navegação por categorias.",
        "corpo_texto": AVISO_DEMONSTRACAO + "Texto de exemplo para demonstrar filtros e listagens.",
        "tags": "demonstração, categorias",
        "tipo_fonte": TipoFonte.LEGISLACAO,
    },
    {
        "titulo": "[DEMONSTRAÇÃO] Exemplo de conteúdo em destaque",
        "sub_titulo": "Registro fictício para testar os destaques da página inicial.",
        "resumo_home": "Exemplo local fictício para demonstrar os cards da página inicial.",
        "corpo_texto": AVISO_DEMONSTRACAO + "Texto de exemplo para demonstrar os destaques.",
        "tags": "demonstração, destaque",
        "tipo_fonte": TipoFonte.ACORDAO,
    },
)

FONTES_LEGADAS_DEMONSTRACAO = (
    "https://exemplo.com/materia-1",
    "https://exemplo.com/materia-2",
    "https://exemplo.com/materia-3",
)
EMAIL_USUARIO_DEMONSTRACAO = "demo@example.invalid"

FEEDBACKS_DEMONSTRACAO = (
    {
        "id": "fb-demo-001",
        "protocolo": "JH-DEMO-001",
        "tipo": "Sugestão",
        "assunto": "[DEMONSTRAÇÃO] Filtro de pesquisa",
        "mensagem": "REGISTRO FICTÍCIO. Exemplo para demonstrar o atendimento de feedback.",
        "avaliacao": 5,
        "status": "Recebido",
        "prioridade": "Normal",
    },
    {
        "id": "fb-demo-002",
        "protocolo": "JH-DEMO-002",
        "tipo": "Dificuldade de acesso",
        "assunto": "[DEMONSTRAÇÃO] Acesso pelo celular",
        "mensagem": "REGISTRO FICTÍCIO. Exemplo para testar a resposta da equipe.",
        "avaliacao": None,
        "status": "Em análise",
        "prioridade": "Alta",
    },
)


def _validar_bancos_locais() -> None:
    urls = [SQLALCHEMY_DATABASE_URL]
    if FEEDBACK_DATABASE_URL:
        urls.append(FEEDBACK_DATABASE_URL)
    if any(not url.lower().startswith("sqlite") for url in urls):
        raise RuntimeError(
            "O seed contém somente dados fictícios e só pode ser executado em banco SQLite local. "
            "Confira DATABASE_URL e FEEDBACK_DATABASE_URL; nenhum registro foi alterado."
        )


def _marcar_conteudos_legados(db) -> int:
    legados = (
        db.query(Conteudo)
        .filter(Conteudo.fonte_original.in_(FONTES_LEGADAS_DEMONSTRACAO))
        .all()
    )
    for conteudo in legados:
        demonstracao = CONTEUDOS_DEMONSTRACAO[
            FONTES_LEGADAS_DEMONSTRACAO.index(conteudo.fonte_original)
        ]
        conteudo.titulo = demonstracao["titulo"]
        conteudo.sub_titulo = demonstracao["sub_titulo"]
        conteudo.resumo_home = demonstracao["resumo_home"]
        conteudo.corpo_texto = demonstracao["corpo_texto"]
        conteudo.fonte_original = None
        conteudo.tags = demonstracao["tags"]
        conteudo.imagem_miniatura = None
        conteudo.imagem_corpo = None
        conteudo.fonte_imagem = None
        conteudo.tipo_fonte = demonstracao["tipo_fonte"]
        conteudo.status = StatusConteudo.APROVADO
    return len(legados)


def _criar_conteudos(db, categoria: Categoria, autor: Usuario) -> int:
    existentes = {
        titulo
        for (titulo,) in db.query(Conteudo.titulo)
        .filter(Conteudo.titulo.in_([item["titulo"] for item in CONTEUDOS_DEMONSTRACAO]))
        .all()
    }
    novos = [
        Conteudo(
            **demonstracao,
            fonte_original=None,
            imagem_miniatura=None,
            imagem_corpo=None,
            fonte_imagem=None,
            status=StatusConteudo.APROVADO,
            categoria_id=categoria.uuid,
            autor_id=autor.uuid,
        )
        for demonstracao in CONTEUDOS_DEMONSTRACAO
        if demonstracao["titulo"] not in existentes
    ]
    db.add_all(novos)
    return len(novos)


def _historico_demo(agora: datetime) -> str:
    return json.dumps(
        [{
            "id": "hist-demo",
            "tipo": "criacao",
            "autor": "Usuário fictício de demonstração",
            "descricao": "Registro fictício para demonstração local.",
            "criadoEm": agora.isoformat(),
            "visibilidade": "publica",
        }],
        ensure_ascii=True,
    )


def _criar_feedbacks(feedback_db) -> int:
    existentes = {
        identificador
        for (identificador,) in feedback_db.query(FeedbackAtendimento.id)
        .filter(FeedbackAtendimento.id.in_([item["id"] for item in FEEDBACKS_DEMONSTRACAO]))
        .all()
    }
    agora = datetime.now(timezone.utc)
    novos = [
        FeedbackAtendimento(
            **demonstracao,
            usuario_id="usr-demo-local",
            usuario_nome="Usuário fictício de demonstração",
            usuario_email=EMAIL_USUARIO_DEMONSTRACAO,
            respostas_json="[]",
            observacoes_json="[]",
            historico_json=_historico_demo(agora),
            novo=True,
            arquivado=False,
            criado_em=agora,
            atualizado_em=agora,
        )
        for demonstracao in FEEDBACKS_DEMONSTRACAO
        if demonstracao["id"] not in existentes
    ]
    feedback_db.add_all(novos)
    return len(novos)


def _sanitizar_feedbacks_legados(feedback_db) -> int:
    legados = {
        item.id: item
        for item in feedback_db.query(FeedbackAtendimento)
        .filter(FeedbackAtendimento.id.in_([item["id"] for item in FEEDBACKS_DEMONSTRACAO]))
        .all()
    }
    agora = datetime.now(timezone.utc)
    sanitizados = 0
    for demonstracao in FEEDBACKS_DEMONSTRACAO:
        feedback = legados.get(demonstracao["id"])
        if feedback is None:
            continue
        try:
            historico = json.loads(feedback.historico_json or "[]")
        except (TypeError, json.JSONDecodeError):
            historico = None
        historico_seguro = (
            isinstance(historico, list)
            and len(historico) == 1
            and isinstance(historico[0], dict)
            and historico[0].get("autor") == "Usuário fictício de demonstração"
            and historico[0].get("descricao") == "Registro fictício para demonstração local."
            and historico[0].get("visibilidade") == "publica"
        )
        campos_divergentes = any(
            getattr(feedback, campo) != valor
            for campo, valor in demonstracao.items()
        )
        precisa_sanitizar = (
            campos_divergentes
            or feedback.usuario_id != "usr-demo-local"
            or feedback.usuario_nome != "Usuário fictício de demonstração"
            or feedback.usuario_email != EMAIL_USUARIO_DEMONSTRACAO
            or feedback.respostas_json != "[]"
            or feedback.observacoes_json != "[]"
            or not historico_seguro
            or not feedback.novo
            or feedback.arquivado
        )
        if not precisa_sanitizar:
            continue
        for campo, valor in demonstracao.items():
            setattr(feedback, campo, valor)
        feedback.usuario_id = "usr-demo-local"
        feedback.usuario_nome = "Usuário fictício de demonstração"
        feedback.usuario_email = EMAIL_USUARIO_DEMONSTRACAO
        feedback.respostas_json = "[]"
        feedback.observacoes_json = "[]"
        feedback.historico_json = _historico_demo(agora)
        feedback.novo = True
        feedback.arquivado = False
        feedback.criado_em = agora
        feedback.atualizado_em = agora
        sanitizados += 1
    return sanitizados


def main() -> int:
    db = feedback_db = None
    try:
        _validar_bancos_locais()
        Base.metadata.create_all(bind=engine)
        criar_tabela_feedback()

        db = SessionLocal()
        feedback_db = FeedbackSessionLocal()
        autor = (
            db.query(Usuario)
            .filter(Usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR)
            .order_by(Usuario.criado_em.asc())
            .first()
        )
        if autor is None:
            raise RuntimeError(
                "Crie primeiro um administrador local com 'python criar_admin.py'; "
                "o seed nao cria contas nem credenciais."
            )

        categoria = db.query(Categoria).filter_by(nome="Direito Trabalhista").first()
        if categoria is None:
            categoria = Categoria(
                nome="Direito Trabalhista",
                descricao="Categoria usada nos registros ficticios de demonstracao local.",
            )
            db.add(categoria)
            db.flush()

        conteudos_legados = _marcar_conteudos_legados(db)
        feedbacks_legados = _sanitizar_feedbacks_legados(feedback_db)
        conteudos_criados = _criar_conteudos(db, categoria, autor)
        feedbacks_criados = _criar_feedbacks(feedback_db)
        db.commit()
        feedback_db.commit()
        print(f"{conteudos_criados} conteudo(s) ficticio(s) criado(s).")
        print(f"{feedbacks_criados} feedback(s) ficticio(s) criado(s).")
        if conteudos_legados or feedbacks_legados:
            print("Registros antigos do seed foram atualizados para identifica-los como demonstracao ficticia.")
        return 0
    except Exception as erro:
        if db is not None:
            db.rollback()
        if feedback_db is not None:
            feedback_db.rollback()
        print(f"Erro ao popular o banco local: {erro}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()
        if feedback_db is not None:
            feedback_db.close()


if __name__ == "__main__":
    raise SystemExit(main())
