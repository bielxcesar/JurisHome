import model.models  # Força o carregamento dos modelos no Base metadata
from model.models import Usuario, Categoria, Conteudo, StatusConteudo, TipoFonte, TipoUsuario
from database import engine, Base, SessionLocal

# Cria as tabelas atualizadas no SQLite
Base.metadata.create_all(bind=engine)

db = SessionLocal()

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

    db.add_all([n1, n2, n3])
    db.commit()
    print("Dados fictícios criados com sucesso!")

except Exception as e:
    db.rollback()
    print(f"Erro ao popular o banco de dados: {e}")

finally:
    db.close()