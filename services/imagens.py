"""Valida e normaliza imagens de matérias sem serviço externo."""
import base64
import binascii
import re
import warnings
from urllib.parse import urlsplit
from io import BytesIO

from PIL import Image, UnidentifiedImageError

LIMITE_IMAGEM_BYTES = 1024 * 1024
DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/]+={0,2})$")


def url_fonte_segura(valor: str | None) -> str | None:
    if not valor:
        return None
    valor = valor.strip()
    try:
        url = urlsplit(valor)
        if url.scheme.lower() in {"http", "https"} and url.netloc and not any(ord(c) < 32 for c in valor):
            return valor
    except ValueError:
        pass
    return None


def url_imagem_segura(valor: str | None) -> str | None:
    if not valor:
        return None
    if DATA_URL.fullmatch(valor):
        return valor
    if valor.startswith("/static/") and not any(c in valor for c in ('"', "'", "<", ">", "\\")):
        return valor
    return url_fonte_segura(valor)


def normalizar_imagem(valor: str | None) -> str | None:
    if not valor:
        return None
    if len(valor) > 4 * ((LIMITE_IMAGEM_BYTES + 2) // 3) + 64:
        raise ValueError("A imagem deve ter no máximo 1 MB antes da codificação Base64.")
    correspondencia = DATA_URL.fullmatch(valor)
    if not correspondencia:
        raise ValueError("Envie uma imagem JPEG, PNG ou WebP em Base64.")
    try:
        dados = base64.b64decode(correspondencia[2], validate=True)
        if len(dados) > LIMITE_IMAGEM_BYTES:
            raise ValueError("Imagem muito grande.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(dados)) as imagem:
                if imagem.format not in {"JPEG", "PNG", "WEBP"} or imagem.width * imagem.height > 16_000_000:
                    raise ValueError("Formato ou dimensões inválidos.")
                imagem.load()
                imagem = imagem.convert("RGB")
                imagem.thumbnail((800, 800))
                saida = BytesIO()
                imagem.save(saida, format="JPEG", quality=70)
                if saida.tell() > LIMITE_IMAGEM_BYTES:
                    raise ValueError("Imagem muito grande.")
                return "data:image/jpeg;base64," + base64.b64encode(saida.getvalue()).decode("ascii")
    except (binascii.Error, OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as erro:
        raise ValueError("Imagem inválida ou acima dos limites permitidos.") from erro
