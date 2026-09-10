from database import SessionLocal
from model.models import Usuario, Categoria, Subcategoria, Conteudo, StatusConteudo, TipoFonte, TipoUsuario

def popular_banco():
    db = SessionLocal()

    # 1. Cria Usuário Autor
    usuario = db.query(Usuario).filter(Usuario.email == "autor@jurishome.com").first()
    if not usuario:
        usuario = Usuario(
            nome="Autor de Teste",
            email="autor@jurishome.com",
            tipo_usuario=TipoUsuario.ADMINISTRADOR,
            e_root_admin=True
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    # 2. Cria Categoria
    categoria = db.query(Categoria).filter(Categoria.nome == "Direito Constitucional").first()
    if not categoria:
        categoria = Categoria(
            nome="Direito Constitucional",
            descricao="Artigos e conteúdos sobre a Constituição Federal."
        )
        db.add(categoria)
        db.commit()
        db.refresh(categoria)

    # 3. Cria Subcategoria
    subcategoria = db.query(Subcategoria).filter(Subcategoria.nome == "Direitos Fundamentais").first()
    if not subcategoria:
        subcategoria = Subcategoria(
            nome="Direitos Fundamentais",
            categoria_id=categoria.id
        )
        db.add(subcategoria)
        db.commit()
        db.refresh(subcategoria)

    # 4. Cria Conteúdo Aprovado
    conteudo_existente = db.query(Conteudo).filter(Conteudo.titulo == "Liberdade de Expressão").first()
    if not conteudo_existente:
        conteudo = Conteudo(
            titulo="Liberdade de Expressão",
            sub_titulo="Limites e garantias na Constituição Federal",
            resumo_home="Uma análise sobre a garantia da liberdade de expressão e seus contornos jurídicos.",
            corpo_texto="Texto completo do artigo explicativo sobre os Direitos Fundamentais...",
            tipo_fonte=TipoFonte.DOUTRINA,
            status=StatusConteudo.APROVADO,
            categoria_id=categoria.id,
            subcategoria_id=subcategoria.id,
            autor_id=usuario.id
        )
        db.add(conteudo)
        db.commit()

    db.close()
    print("Banco de dados populado com sucesso!")

if __name__ == "__main__":
    popular_banco()