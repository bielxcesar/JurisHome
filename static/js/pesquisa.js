(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
        document.getElementById("data-atual").textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
        configurarMenuPerfil();
        configurarSaida();
        const parametros = new URLSearchParams(window.location.search);
        const termo = parametros.get("q") || "";
        document.getElementById("campo-pesquisa").value = termo;
        if (termo.trim()) pesquisar(termo.trim());
    });

    document.getElementById("form-pesquisa").addEventListener("submit", (evento) => {
        evento.preventDefault();
        const termo = document.getElementById("campo-pesquisa").value.trim();
        const destino = new URL(window.location.href);
        if (termo) destino.searchParams.set("q", termo);
        else destino.searchParams.delete("q");
        history.replaceState({}, "", destino);
        if (termo) pesquisar(termo);
        else document.getElementById("search-results").hidden = true;
    });

    async function pesquisar(termo) {
        const area = document.getElementById("search-results");
        const lista = document.getElementById("search-result-list");
        const vazio = document.getElementById("search-empty");
        const contador = document.getElementById("search-count");
        area.hidden = false;
        lista.replaceChildren();
        vazio.hidden = true;
        contador.textContent = "Buscando...";
        try {
            const resposta = await fetch(`/api/conteudos?busca=${encodeURIComponent(termo)}`);
            const materias = await resposta.json();
            if (!resposta.ok) throw new Error(materias.detail || "Não foi possível concluir a pesquisa.");
            contador.textContent = `${materias.length} ${materias.length === 1 ? "resultado" : "resultados"}`;
            vazio.hidden = materias.length > 0;
            materias.forEach((materia) => {
                const link = document.createElement("a");
                link.className = "search-result";
                link.href = `/materia/${encodeURIComponent(materia.uuid)}`;
                const categoria = document.createElement("span");
                categoria.textContent = materia.categoria || "Direito";
                const titulo = document.createElement("h2");
                titulo.textContent = materia.titulo;
                const resumo = document.createElement("p");
                resumo.textContent = materia.resumo_home || materia.sub_titulo || "";
                const data = document.createElement("time");
                data.textContent = materia.criado_em || "";
                link.append(categoria, titulo, resumo, data);
                lista.append(link);
            });
        } catch (erro) {
            contador.textContent = "";
            vazio.hidden = false;
            vazio.textContent = erro.message;
        }
    }

    function configurarMenuPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");
        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
        });
        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) {
                menu.classList.remove("ativo");
                botao.setAttribute("aria-expanded", "false");
            }
        });
    }

    function configurarSaida() {
        document.querySelectorAll(".btn-desconectar").forEach((link) => {
            link.addEventListener("click", (evento) => {
                evento.preventDefault();
                fetch("/api/auth/logout", { method: "POST" }).finally(() => { window.location.href = "/"; });
            });
        });
    }
})();
