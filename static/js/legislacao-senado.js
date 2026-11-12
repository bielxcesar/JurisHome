(() => {
    'use strict';

    const form = document.getElementById('legislacao-form');
    if (!form) return;

    const campoTipo = document.getElementById('legislacao-tipo');
    const campoNumero = document.getElementById('legislacao-numero');
    const campoAno = document.getElementById('legislacao-ano');
    const botao = document.getElementById('legislacao-buscar');
    const status = document.getElementById('legislacao-status');
    const resultado = document.getElementById('legislacao-resultado');

    const linhaTempo = document.getElementById('legislacao-linha-tempo');
    const seletorAno = document.getElementById('legislacao-ano-slider');
    const anoEscolhido = document.getElementById('legislacao-ano-escolhido');

    function atualizarLinhaTempo() {
        const ano = campoAno.valueAsNumber;
        const valido = Number.isInteger(ano) && campoAno.validity.valid;
        anoEscolhido.textContent = valido ? String(ano) : '—';
        if (valido) seletorAno.value = String(ano);
    }

    if (!campoAno.value) {
        campoAno.value = String(Math.min(Number(campoAno.max), Math.max(Number(campoAno.min), new Date().getFullYear())));
    }
    atualizarLinhaTempo();
    linhaTempo.hidden = false;
    seletorAno.addEventListener('input', () => {
        campoAno.value = seletorAno.value;
        atualizarLinhaTempo();
    });
    campoAno.addEventListener('input', atualizarLinhaTempo);

    function informar(mensagem, erro = false) {
        status.textContent = mensagem;
        status.className = `mt-4 text-sm ${erro ? 'text-red-300' : 'text-gray-300'}`;
        status.hidden = !mensagem;
    }

    function adicionarCampo(lista, rotulo, valor) {
        if (!valor) return;
        const grupo = document.createElement('div');
        const titulo = document.createElement('dt');
        const texto = document.createElement('dd');
        titulo.className = 'text-gray-500 text-xs uppercase tracking-wide';
        texto.className = 'text-gray-200 mt-1 break-words';
        titulo.textContent = rotulo;
        texto.textContent = valor;
        grupo.append(titulo, texto);
        lista.append(grupo);
    }

    function mostrarLegislacao(dados) {
        resultado.replaceChildren();
        if (!dados.encontrado || !dados.norma) {
            informar('Não encontramos uma norma com esses dados. Confira o tipo, o número e o ano.');
            return;
        }

        const norma = dados.norma;
        const cartao = document.createElement('article');
        cartao.className = 'legislacao-card bg-[#1e1e1e] border border-gray-700 rounded-xl p-5';
        const titulo = document.createElement('h3');
        titulo.className = 'text-lg font-bold text-white mb-4';
        titulo.textContent = norma.nome || 'Norma consultada';

        const campos = document.createElement('dl');
        campos.className = 'grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4';
        adicionarCampo(campos, 'Tipo', norma.tipo);
        adicionarCampo(campos, 'Número e ano', `${norma.numero || ''}${norma.ano ? ` / ${norma.ano}` : ''}`);
        adicionarCampo(campos, 'Data de assinatura', norma.data_assinatura);
        adicionarCampo(campos, 'Nome conhecido', norma.apelido);
        cartao.append(titulo, campos);

        if (norma.ementa) {
            const bloco = document.createElement('section');
            bloco.className = 'mt-5';
            const subtitulo = document.createElement('h4');
            subtitulo.className = 'text-sm font-bold text-amber-500 mb-2';
            subtitulo.textContent = 'Ementa';
            const texto = document.createElement('p');
            texto.className = 'text-gray-300 text-sm leading-relaxed';
            texto.textContent = norma.ementa;
            bloco.append(subtitulo, texto);
            cartao.append(bloco);
        }

        if (norma.url_documento) {
            try {
                const endereco = new URL(norma.url_documento);
                if (endereco.protocol === 'https:' && ['normas.leg.br', 'www.planalto.gov.br'].includes(endereco.hostname)) {
                    const link = document.createElement('a');
                    link.className = 'inline-flex mt-5 text-amber-500 hover:text-amber-400 underline font-semibold';
                    link.href = endereco.href;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = 'Consultar texto oficial';
                    cartao.append(link);
                }
            } catch (_) {}
        }

        const fonte = document.createElement('p');
        fonte.className = 'text-xs text-gray-500 mt-5 border-t border-gray-800 pt-3';
        fonte.textContent = `Fonte: ${dados.fonte || 'Dados Abertos do Senado Federal'}.`;
        cartao.append(fonte);
        resultado.append(cartao);
        informar('Consulta concluída. Consulte o texto oficial para conferir a redação vigente.');
    }

    form.addEventListener('submit', async evento => {
        evento.preventDefault();
        if (!form.reportValidity()) return;
        const tipo = campoTipo.value;
        const numero = campoNumero.value.trim();
        const ano = campoAno.valueAsNumber;
        botao.disabled = true;
        resultado.replaceChildren();
        informar('Consultando a norma selecionada…');
        try {
            const resposta = await fetch('/api/glossario/legislacao', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tipo, numero, ano}),
            });
            let dados;
            try { dados = await resposta.json(); }
            catch (_) { throw new Error('O servidor retornou uma resposta inválida.'); }
            if (!resposta.ok) {
                const detalhe = typeof dados.detail === 'string' ? dados.detail : 'Não foi possível concluir a consulta.';
                throw new Error(detalhe);
            }
            mostrarLegislacao(dados);
        } catch (erro) {
            resultado.replaceChildren();
            informar(erro.message || 'Não foi possível consultar a legislação. Tente novamente.', true);
        } finally {
            botao.disabled = false;
        }
    });
})();
