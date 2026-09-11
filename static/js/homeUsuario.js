(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTema();
        mostrarData();
        configurarPerfil();
        carregarMaterias();
    }

    function aplicarTema() {
        document.body.classList.toggle("modo-claro", window.localStorage.getItem("tema_juris") === "claro");
    }

    function mostrarData() {
        document.getElementById("data-atual").textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
    }

    function configurarPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");

        botao.addEventListener("click", (evento) => {
            evento.stopPropagation();
            const aberto = menu.classList.toggle("ativo");
            botao.setAttribute("aria-expanded", String(aberto));
        });

        document.addEventListener("click", (evento) => {
            if (!menu.contains(evento.target) && !botao.contains(evento.target)) fecharMenu();
        });
        document.addEventListener("keydown", (evento) => {
            if (evento.key === "Escape") fecharMenu();
        });

        function fecharMenu() {
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
        }
    }

    async function carregarMaterias() {
        try {
            const resposta = await window.fetch("/api/conteudos");
            if (!resposta.ok) throw new Error("Não foi possível carregar as matérias.");
            const materias = await resposta.json();
            if (!Array.isArray(materias) || materias.length === 0) {
                mostrarEstadoVazio();
                return;
            }

            preencherDestaque("card-destaque-principal", "hero-cat-1", "hero-titulo-1", materias[0]);
            preencherDestaque("card-destaque-2", "hero-cat-2", "hero-titulo-2", materias[1] || materias[0]);
            preencherDestaque("card-destaque-3", "hero-cat-3", "hero-titulo-3", materias[2] || materias[0]);
            preencherRecomendados(materias.slice(3));
        } catch (erro) {
            mostrarEstadoVazio("Não foi possível carregar as matérias agora.");
            console.error(erro);
        }
    }

    function preencherDestaque(cardId, categoriaId, tituloId, materia) {
        const card = document.getElementById(cardId);
        document.getElementById(categoriaId).textContent = materia.categoria || "Direito";
        document.getElementById(tituloId).textContent = materia.titulo;
        card.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.88)), url('${materia.imagem_miniatura || ""}')`;
        tornarClicavel(card, materia.uuid);
    }

    function preencherRecomendados(materias) {
        const grade = document.getElementById("grid-voce-pode-gostar");
        grade.replaceChildren();

        if (materias.length === 0) {
            const aviso = document.createElement("p");
            aviso.textContent = "Novas matérias aparecerão aqui.";
            grade.append(aviso);
            return;
        }

        materias.forEach((materia) => {
            const card = document.createElement("article");
            card.className = "card-recomendado";
            card.tabIndex = 0;
            card.style.backgroundImage = `linear-gradient(180deg, rgba(0,0,0,.2), rgba(0,0,0,.88)), url('${materia.imagem_miniatura || ""}')`;

            const categoria = document.createElement("span");
            categoria.className = "categoria-tag";
            categoria.textContent = materia.categoria || "Direito";
            const titulo = document.createElement("h3");
            titulo.textContent = materia.titulo;
            card.append(categoria, titulo);
            tornarClicavel(card, materia.uuid);
            grade.append(card);
        });
    }

    function tornarClicavel(elemento, uuid) {
        if (!uuid) return;
        const abrir = () => { window.location.href = `/materia/${uuid}`; };
        elemento.addEventListener("click", abrir);
        elemento.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter" || evento.key === " ") {
                evento.preventDefault();
                abrir();
            }
        });
    }

    function mostrarEstadoVazio(mensagem = "Nenhuma matéria disponível.") {
        document.getElementById("hero-titulo-1").textContent = mensagem;
        document.getElementById("hero-titulo-2").textContent = "Tente novamente mais tarde.";
        document.getElementById("hero-titulo-3").textContent = "";
    }
})();
