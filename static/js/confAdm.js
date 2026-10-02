document.addEventListener("DOMContentLoaded", () => {
    const btnVoltar = document.getElementById("btn-voltar");
    const formSenha = document.getElementById("form-troca-senha");
    const alertSucesso = document.getElementById("alert-sucesso");
    const formAnonimizacao = document.getElementById("form-anonimizacao");
    const privacySuccess = document.getElementById("privacy-success");
    const privacyError = document.getElementById("privacy-error");
    const btnAnonimizar = document.getElementById("btn-anonimizar");
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
    const secaoDisponivel = paineisSecao.some((painel) => painel.dataset.configPanel === secaoInicial);
    exibirSecao(secaoDisponivel ? secaoInicial : "senha", false);

    if (btnVoltar) {
        btnVoltar.addEventListener("click", () => {
            window.location.href = document.body.dataset.destinoVoltar || "/home_usuario";
        });
    }

    document.querySelectorAll(".btn-desconectar-side").forEach((link) => {
        link.addEventListener("click", (evento) => {
            evento.preventDefault();
            localStorage.removeItem("jurishome_access_token");
            sessionStorage.removeItem("jurishome_desafio_2fa");
            fetch("/api/auth/logout", { method: "POST" })
                .finally(() => { window.location.href = "/"; });
        });
    });

    if (formSenha) {
        formSenha.addEventListener("submit", async (e) => {
            e.preventDefault();

            const novaSenha = document.getElementById("nova-senha").value;
            const confirmaSenha = document.getElementById("confirma-senha").value;

            if (novaSenha !== confirmaSenha) {
                alert("A nova senha e a confirmação não conferem!");
                return;
            }

            try {
                const resposta = await fetch("/api/usuarios/me/senha", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        senha_atual: document.getElementById("senha-atual").value,
                        nova_senha: novaSenha
                    })
                });
                const dados = await resposta.json();
                if (!resposta.ok) throw new Error(dados.detail || "Não foi possível alterar a senha.");

                alertSucesso.style.display = "block";
                alertSucesso.classList.add("exibir");
                formSenha.reset();

                setTimeout(() => {
                    alertSucesso.classList.remove("exibir");
                    alertSucesso.style.display = "none";
                }, 4000);
            } catch (erro) {
                alert(erro.message || "Não foi possível alterar a senha.");
            }
        });
    }

    if (formAnonimizacao) {
        formAnonimizacao.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            privacySuccess.hidden = true;
            privacyError.hidden = true;

            const senha = document.getElementById("senha-anonimizacao").value;
            const confirmado = document.getElementById("confirmar-anonimizacao").checked;
            if (!senha || !confirmado) {
                privacyError.textContent = "Informe sua senha e confirme que entendeu a anonimização.";
                privacyError.hidden = false;
                return;
            }

            const desejaContinuar = window.confirm(
                "Esta ação removerá seus dados pessoais, encerrará a conta e não poderá ser desfeita. Deseja continuar?"
            );
            if (!desejaContinuar) return;

            btnAnonimizar.disabled = true;
            btnAnonimizar.classList.add("is-loading");

            try {
                const resposta = await fetch("/api/usuarios/me/dados-pessoais", {
                    method: "DELETE",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ senha, confirmacao: "ANONIMIZAR" })
                });
                const dados = await resposta.json();
                if (!resposta.ok) throw new Error(dados.detail || "Não foi possível anonimizar os dados.");

                formAnonimizacao.reset();
                privacySuccess.textContent = dados.mensagem;
                privacySuccess.hidden = false;
                localStorage.removeItem("jurishome_access_token");
                sessionStorage.removeItem("jurishome_desafio_2fa");
                window.setTimeout(() => { window.location.href = "/?dados=anonimizados"; }, 1200);
            } catch (erro) {
                document.getElementById("senha-anonimizacao").value = "";
                privacyError.textContent = erro.message || "Não foi possível anonimizar os dados.";
                privacyError.hidden = false;
            } finally {
                btnAnonimizar.disabled = false;
                btnAnonimizar.classList.remove("is-loading");
            }
        });
    }

});
