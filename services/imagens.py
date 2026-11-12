"""Valida e normaliza imagens de matérias sem serviço externo."""
import base64
import binascii
import re
import warnings
from urllib.parse import urlsplit
from io import BytesIO

from PIL import Image, UnidentifiedImageError

LIMITE_IMAGEM_BYTES = 1024 * 1024
LIMITE_IMAGEM_BASE64 = 4 * ((LIMITE_IMAGEM_BYTES + 2) // 3) + 64
FORMATOS = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
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
    if len(valor) > LIMITE_IMAGEM_BASE64:
        raise ValueError("A imagem deve ter no máximo 1 MB antes da codificação Base64.")
    correspondencia = DATA_URL.fullmatch(valor)
    if not correspondencia:
        raise ValueError("Envie uma imagem JPEG, PNG ou WebP em Base64.")
    try:
        dados = base64.b64decode(correspondencia[2], validate=True)
    except binascii.Error as erro:
        raise ValueError("Codificação Base64 inválida.") from erro
    jpeg = normalizar_imagem_bytes(dados, formato=FORMATOS[correspondencia[1]])
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def normalizar_imagem_bytes(dados, *, limite=LIMITE_IMAGEM_BYTES, tamanho=800, qualidade=70, formato=None):
    if len(dados) > limite:
        raise ValueError("Imagem acima do limite permitido.")
    formatos = (formato,) if formato else tuple(FORMATOS.values())
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(dados), formats=formatos) as imagem:
                if imagem.width * imagem.height > 16_000_000:
                    raise ValueError("Dimensões acima do limite permitido.")
                imagem.load()
                pixels = imagem.convert("RGB")
                pixels.thumbnail((tamanho, tamanho))
        # O JPEG recebe apenas pixels, sem comentários, EXIF ou bytes anexados.
        limpa = Image.new("RGB", pixels.size)
        limpa.paste(pixels)
        saida = BytesIO()
        limpa.save(saida, format="JPEG", quality=qualidade)
        if saida.tell() > limite:
            raise ValueError("Imagem acima do limite permitido.")
        return saida.getvalue()
    except (OSError, SyntaxError, ValueError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as erro:
        raise ValueError("Envie uma imagem JPEG, PNG ou WebP válida, no formato informado e dentro dos limites.") from erro
