(() => {
    "use strict";

    const painel = document.getElementById("perfil-dashboard");
    if (!painel) return;

    const status = document.getElementById("perfil-dashboard-status");
    const totalMaterias = document.getElementById("dashboard-materias-total");
    const seletorPeriodo = document.getElementById("dashboard-periodo");
    const barras = document.getElementById("dashboard-categorias-barras");
    const vazio = document.getElementById("dashboard-categorias-vazio");
    const periodoLegivel = document.getElementById("dashboard-categorias-periodo");
    const tentarNovamente = document.getElementById("dashboard-tentar-novamente");
    const formatarNumero = valor => Math.max(0, Number(valor) || 0).toLocaleString("pt-BR");
    const cores = ["#38a3ff", "#4bbe75", "#f87171", "#f5b32c", "#bd70ff", "#21c9cd", "#f59e0b", "#939aaa"];
    let requisicaoAtual = 0;

    function nomePeriodo(dias) {
        return `Últimos ${dias} dias`;
    }

    function dataLegivel(valor) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(valor || "")) return "";
        const [ano, mes, dia] = valor.split("-");
        return `${dia}/${mes}/${ano}`;
    }

    function informar(mensagem, estado = "carregando") {
        status.textContent = mensagem;
        status.dataset.estado = estado;
    }

    function limparResumo() {
        totalMaterias.textContent = "—";
        barras.replaceChildren();
        barras.hidden = true;
        vazio.hidden = false;
        vazio.textContent = "Aguardando os dados do período.";
    }

    function desenharBarras(registros, dias) {
        barras.replaceChildren();
        const dados = Array.isArray(registros)
            ? registros.filter(item => item && Number(item.quantidade) > 0)
            : [];

        if (!dados.length) {
            barras.hidden = true;
            vazio.hidden = false;
            vazio.textContent = `Você ainda não acessou nenhuma categoria nos ${dias} dias selecionados.`;
            return false;
        }

        vazio.hidden = true;
        barras.hidden = false;
        const maiorValor = Math.max(...dados.map(item => Number(item.quantidade) || 0));
        const periodo = nomePeriodo(dias).toLocaleLowerCase("pt-BR");

        dados.forEach((item, indice) => {
            const quantidade = Math.max(0, Number(item.quantidade) || 0);
            const nomeCategoria = item.categoria || "Outra categoria";
            const cor = cores[indice % cores.length];
            const linha = document.createElement("li");
            linha.className = "perfil-bar-row";

            const cabecalho = document.createElement("div");
            cabecalho.className = "perfil-bar-heading";
            const nome = document.createElement("span");
            nome.className = "perfil-bar-name";
            nome.textContent = nomeCategoria;
            const valor = document.createElement("strong");
            valor.className = "perfil-bar-value";
            valor.textContent = `${formatarNumero(quantidade)} ${quantidade === 1 ? "acesso" : "acessos"}`;
            cabecalho.append(nome, valor);

            const trilho = document.createElement("div");
            trilho.className = "perfil-bar-track";
            trilho.setAttribute("role", "progressbar");
            trilho.setAttribute("aria-label", `${nomeCategoria}: acessos no período`);
            trilho.setAttribute("aria-valuemin", "0");
            trilho.setAttribute("aria-valuemax", String(maiorValor));
            trilho.setAttribute("aria-valuenow", String(quantidade));
            trilho.setAttribute("aria-valuetext", `${formatarNumero(quantidade)} ${quantidade === 1 ? "acesso" : "acessos"} nos ${periodo}`);
            const preenchimento = document.createElement("span");
            preenchimento.className = "perfil-bar-fill";
            preenchimento.style.width = `${Math.max(2, (quantidade / maiorValor) * 100)}%`;
            preenchimento.style.setProperty("--categoria-cor", cor);
            preenchimento.setAttribute("aria-hidden", "true");
            trilho.append(preenchimento);

            linha.append(cabecalho, trilho);
            barras.append(linha);
        });

        return true;
    }

    function atualizarPeriodo(dados, dias) {
        const inicio = dataLegivel(dados?.periodo?.inicio);
        const fim = dataLegivel(dados?.periodo?.fim);
        periodoLegivel.textContent = inicio && fim
            ? `${nomePeriodo(dias)} · ${inicio} a ${fim}`
            : nomePeriodo(dias);
    }

    async function carregarDashboard() {
        const requisicao = ++requisicaoAtual;
        const dias = Number(seletorPeriodo.value) === 90 ? 90 : 30;
        const periodo = nomePeriodo(dias).toLocaleLowerCase("pt-BR");
        painel.setAttribute("aria-busy", "true");
        tentarNovamente.hidden = true;
        periodoLegivel.textContent = nomePeriodo(dias);
        limparResumo();
        informar(`Carregando o resumo dos ${periodo}...`);

        try {
            const resposta = await fetch(`/api/perfil/dashboard?periodo=${dias}`, {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            if (!resposta.ok) throw new Error("dashboard indisponível");
            const dados = await resposta.json();
            if (requisicao !== requisicaoAtual) return;

            const indicadores = dados.indicadores || {};
            totalMaterias.textContent = formatarNumero(indicadores.materias_total);
            atualizarPeriodo(dados, dias);
            const temCategorias = desenharBarras(dados.categorias, dias);
            const semAtividade = !Number(indicadores.materias_total) && !temCategorias;
            informar(semAtividade
                ? `Ainda não há dados nos ${periodo} selecionados. Suas consultas e categorias acessadas aparecerão aqui.`
                : `Resumo atualizado para ${periodo}.`, "pronto");
        } catch (_erro) {
            if (requisicao !== requisicaoAtual) return;
            limparResumo();
            informar("Não foi possível carregar seu resumo agora. Tente novamente.", "erro");
            tentarNovamente.hidden = false;
        } finally {
            if (requisicao === requisicaoAtual) painel.setAttribute("aria-busy", "false");
        }
    }

    seletorPeriodo.addEventListener("change", carregarDashboard);
    tentarNovamente.addEventListener("click", carregarDashboard);
    carregarDashboard();
})();
