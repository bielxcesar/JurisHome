(() => {
    'use strict';

    const form = document.getElementById('datajud-form');
    if (!form) return;

    const numero = document.getElementById('datajud-numero');
    const tribunal = document.getElementById('datajud-tribunal');
    const botao = document.getElementById('datajud-buscar');
    const status = document.getElementById('datajud-status');
    const resultado = document.getElementById('datajud-resultado');

    function informar(mensagem, erro = false) {
        status.textContent = mensagem;
        status.className = `mt-4 text-sm ${erro ? 'text-red-300' : 'text-gray-300'}`;
        status.hidden = !mensagem;
    }

    function adicionarCampo(lista, titulo, valor) {
        if (!valor) return;
        const grupo = document.createElement('div');
        const rotulo = document.createElement('dt');
        const dado = document.createElement('dd');
        rotulo.className = 'text-gray-500 text-xs uppercase tracking-wide';
        dado.className = 'text-gray-200 mt-1 break-words';
        rotulo.textContent = titulo;
        dado.textContent = valor;
        grupo.append(rotulo, dado);
        lista.append(grupo);
    }

    function formatarData(valor) {
        if (!valor) return '';
        const data = new Date(valor);
        return Number.isNaN(data.getTime()) ? valor : new Intl.DateTimeFormat('pt-BR', {dateStyle: 'medium', timeStyle: 'short'}).format(data);
    }

    function mostrarProcesso(dados) {
        resultado.replaceChildren();
        if (!dados.encontrado || !dados.processo) {
            informar('Nenhum processo público foi encontrado neste tribunal para o número informado.');
            return;
        }

        const processo = dados.processo;
        const cartao = document.createElement('article');
        cartao.className = 'datajud-card bg-[#1e1e1e] border border-gray-700 rounded-xl p-5';
        const titulo = document.createElement('h3');
        titulo.className = 'text-lg font-bold text-white mb-4';
        titulo.textContent = processo.numero_processo || 'Processo consultado';

        const campos = document.createElement('dl');
        campos.className = 'grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4';
        adicionarCampo(campos, 'Tribunal', processo.tribunal);
        adicionarCampo(campos, 'Grau', processo.grau);
        adicionarCampo(campos, 'Classe processual', processo.classe);
        adicionarCampo(campos, 'Órgão julgador', processo.orgao_julgador);
        adicionarCampo(campos, 'Data de ajuizamento', formatarData(processo.data_ajuizamento));

        cartao.append(titulo, campos);
        if (Array.isArray(processo.assuntos) && processo.assuntos.length) {
            const bloco = document.createElement('section');
            bloco.className = 'mt-5';
            const cabecalho = document.createElement('h4');
            cabecalho.className = 'text-sm font-bold text-amber-500 mb-2';
            cabecalho.textContent = 'Assuntos';
            const lista = document.createElement('ul');
            lista.className = 'list-disc pl-5 text-sm text-gray-300 space-y-1';
            processo.assuntos.forEach(assunto => {
                const item = document.createElement('li');
                item.textContent = assunto;
                lista.append(item);
            });
            bloco.append(cabecalho, lista);
            cartao.append(bloco);
        }
        if (Array.isArray(processo.movimentos) && processo.movimentos.length) {
            const bloco = document.createElement('section');
            bloco.className = 'mt-5';
            const cabecalho = document.createElement('h4');
            cabecalho.className = 'text-sm font-bold text-amber-500 mb-2';
            cabecalho.textContent = 'Movimentações recentes';
            const lista = document.createElement('ul');
            lista.className = 'space-y-2 text-sm text-gray-300';
            processo.movimentos.forEach(movimento => {
                const item = document.createElement('li');
                const data = movimento.data ? `${formatarData(movimento.data)} — ` : '';
                item.textContent = `${data}${movimento.nome}`;
                lista.append(item);
            });
            bloco.append(cabecalho, lista);
            cartao.append(bloco);
        }

        const fonte = document.createElement('p');
        fonte.className = 'text-xs text-gray-500 mt-5 border-t border-gray-800 pt-3';
        fonte.textContent = `Fonte dos metadados: ${dados.fonte}. Os dados de partes não são exibidos pelo JurisHome.`;
        cartao.append(fonte);
        resultado.append(cartao);
        informar('Consulta concluída. Confira a fonte oficial para informações atualizadas.');
    }

    form.addEventListener('submit', async evento => {
        evento.preventDefault();
        const numeroInformado = numero.value.trim();
        const tribunalInformado = tribunal.value;
        if (!numeroInformado || !tribunalInformado) {
            informar('Preencha o número CNJ e selecione o tribunal.', true);
            return;
        }

        botao.disabled = true;
        resultado.replaceChildren();
        informar('Consultando a API pública do DataJud…');
        try {
            const resposta = await fetch('/api/glossario/datajud', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({numero_processo: numeroInformado, tribunal: tribunalInformado}),
            });
            let dados;
            try { dados = await resposta.json(); }
            catch (_) { throw new Error('O servidor retornou uma resposta inválida.'); }
            if (!resposta.ok) {
                const detalhe = typeof dados.detail === 'string' ? dados.detail : 'Não foi possível concluir a consulta.';
                throw new Error(detalhe);
            }
            mostrarProcesso(dados);
        } catch (erro) {
            resultado.replaceChildren();
            informar(erro.message || 'Não foi possível consultar o DataJud. Tente novamente.', true);
        } finally {
            botao.disabled = false;
        }
    });
})();
