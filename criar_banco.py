from database import engine, Base
# Importamos os modelos para que a ferramenta saiba o que precisa ser criado
import model.models 

print("Construindo as tabelas no PostgreSQL...")

# Esse comando olha para o models.py e cria as tabelas que ainda não existem
Base.metadata.create_all(bind=engine)

print("Tabelas criadas com sucesso! O banco está pronto para uso.")