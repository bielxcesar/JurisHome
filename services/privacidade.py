"""Minimização de dados apresentados na administração."""


def mascarar_email(email: str | None) -> str:
    """Máscara de exibição; o endereço original continua sendo dado pessoal."""
    if not email or "@" not in email:
        return "***"
    local, dominio = email.rsplit("@", 1)
    return f"{local[:1]}***@{dominio[:1]}***"
