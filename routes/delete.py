"""

AQUI TEM UM SISTEMA ONDE ELE PROTEGE DE DELETE O USUARIO ADMIN PRINCIPAL (ROOT) E 
TAMBÉM GARANTE QUE SEMPRE HAJA PELO MENOS UM ADMINISTRADOR NO SISTEMA.

----------------------------------------------------------------------------

router = APIRouter()

@router.delete("/usuarios/{usuario_id}", status_code=204)
def deletar_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    admin_logado: Usuario = Depends(exigir_admin)
):
    usuario_alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    if not usuario_alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # TRAVA 1: Impedir exclusão do Admin Principal (Root)
    if usuario_alvo.e_root_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O Administrador Principal (Root) não pode ser excluído do sistema."
        )

    # TRAVA 2: Garantir que o sistema NUNCA fique com 0 administradores
    if usuario_alvo.tipo_usuario == TipoUsuario.ADMINISTRADOR:
        total_admins = db.query(Usuario).filter(
            Usuario.tipo_usuario == TipoUsuario.ADMINISTRADOR
        ).count()
        
        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operação negada. O sistema precisa manter ao menos um administrador ativo."
            )

    db.delete(usuario_alvo)
    db.commit()
    return None
"""