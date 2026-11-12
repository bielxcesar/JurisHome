"""Conteúdo introdutório e referências oficiais para as áreas do Direito."""

from copy import deepcopy

from services.categorias import CATALOGO, categoria_canonica, descricao_categoria


CONTEUDO_PEDAGOGICO = {
    "Direito Trabalhista": {
        "assuntos": ["Relações de emprego", "Jornada e remuneração", "Direitos e deveres de empregados e empregadores"],
        "cotidiano": "A área aparece em situações como contratação, pagamento, férias, jornada, segurança no trabalho e encerramento do vínculo de emprego.",
        "curiosidade": {
            "titulo": "O que significa CLT?",
            "texto": "A sigla se refere à Consolidação das Leis do Trabalho. O art. 2º da CLT também apresenta a definição legal de empregador.",
            "fonte": "CLT, art. 2º",
            "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm#art2",
        },
        "legislacoes": [
            {"nome": "Consolidação das Leis do Trabalho", "numero": "Decreto-Lei nº 5.452/1943", "artigos": "Arts. 2º, 3º, 58 e 74", "descricao": "Reúne normas sobre relações individuais e coletivas de trabalho, jornada e registro de horário.", "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm"},
        ],
    },
    "Direito do Consumidor": {
        "assuntos": ["Direitos básicos do consumidor", "Qualidade de produtos e serviços", "Práticas comerciais e contratos de consumo"],
        "cotidiano": "A área se relaciona a compras, contratação de serviços, publicidade, atendimento, cobranças e solução de problemas de consumo.",
        "curiosidade": {
            "titulo": "O CDC também trata de direitos coletivos",
            "texto": "Além de relações individuais, o Código prevê proteção e defesa de interesses coletivos e difusos dos consumidores.",
            "fonte": "Código de Defesa do Consumidor, arts. 81 e seguintes",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm#art81",
        },
        "legislacoes": [
            {"nome": "Código de Defesa do Consumidor", "numero": "Lei nº 8.078/1990", "artigos": "Arts. 6º, 18, 39 e 81", "descricao": "Apresenta direitos básicos, responsabilidade por produtos e serviços, práticas comerciais e tutela coletiva.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm"},
        ],
    },
    "Direito Penal": {
        "assuntos": ["Teoria do crime", "Crimes e penas", "Limites e garantias do poder de punir"],
        "cotidiano": "A área aparece na definição legal de crimes, na investigação de fatos e na aplicação de garantias durante processos criminais.",
        "curiosidade": {
            "titulo": "A lei penal precisa ser anterior ao fato",
            "texto": "O art. 1º do Código Penal estabelece que não há crime sem lei anterior que o defina, nem pena sem prévia cominação legal.",
            "fonte": "Código Penal, art. 1º",
            "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm#art1",
        },
        "legislacoes": [
            {"nome": "Código Penal", "numero": "Decreto-Lei nº 2.848/1940", "artigos": "Arts. 1º, 121, 129 e 155", "descricao": "Reúne regras gerais sobre aplicação da lei penal e descreve crimes e respectivas penas.", "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm"},
            {"nome": "Código de Processo Penal", "numero": "Decreto-Lei nº 3.689/1941", "artigos": "Arts. 4º e seguintes", "descricao": "Organiza regras do processo penal e da investigação criminal.", "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689.htm"},
        ],
    },
    "Direito Civil": {
        "assuntos": ["Pessoas e bens", "Contratos e obrigações", "Família, propriedade e responsabilidade civil"],
        "cotidiano": "A área está presente em contratos, relações familiares, propriedade, sucessões e pedidos de reparação por danos.",
        "curiosidade": {
            "titulo": "O Código Civil começa falando sobre pessoas",
            "texto": "O art. 1º afirma que toda pessoa é capaz de direitos e deveres na ordem civil.",
            "fonte": "Código Civil, art. 1º",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm#art1",
        },
        "legislacoes": [
            {"nome": "Código Civil", "numero": "Lei nº 10.406/2002", "artigos": "Arts. 104, 186, 421 e 927", "descricao": "Trata de pessoas, negócios jurídicos, contratos e responsabilidade civil.", "url": "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm"},
            {"nome": "Código de Processo Civil", "numero": "Lei nº 13.105/2015", "artigos": "Arts. 1º e seguintes", "descricao": "Estabelece regras para o processo civil e a atuação em juízo.", "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm"},
        ],
    },
    "Direito Constitucional": {
        "assuntos": ["Organização do Estado e dos Poderes", "Direitos e garantias fundamentais", "Controle de constitucionalidade"],
        "cotidiano": "A área ajuda a compreender direitos fundamentais, serviços públicos, eleições, competências dos entes federativos e limites dos poderes do Estado.",
        "curiosidade": {
            "titulo": "Os direitos fundamentais estão em diferentes partes da Constituição",
            "texto": "O art. 5º está no Título dos Direitos e Garantias Fundamentais, que também reúne direitos sociais, nacionalidade, direitos políticos e partidos políticos.",
            "fonte": "Constituição Federal, Título II",
            "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#tituloII",
        },
        "legislacoes": [
            {"nome": "Constituição da República Federativa do Brasil", "numero": "Constituição Federal de 1988", "artigos": "Arts. 1º, 5º, 6º, 37 e 60", "descricao": "Apresenta fundamentos e organização do Estado, direitos fundamentais, direitos sociais e processo de emenda constitucional.", "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"},
        ],
    },
    "Direito Tributário": {
        "assuntos": ["Tributos e espécies tributárias", "Obrigação e crédito tributário", "Limitações ao poder de tributar"],
        "cotidiano": "A área se relaciona a impostos, taxas e contribuições presentes em compras, rendimentos, propriedade e atividades empresariais.",
        "curiosidade": {
            "titulo": "Tributo não é punição por ato ilícito",
            "texto": "O art. 3º do Código Tributário Nacional define tributo e exclui de sua definição a sanção por ato ilícito.",
            "fonte": "Código Tributário Nacional, art. 3º",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm#art3",
        },
        "legislacoes": [
            {"nome": "Código Tributário Nacional", "numero": "Lei nº 5.172/1966", "artigos": "Arts. 3º, 113 e 142", "descricao": "Apresenta normas gerais do sistema tributário, obrigações e constituição do crédito tributário.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"},
            {"nome": "Constituição Federal", "numero": "Constituição Federal de 1988", "artigos": "Arts. 145 a 162", "descricao": "Reúne competências tributárias, limitações ao poder de tributar e regras de repartição de receitas.", "url": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"},
        ],
    },
    "Direito Administrativo": {
        "assuntos": ["Atos e poderes administrativos", "Serviços e agentes públicos", "Licitações e contratos públicos"],
        "cotidiano": "A área aparece no funcionamento de órgãos públicos, na prestação de serviços, em concursos, licitações e decisões administrativas.",
        "curiosidade": {
            "titulo": "A Lei nº 9.784/1999 tem âmbito federal",
            "texto": "Ela estabelece normas básicas para processos na Administração Pública Federal direta e indireta; o art. 2º enumera princípios aplicáveis.",
            "fonte": "Lei nº 9.784/1999, arts. 1º e 2º",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l9784.htm#art2",
        },
        "legislacoes": [
            {"nome": "Lei do Processo Administrativo Federal", "numero": "Lei nº 9.784/1999", "artigos": "Arts. 1º, 2º e 50", "descricao": "Define normas básicas do processo administrativo federal, princípios e hipóteses de motivação dos atos.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l9784.htm"},
            {"nome": "Lei de Licitações e Contratos Administrativos", "numero": "Lei nº 14.133/2021", "artigos": "Arts. 1º e seguintes", "descricao": "Estabelece normas gerais de licitação e contratação para a Administração Pública.", "url": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm"},
        ],
    },
    "Direito Previdenciário": {
        "assuntos": ["Segurados e dependentes", "Benefícios previdenciários", "Custeio e contribuições"],
        "cotidiano": "A área se relaciona a contribuições previdenciárias, aposentadorias, benefícios por incapacidade, pensões e proteção social.",
        "curiosidade": {
            "titulo": "A lei dos benefícios também organiza suas espécies",
            "texto": "O art. 18 da Lei nº 8.213/1991 lista prestações devidas a segurados e dependentes no Regime Geral de Previdência Social.",
            "fonte": "Lei nº 8.213/1991, art. 18",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm#art18",
        },
        "legislacoes": [
            {"nome": "Planos de Benefícios da Previdência Social", "numero": "Lei nº 8.213/1991", "artigos": "Arts. 18, 25 e 59", "descricao": "Dispõe sobre prestações previdenciárias, carência e benefícios do Regime Geral.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm"},
            {"nome": "Plano de Custeio da Seguridade Social", "numero": "Lei nº 8.212/1991", "artigos": "Arts. 10 e seguintes", "descricao": "Trata da organização do custeio da Seguridade Social.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l8212compilado.htm"},
        ],
    },
    "Direito Empresarial": {
        "assuntos": ["Empresário e sociedades", "Contratos e títulos empresariais", "Recuperação e falência"],
        "cotidiano": "A área aparece na abertura e organização de empresas, nas relações entre sócios, em contratos comerciais e em situações de crise empresarial.",
        "curiosidade": {
            "titulo": "Recuperação judicial e falência estão na mesma lei",
            "texto": "A Lei nº 11.101/2005 disciplina recuperação judicial, recuperação extrajudicial e falência do empresário e da sociedade empresária.",
            "fonte": "Lei nº 11.101/2005, art. 1º",
            "url": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101compilado.htm#art1",
        },
        "legislacoes": [
            {"nome": "Lei de Recuperação Judicial e Falência", "numero": "Lei nº 11.101/2005", "artigos": "Arts. 1º, 47 e seguintes", "descricao": "Regula recuperação judicial, recuperação extrajudicial e falência.", "url": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101compilado.htm"},
            {"nome": "Lei das Sociedades por Ações", "numero": "Lei nº 6.404/1976", "artigos": "Arts. 1º e 2º", "descricao": "Dispõe sobre características, capital e objeto das companhias e sociedades anônimas.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l6404consol.htm"},
        ],
    },
    "Direito Ambiental": {
        "assuntos": ["Política e licenciamento ambiental", "Responsabilidade por danos ambientais", "Proteção de recursos naturais"],
        "cotidiano": "A área está presente em licenciamento de atividades, conservação de recursos naturais, prevenção de danos e responsabilização por infrações ambientais.",
        "curiosidade": {
            "titulo": "A Lei de Crimes Ambientais prevê responsabilidade de pessoas jurídicas",
            "texto": "O art. 3º da Lei nº 9.605/1998 prevê responsabilização da pessoa jurídica nas hipóteses descritas no próprio dispositivo.",
            "fonte": "Lei nº 9.605/1998, art. 3º",
            "url": "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm#art3",
        },
        "legislacoes": [
            {"nome": "Política Nacional do Meio Ambiente", "numero": "Lei nº 6.938/1981", "artigos": "Arts. 2º e 9º", "descricao": "Estabelece objetivos e instrumentos da Política Nacional do Meio Ambiente.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l6938.htm"},
            {"nome": "Lei de Crimes Ambientais", "numero": "Lei nº 9.605/1998", "artigos": "Arts. 2º, 3º e 70", "descricao": "Trata de sanções penais e administrativas relacionadas a condutas lesivas ao meio ambiente.", "url": "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm"},
        ],
    },
}


def conteudo_categoria(nome: str) -> dict:
    """Retorna material introdutório e fontes oficiais para uma categoria conhecida."""
    canonica = categoria_canonica(nome)
    if canonica not in CATALOGO:
        return {
            "descricao": descricao_categoria(nome),
            "assuntos": [],
            "cotidiano": "",
            "curiosidade": None,
            "legislacoes": [],
        }

    resultado = deepcopy(CONTEUDO_PEDAGOGICO[canonica])
    resultado["descricao"] = descricao_categoria(canonica)
    return resultado
