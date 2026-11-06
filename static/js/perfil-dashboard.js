(() => {
    "use strict";

    const painel = document.getElementById("perfil-dashboard");
    if (!painel) return;

    const status = document.getElementById("perfil-dashboard-status");
    const totalMaterias = document.getElementById("dashboard-materias-total");
    const barras = document.getElementById("dashboard-categorias-barras");
    const vazio = document.getElementById("dashboard-categorias-vazio");
    const periodo = document.getElementById("dashboard-categorias-periodo");
    const tentarNovamente = document.getElementById("dashboard-tentar-novamente");
    const formatarNumero = valor => Math.max(0, Number(valor) || 0).toLocaleString("pt-BR");
    const cores = ["#38a3ff", "#4bbe75", "#f87171", "#f5b32c", "#bd70ff", "#21c9cd", "#f59e0b", "#939aaa"];

    function informar(mensagem, estado = "carregando") {
        status.textContent = mensagem;
        status.dataset.estado = estado;
    }

    function desenharBarras(registros) {
        barras.replaceChildren();
        const dados = Array.isArray(registros)
            ? registros.filter(item => item && Number(item.quantidade) > 0)
            : [];

        if (!dados.length) {
            barras.hidden = true;
            vazio.hidden = false;
            return false;
        }

        vazio.hidden = true;
        barras.hidden = false;
        const maiorValor = Math.max(...dados.map(item => Number(item.quantidade) || 0));

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
            trilho.setAttribute("aria-label", `${nomeCategoria}: acessos no mês`);
            trilho.setAttribute("aria-valuemin", "0");
            trilho.setAttribute("aria-valuemax", String(maiorValor));
            trilho.setAttribute("aria-valuenow", String(quantidade));
            trilho.setAttribute("aria-valuetext", `${formatarNumero(quantidade)} ${quantidade === 1 ? "acesso" : "acessos"} no mês`);
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

    function atualizarPeriodo(dados) {
        const inicio = dados?.periodo?.inicio;
        if (!inicio || !/^\d{4}-\d{2}-\d{2}$/.test(inicio)) return;
        const dataMes = new Date(`${inicio}T12:00:00`);
        const rotulo = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(dataMes);
        const mesLegivel = rotulo.charAt(0).toLocaleUpperCase("pt-BR") + rotulo.slice(1);
        periodo.textContent = `${mesLegivel}. A mesma categoria conta uma vez por dia, mesmo que você a acesse mais vezes.`;
    }

    async function carregarDashboard() {
        painel.setAttribute("aria-busy", "true");
        tentarNovamente.hidden = true;
        informar("Carregando seu resumo...");
        try {
            const resposta = await fetch("/api/perfil/dashboard", {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            if (!resposta.ok) throw new Error("dashboard indisponível");
            const dados = await resposta.json();
            const indicadores = dados.indicadores || {};

            totalMaterias.textContent = formatarNumero(indicadores.materias_total);
            atualizarPeriodo(dados);
            const temCategorias = desenharBarras(dados.categorias_mes);
            const semAtividade = !Number(indicadores.materias_total) && !temCategorias;
            informar(semAtividade
                ? "Ainda não há dados para mostrar. Suas consultas e categorias acessadas aparecerão aqui."
                : "Resumo atualizado.", "pronto");
        } catch (_erro) {
            informar("Não foi possível carregar seu resumo agora. Tente novamente.", "erro");
            tentarNovamente.hidden = false;
        } finally {
            painel.setAttribute("aria-busy", "false");
        }
    }

    tentarNovamente.addEventListener("click", carregarDashboard);
    carregarDashboard();
})();
