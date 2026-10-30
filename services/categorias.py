"""Áreas do Direito e tags temáticas do catálogo editorial."""
import unicodedata

from sqlalchemy.exc import IntegrityError

from model.models import Categoria, Conteudo


CATALOGO = {
    "Direito Trabalhista": ("CLT", "emprego", "trabalho", "trabalhista", "serviço", "relações de trabalho"),
    "Direito do Consumidor": ("CDC", "consumidor", "consumo", "produto", "serviço", "relação de consumo"),
    "Direito Penal": ("criminal", "penal", "crime", "Código Penal", "processo penal", "justiça criminal"),
    "Direito Civil": ("Código Civil", "contratos", "responsabilidade civil", "família", "bens", "obrigações"),
    "Direito Constitucional": ("Constituição", "direitos fundamentais", "cidadania", "STF", "poderes do Estado"),
    "Direito Tributário": ("tributos", "impostos", "contribuições", "CTN", "tributário", "fiscal"),
    "Direito Administrativo": ("administração pública", "servidor público", "licitações", "atos administrativos", "serviço público"),
    "Direito Previdenciário": ("INSS", "previdência", "aposentadoria", "benefícios", "seguridade social"),
    "Direito Empresarial": ("empresa", "sociedades", "empresarial", "recuperação judicial", "atividade econômica"),
    "Direito Ambiental": ("meio ambiente", "ambiental", "sustentabilidade", "licenciamento", "proteção ambiental"),
}


DESCRICOES = {
    "Direito do Consumidor": "Estuda a proteção de quem compra produtos ou contrata serviços e as responsabilidades dos fornecedores. Abrange temas como publicidade, qualidade dos produtos, atendimento e relações de consumo.",
    "Direito Trabalhista": "Trata das relações de trabalho, especialmente entre empregados e empregadores. Explora temas como contratação, jornada, remuneração, condições de trabalho e direitos e deveres das partes.",
    "Direito Penal": "Estuda os crimes, as penas e os limites do poder de punir do Estado. Reúne temas sobre responsabilidade penal, proteção de bens jurídicos e garantias das pessoas envolvidas.",
    "Direito Civil": "Trata das relações da vida privada entre pessoas e organizações. Inclui assuntos como contratos, família, propriedade, sucessões e responsabilidade por danos.",
    "Direito Constitucional": "Estuda a Constituição, a organização do Estado e os direitos fundamentais. Ajuda a compreender a cidadania, a divisão dos poderes e as bases do sistema jurídico.",
    "Direito Tributário": "Examina os tributos e as relações entre o poder público e os contribuintes. Aborda impostos, taxas, contribuições e os limites da tributação.",
    "Direito Administrativo": "Trata da organização e da atuação da administração pública. Abrange serviços públicos, agentes públicos, licitações e o controle das atividades do Estado.",
    "Direito Previdenciário": "Estuda a proteção previdenciária e as relações entre segurados, dependentes e os regimes de previdência. Inclui temas como contribuições, aposentadorias e outros benefícios.",
    "Direito Empresarial": "Estuda a atividade econômica organizada e as relações jurídicas das empresas. Explora sociedades, contratos empresariais, títulos de crédito e situações de crise empresarial.",
    "Direito Ambiental": "Trata da proteção do meio ambiente e da relação entre atividades humanas e recursos naturais. Abrange prevenção de danos, licenciamento, conservação e responsabilidade ambiental.",
}


def descricao_categoria(nome):
    return DESCRICOES.get(categoria_canonica(nome), "Esta área reúne matérias e conceitos relacionados ao tema selecionado. Explore as publicações abaixo para conhecer seus principais assuntos.")


def normalizar(valor):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", valor.casefold()) if not unicodedata.combining(c)).split())


ALIASES = {
    "direito do trabalho": "Direito Trabalhista", "trabalhista": "Direito Trabalhista", "trabalista": "Direito Trabalhista",
    "direito trabalhista": "Direito Trabalhista", "direito trabalista": "Direito Trabalhista",
    "consumidor": "Direito do Consumidor", "direito consumidor": "Direito do Consumidor",
    "criminal": "Direito Penal", "direito criminal": "Direito Penal", "penal": "Direito Penal",
    "direito penal (criminal)": "Direito Penal",
    **{normalizar(nome): nome for nome in CATALOGO},
}


def categoria_canonica(nome):
    return ALIASES.get(normalizar(nome or ""))


def tags_padrao(nome):
    return list(CATALOGO.get(categoria_canonica(nome), ()))


def combinar_tags(nome, extras=None):
    resultado, vistas = [], set()
    for valor in [*tags_padrao(nome), *(extras or "").split(",")]:
        tag = valor.strip().lstrip("#").strip()[:60]
        chave = normalizar(tag)
        if chave and chave not in vistas:
            resultado.append(tag)
            vistas.add(chave)
        if len(resultado) == 30:
            break
    return resultado


def garantir_categorias(db):
    """Adiciona somente áreas ausentes, preservando UUIDs e nomes existentes."""
    for tentativa in range(2):
        existentes = {categoria_canonica(item.nome) for item in db.query(Categoria).all()}
        novas = [Categoria(nome=nome) for nome in CATALOGO if nome not in existentes]
        if not novas:
            return 0
        db.add_all(novas)
        try:
            db.commit()
            return len(novas)
        except IntegrityError:
            db.rollback()
            if tentativa:
                raise


def corrigir_vinculos_legados(db):
    """Repara apenas os identificadores de exemplo usados no formulário antigo."""
    mapa = {"ID_DIREITO_TRABALHISTA": "Direito Trabalhista", "ID_DIREITO_PENAL": "Direito Penal"}
    existentes = {categoria_canonica(item.nome): item for item in db.query(Categoria).all()}
    total = 0
    for identificador, nome in mapa.items():
        categoria = existentes.get(nome)
        if not categoria or db.get(Categoria, identificador):
            continue
        for materia in db.query(Conteudo).filter_by(categoria_id=identificador).all():
            materia.categoria_id = categoria.uuid
            materia.tags = ", ".join(combinar_tags(categoria.nome, materia.tags))
            total += 1
    if total:
        db.commit()
    return total
