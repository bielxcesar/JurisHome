"""Formatação editorial limitada: texto escapado, sem aceitar HTML do usuário."""
import json
import re
from html import escape
from typing import Literal
from urllib.parse import urlsplit
from pathlib import Path

from markupsafe import Markup
from pydantic import BaseModel, ConfigDict, Field

from services.imagens import url_fonte_segura, url_imagem_segura


def estilos_previa():
    pasta = Path(__file__).resolve().parents[1] / 'static' / 'css'
    # Somente arquivos estáticos do projeto; nenhum CSS enviado pelo usuário.
    return Markup('\n'.join((pasta / nome).read_text(encoding='utf-8') for nome in ('juris-ui.css', 'materia.css')))


class ImagemEditorial(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fonte: str = Field(default='', max_length=2000)
    legenda: str = Field(default='', max_length=240)
    alt: str = Field(default='', max_length=200)
    apos_bloco: int = Field(default=1, ge=0, le=1000)
    largura: Literal['normal', 'ampla'] = 'ampla'


class ConfiguracaoEditorial(BaseModel):
    model_config = ConfigDict(extra='forbid')
    titulo_home: str | None = Field(default=None, max_length=180)
    formatado: bool = True
    alinhamento: Literal['esquerda', 'justificado'] = 'esquerda'
    capa_legenda: str = Field(default='', max_length=240)
    capa_alt: str = Field(default='', max_length=200)
    imagens: list[ImagemEditorial] = Field(default_factory=list, max_length=3)


def credito(valor):
    texto = (valor or '').strip()
    url = url_fonte_segura(texto)
    if url:
        host = urlsplit(url).hostname or 'Fonte original'
        rotulo = host.removeprefix('www.')
        return {'texto': rotulo if len(rotulo) <= 70 else rotulo[:67] + '…', 'url': url, 'completo': texto}
    return {'texto': texto if len(texto) <= 90 else texto[:87] + '…', 'url': None, 'completo': texto}


def inline(texto):
    # A substituição só envolve texto já escapado, sem atributos ou links arbitrários.
    seguro = escape(texto)
    seguro = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', seguro)
    seguro = re.sub(r'_([^_\n]+)_', r'<em>\1</em>', seguro)
    seguro = re.sub(r'==([^=\n]+)==', r'<mark>\1</mark>', seguro)
    return Markup(seguro)


def blocos_texto(texto, formatado):
    blocos = []
    for linha in (texto or '').splitlines():
        linha = linha.strip()
        if not linha:
            continue
        tipo = 'paragrafo'
        if formatado:
            for prefixo, estilo in (('## ', 'subtitulo'), ('> ', 'citacao'), ('- ', 'lista')):
                if linha.startswith(prefixo):
                    tipo, linha = estilo, linha[len(prefixo):]
                    break
        blocos.append({'tipo': tipo, 'texto': inline(linha) if formatado else linha})
    return blocos


def montar_editorial(materia, configuracao=None):
    if configuracao is None:
        registro = getattr(materia, 'editorial', None)
        if registro:
            try:
                configuracao = ConfiguracaoEditorial.model_validate(json.loads(registro.configuracao_json))
            except (ValueError, TypeError):
                configuracao = None
    config = configuracao or ConfiguracaoEditorial(formatado=False)
    textos = blocos_texto(materia.corpo_texto, config.formatado)
    imagens = []
    for indice, valor in enumerate((materia.imagem_corpo, materia.imagem_extra_2, materia.imagem_extra_3)):
        url = url_imagem_segura(valor)
        if not url:
            continue
        opcoes = config.imagens[indice] if indice < len(config.imagens) else ImagemEditorial(apos_bloco=indice+1)
        imagens.append({'tipo': 'imagem', 'url': url, 'alt': opcoes.alt.strip() or f'Imagem complementar {indice+1} da matéria',
                        'legenda': opcoes.legenda, 'credito': credito(opcoes.fonte), 'largura': opcoes.largura,
                        'apos': min(opcoes.apos_bloco, len(textos))})
    blocos = []
    for posicao in range(len(textos)+1):
        blocos.extend(imagem for imagem in imagens if imagem['apos'] == posicao)
        if posicao < len(textos):
            blocos.append(textos[posicao])
    return {'blocos_editoriais': blocos, 'alinhamento_editorial': config.alinhamento,
            'credito_capa': credito(materia.fonte_imagem), 'legenda_capa': config.capa_legenda,
            'alt_capa': config.capa_alt.strip() or f'Imagem de apoio da matéria: {materia.titulo}'}
