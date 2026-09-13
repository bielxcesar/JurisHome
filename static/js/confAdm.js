document.addEventListener("DOMContentLoaded", () => {
    const btnVoltar = document.getElementById("btn-voltar");
    const formSenha = document.getElementById("form-troca-senha");
    const alertSucesso = document.getElementById("alert-sucesso");
    const btnTema = document.querySelector(".btn-theme");
    const iconeTema = btnTema ? btnTema.querySelector("i") : null;
    const atalhosSecao = Array.from(document.querySelectorAll("[data-config-section]"));
    const paineisSecao = Array.from(document.querySelectorAll("[data-config-panel]"));

    function exibirSecao(nome, atualizarEndereco = true) {
        const painelSelecionado = paineisSecao.find((painel) => painel.dataset.configPanel === nome);
        if (!painelSelecionado) return;

        paineisSecao.forEach((painel) => {
            painel.hidden = painel !== painelSelecionado;
        });

        atalhosSecao.forEach((atalho) => {
            const ativo = atalho.dataset.configSection === nome;
            atalho.classList.toggle("active", ativo);
            if (ativo) {
                atalho.setAttribute("aria-current", "page");
            } else {
                atalho.removeAttribute("aria-current");
            }
        });

        if (atualizarEndereco) {
            window.history.replaceState(null, "", `#${nome}`);
        }
    }

    function aplicarTemaSalvo() {
        const temaSalvo = localStorage.getItem("tema_juris");
        if (temaSalvo === "claro") {
            document.body.classList.add("modo-claro");
            if (iconeTema) {
                iconeTema.classList.replace("fa-moon", "fa-sun");
            }
        }
    }

    if (btnTema) {
        btnTema.addEventListener("click", () => {
            document.body.classList.toggle("modo-claro");
            const estaNoModoClaro = document.body.classList.contains("modo-claro");

            // Salva a escolha
            localStorage.setItem("tema_juris", estaNoModoClaro ? "claro" : "escuro");

            // Troca o ícone de lua para sol
            if (iconeTema) {
                if (estaNoModoClaro) {
                    iconeTema.classList.replace("fa-moon", "fa-sun");
                } else {
                    iconeTema.classList.replace("fa-sun", "fa-moon");
                }
            }
        });
    }

    aplicarTemaSalvo();

    atalhosSecao.forEach((atalho) => {
        atalho.addEventListener("click", (evento) => {
            evento.preventDefault();
            exibirSecao(atalho.dataset.configSection);
        });
    });

    const secaoInicial = window.location.hash.slice(1);
    exibirSecao(secaoInicial === "feedback" ? "feedback" : "senha", false);

    if (btnVoltar) {
        btnVoltar.addEventListener("click", () => {
            window.location.href = document.body.dataset.destinoVoltar || "/";
        });
    }

    if (formSenha) {
        formSenha.addEventListener("submit", (e) => {
            e.preventDefault();

            const novaSenha = document.getElementById("nova-senha").value;
            const confirmaSenha = document.getElementById("confirma-senha").value;

            if (novaSenha !== confirmaSenha) {
                alert("A nova senha e a confirmação não conferem!");
                return;
            }

            alertSucesso.classList.add("exibir");
            formSenha.reset();

            setTimeout(() => {
                alertSucesso.classList.remove("exibir");
            }, 4000);
        });
    }
});
