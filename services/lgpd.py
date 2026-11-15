"""Versão vigente e texto dos documentos legais."""

from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from model.models import RevisaoLegal, Usuario

TERMOS_VERSAO = "2.2"
POLITICA_PRIVACIDADE_VERSAO = "2.2"
LIMITE_DOCUMENTO = 30000

DOCUMENTOS = {
    "termos": ("Termo de Aceite", "termos.html", "termos"),
    "privacidade": ("Política de Privacidade", "politica_privacidade.html", "politica"),
}


def revisao_vigente(db: Session) -> RevisaoLegal | None:
    return db.scalar(select(RevisaoLegal).order_by(RevisaoLegal.id.desc()).limit(1))


def versao_legal(revisao: RevisaoLegal | None) -> str:
    return f"legal-{revisao.id}" if revisao else TERMOS_VERSAO


def aceite_pendente(db: Session, usuario: Usuario) -> bool:
    revisao = revisao_vigente(db)
    return revisao is not None and (
        not usuario.consentimento_lgpd or usuario.versao_termos != versao_legal(revisao)
    )


class _TextoDocumento(HTMLParser):
    """Extrai o conteúdo inicial dos documentos distribuídos com o site."""

    def __init__(self):
        super().__init__()
        self.partes = []
        self.descricao = False
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.descricao = True
        if not self.descricao:
            return
        if tag == "li":
            self.partes.append("\n• ")
        elif tag == "a":
            self.link = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if not self.descricao:
            return
        if tag in {"td", "th"}:
            self.partes.append(" | ")
        elif tag in {"h2", "h3", "p", "li", "tr", "section"}:
            self.partes.append("\n")
        elif tag == "a" and self.link:
            self.partes.append(f" ({self.link})")
            self.link = None
        if tag == "section":
            self.partes.append("\n")
            self.descricao = False

    def handle_data(self, data):
        if self.descricao and data.strip():
            inicio = " " if data[0].isspace() else ""
            fim = " " if data[-1].isspace() else ""
            self.partes.append(inicio + " ".join(data.split()) + fim)


def texto_inicial(tipo: str) -> str:
    arquivo = Path(__file__).resolve().parents[1] / "templates" / DOCUMENTOS[tipo][1]
    parser = _TextoDocumento()
    parser.feed(arquivo.read_text(encoding="utf-8"))
    return "\n".join(linha.strip().removesuffix(" |") for linha in "".join(parser.partes).strip().splitlines())
