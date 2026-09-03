import os
from app.core.db.database import SessionLocal
from app.models.usuario import Usuario, TipoUsuario
from app.core.security import gerar_hash_senha

def criar_admin_inicial():
    db = SessionLocal()
    
    # Busca credenciais seguras das variáveis de ambiente do Railway
    admin_email = os.getenv("FIRST_ADMIN_EMAIL", "FabianADMIN@jurishome.com.br")
    admin_password = os.getenv("FIRST_ADMIN_PASSWORD", "SenhaLasanhaJuri123!")

    # Verifica se o admin já existe no banco
    admin_existente = db.query(Usuario).filter(Usuario.email == admin_email).first()
    
    if not admin_existente:
        admin = Usuario(
            nome="Administrador JurisHome",
            email=admin_email,
            senha_hash=gerar_hash_senha(admin_password),
            tipo_usuario=TipoUsuario.ADMINISTRADOR, # Define como Admin
            consentimento_lgpd=True
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin inicial ({admin_email}) criado com sucesso!")
    else:
        print("ℹ️ Admin inicial já existe no banco de dados.")
        
    db.close()

if __name__ == "__main__":
    criar_admin_inicial()