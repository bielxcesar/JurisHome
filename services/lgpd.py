"""Versão vigente e texto dos documentos legais."""

from html.parser import HTMLParser
from datetime import timezone
from pathlib import Path

from services.auditoria import registrar_auditoria

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from model.models import AceiteDocumento, LogAuditoria, RevisaoLegal, Usuario, obter_hora_local, fuso_br

TERMOS_VERSAO = "2.2"
POLITICA_PRIVACIDADE_VERSAO = "2.2"
LIMITE_DOCUMENTO = 30000

DOCUMENTOS = {
    "termos": ("Termo de Aceite", "termos.html", "termos"),
    "privacidade": ("Política de Privacidade", "politica_privacidade.html", "politica"),
}


VERSAO_BASE_ANTERIOR = "__versao_estatica_inicial__"


def revisao_vigente(db: Session) -> RevisaoLegal | None:
    revisao = db.scalar(select(RevisaoLegal).order_by(RevisaoLegal.id.desc()).limit(1))
    if revisao is not None:
        return revisao

    # Registra o conteúdo que já existia nos arquivos como versão-base, sem
    # alterar o identificador 2.2 aceito pelas contas anteriores.
    base = RevisaoLegal(
        anterior=VERSAO_BASE_ANTERIOR,
        termos=texto_inicial("termos"),
        politica=texto_inicial("privacidade"),
        publicada_em=obter_hora_local().replace(tzinfo=None),
    )
    db.add(base)
    try:
        db.commit()
        return base
    except IntegrityError:
        db.rollback()
        return db.scalar(select(RevisaoLegal).order_by(RevisaoLegal.id.desc()).limit(1))


def versao_legal(revisao: RevisaoLegal | None) -> str:
    if revisao is None or revisao.anterior == VERSAO_BASE_ANTERIOR:
        return TERMOS_VERSAO
    return f"legal-{revisao.id}"


def aceite_pendente(db: Session, usuario: Usuario) -> bool:
    if getattr(usuario.tipo_usuario, "value", usuario.tipo_usuario) != "estudante":
        return False
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


def registrar_aceite(db: Session, usuario: Usuario) -> None:
    if not usuario.versao_termos or not usuario.data_consentimento:
        return
    chave = (usuario.uuid, usuario.versao_termos)
    if db.get(AceiteDocumento, chave) is None:
        db.add(AceiteDocumento(usuario_id=usuario.uuid, versao=usuario.versao_termos,
                              aceito_em=usuario.data_consentimento))


def data_aceite_local(valor):
    if valor is None:
        return None
    # Aceites são gravados em UTC; a interface apresenta Brasília explicitamente.
    return (valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)).astimezone(fuso_br)


def historico_aceites(db: Session, usuario: Usuario) -> list[dict]:
    registros = {item.versao: item.aceito_em for item in db.query(AceiteDocumento).filter_by(usuario_id=usuario.uuid)}
    # Compatibilidade com aceites reais anteriores à tabela de histórico.
    logs = db.query(LogAuditoria).filter_by(usuario_id=usuario.uuid, acao="aceite_termo", resultado="sucesso").all()
    for log in logs:
        if log.recurso_id:
            registros.setdefault(log.recurso_id, log.criado_em)
    if usuario.consentimento_lgpd and usuario.versao_termos and usuario.data_consentimento:
        registros.setdefault(usuario.versao_termos, usuario.data_consentimento)
    return sorted(
        [{"versao": versao, "aceito_em": data_aceite_local(data)} for versao, data in registros.items()],
        key=lambda item: item["aceito_em"], reverse=True,
    )


def publicar_atualizacao_privacidade(db: Session) -> bool:
    """Preserva o texto do root e publica o complemento uma única vez na implantação."""
    revisao = revisao_vigente(db)
    arquivo = Path(__file__).resolve().parents[1] / "docs/lgpd/atualizacao_privacidade_20261120.txt"
    complemento = arquivo.read_text(encoding="utf-8").strip()
    marcador = complemento.splitlines()[0]
    if marcador in (revisao.politica or ""):
        return False
    nova = RevisaoLegal(anterior=versao_legal(revisao), termos=revisao.termos,
                        politica=(revisao.politica or texto_inicial("privacidade")) + "\n\n" + complemento,
                        publicada_em=obter_hora_local().replace(tzinfo=None))
    db.add(nova)
    try:
        db.flush()
        registrar_auditoria(db, acao="documento_legal_publicado", recurso_tipo="politica_privacidade",
                            recurso_id=versao_legal(nova), resultado="sucesso",
                            detalhes={"origem": "atualizacao_privacidade_20261120"})
        db.commit()
    except IntegrityError:
        # Outro worker pode ter publicado a mesma revisão de base.
        db.rollback()
        atual = revisao_vigente(db)
        if marcador not in (atual.politica or ""):
            raise
    return True
