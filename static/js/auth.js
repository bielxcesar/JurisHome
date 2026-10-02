(function () {
    "use strict";

    const TOKEN_KEY = "jurishome_access_token";
    const DESAFIO_2FA_KEY = "jurishome_desafio_2fa";
    const CONFIGURACAO_2FA_KEY = "jurishome_configuracao_2fa";
    const LEMBRAR_CONECTADO_KEY = "jurishome_lembrar_conectado";
    const RECUPERACAO_EMAIL_KEY = "jurishome_recuperacao_email";
    const RECUPERACAO_DESAFIO_KEY = "jurishome_recuperacao_desafio";
    const REDEFINICAO_TOKEN_KEY = "jurishome_redefinicao_token";

    function inicializarAutenticacao() {
        const parametros = new URLSearchParams(window.location.search);
        if (parametros.has("sessao")) {
            localStorage.removeItem(TOKEN_KEY);
            mostrarMensagem("Sua sessão terminou. Entre novamente.");
        } else if (parametros.get("senha") === "alterada") {
            mostrarMensagem("Senha alterada com sucesso. Entre com a nova senha.", false);
        }
        configurarAlternanciaSenha();
        configurarLogin();
        configurarCadastro();
        configurar2FA();
        configurarRecuperacaoSenha();
        configurarConsultaUniversidade();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicializarAutenticacao, { once: true });
    } else {
        inicializarAutenticacao();
    }

    function configurarLogin() {
        const formulario = document.getElementById("form-login");
        if (!formulario) return;

        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            limparMensagem();
            const email = document.getElementById("email").value.trim().toLowerCase();
            const senha = document.getElementById("senha").value;
            if (!emailValido(email)) {
                mostrarMensagem("Informe um e-mail válido, como nome@exemplo.com.");
                document.getElementById("email").focus();
                return;
            }
            if (!senha) {
                mostrarMensagem("Informe sua senha.");
                document.getElementById("senha").focus();
                return;
            }
            const botao = formulario.querySelector("button[type=submit]");
            sessionStorage.setItem(
                LEMBRAR_CONECTADO_KEY,
                String(Boolean(document.getElementById("manter-conectado")?.checked)),
            );
            alternarCarregamento(botao, true, "Entrando...");

            try {
                const resposta = await requisitar("/api/auth/login", {
                    method: "POST",
                    body: JSON.stringify({
                        email,
                        senha,
                    }),
                });
                if (resposta.requer_configuracao_2fa) {
                    iniciarConfiguracao2FA(resposta);
                    return;
                }
                if (resposta.requer_2fa) {
                    sessionStorage.removeItem(CONFIGURACAO_2FA_KEY);
                    sessionStorage.setItem(DESAFIO_2FA_KEY, resposta.desafio_token);
                    window.location.href = "/2fatores";
                    return;
                }
                throw new Error("O servidor não retornou uma etapa de autenticação válida.");
            } catch (erro) {
                mostrarMensagem(erro.message);
            } finally {
                alternarCarregamento(botao, false, "Entrar");
            }
        });
    }

    function configurarCadastro() {
        const formulario = document.getElementById("form-cadastro");
        if (!formulario) return;
        sessionStorage.setItem(LEMBRAR_CONECTADO_KEY, "false");

        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            limparMensagem();
            const nome = document.getElementById("cadastro-nome").value.trim();
            const email = document.getElementById("cadastro-email").value.trim().toLowerCase();
            const senha = document.getElementById("cadastro-senha").value;
            const confirmarSenha = document.getElementById("cadastro-confirma-senha").value;
            if (nome.length < 3) {
                mostrarMensagem("Informe seu nome completo.");
                document.getElementById("cadastro-nome").focus();
                return;
            }
            if (!emailValido(email)) {
                mostrarMensagem("Informe um e-mail válido, como nome@exemplo.com.");
                document.getElementById("cadastro-email").focus();
                return;
            }
            if (senha.length < 8 || !/[A-Za-z]/.test(senha) || !/\d/.test(senha)) {
                mostrarMensagem("A senha deve ter pelo menos 8 caracteres, incluindo letras e números.");
                document.getElementById("cadastro-senha").focus();
                return;
            }
            if (new TextEncoder().encode(senha).length > 72) {
                mostrarMensagem("A senha não pode ultrapassar 72 bytes.");
                document.getElementById("cadastro-senha").focus();
                return;
            }
            if (senha !== confirmarSenha) {
                mostrarMensagem("As senhas não conferem.");
                document.getElementById("cadastro-confirma-senha").focus();
                return;
            }
            if (!document.getElementById("cadastro-lgpd").checked) {
                mostrarMensagem("Aceite o Termo de Aceite e declare ciência da Política de Privacidade para continuar.");
                document.getElementById("cadastro-lgpd").focus();
                return;
            }
            const botao = formulario.querySelector("button[type=submit]");
            alternarCarregamento(botao, true, "Criando conta...");
            try {
                const resposta = await requisitar("/api/auth/cadastro", {
                    method: "POST",
                    body: JSON.stringify({
                        nome,
                        email,
                        senha,
                        confirmar_senha: confirmarSenha,
                        consentimento_lgpd: document.getElementById("cadastro-lgpd").checked,
                    }),
                });
                iniciarConfiguracao2FA(resposta);
            } catch (erro) {
                mostrarMensagem(erro.message);
            } finally {
                alternarCarregamento(botao, false, "Criar conta");
            }
        });
    }

    function configurarRecuperacaoSenha() {
        const formularioEmail = document.getElementById("form-recuperacao-email");
        if (formularioEmail) {
            formularioEmail.addEventListener("submit", async (evento) => {
                evento.preventDefault();
                limparMensagem();
                const email = document.getElementById("recuperacao-email").value.trim().toLowerCase();
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                    mostrarMensagem("Informe um e-mail válido.");
                    return;
                }
                const botao = formularioEmail.querySelector("button[type=submit]");
                sessionStorage.removeItem(RECUPERACAO_DESAFIO_KEY);
                sessionStorage.removeItem(REDEFINICAO_TOKEN_KEY);
                alternarCarregamento(botao, true, "Verificando...");
                try {
                    const resposta = await requisitar("/api/auth/recuperacao/iniciar", {
                        method: "POST",
                        body: JSON.stringify({ email }),
                    });
                    sessionStorage.setItem(RECUPERACAO_EMAIL_KEY, email);
                    sessionStorage.setItem(RECUPERACAO_DESAFIO_KEY, resposta.desafio_token);
                    window.location.href = "/recuperar-senha/confirmar";
                } catch (erro) {
                    mostrarMensagem(erro.message);
                } finally {
                    alternarCarregamento(botao, false, "Próximo");
                }
            });
        }

        const formularioCodigo = document.getElementById("form-recuperacao-codigo");
        if (formularioCodigo) {
            const email = sessionStorage.getItem(RECUPERACAO_EMAIL_KEY);
            const desafio = sessionStorage.getItem(RECUPERACAO_DESAFIO_KEY);
            if (!email || !desafio) {
                window.location.replace("/recuperar-senha");
                return;
            }
            document.getElementById("recovery-address").textContent = email;
            formularioCodigo.addEventListener("submit", async (evento) => {
                evento.preventDefault();
                limparMensagem();
                const codigo = document.getElementById("recuperacao-codigo").value.trim();
                if (!/^\d{6}$/.test(codigo)) {
                    mostrarMensagem("Informe o código de seis dígitos do autenticador.");
                    return;
                }
                const botao = formularioCodigo.querySelector("button[type=submit]");
                alternarCarregamento(botao, true, "Verificando...");
                try {
                    const resposta = await requisitar("/api/auth/recuperacao/validar", {
                        method: "POST",
                        body: JSON.stringify({ email, desafio_token: desafio, codigo }),
                    });
                    sessionStorage.setItem(REDEFINICAO_TOKEN_KEY, resposta.token_redefinicao);
                    sessionStorage.removeItem(RECUPERACAO_DESAFIO_KEY);
                    window.location.href = "/recuperar-senha/nova";
                } catch (erro) {
                    mostrarMensagem(erro.message);
                } finally {
                    alternarCarregamento(botao, false, "Próximo");
                }
            });
        }

        const formularioNovaSenha = document.getElementById("form-recuperacao-nova");
        if (formularioNovaSenha) {
            const token = sessionStorage.getItem(REDEFINICAO_TOKEN_KEY);
            if (!token) {
                window.location.replace("/recuperar-senha");
                return;
            }
            formularioNovaSenha.addEventListener("submit", async (evento) => {
                evento.preventDefault();
                limparMensagem();
                const novaSenha = document.getElementById("recuperacao-nova-senha").value;
                const confirmaSenha = document.getElementById("recuperacao-confirma-senha").value;
                if (!/^(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,25}$/.test(novaSenha)) {
                    mostrarMensagem("Use de 8 a 25 caracteres, incluindo uma letra maiúscula e um caractere especial.");
                    return;
                }
                if (novaSenha !== confirmaSenha) {
                    mostrarMensagem("As senhas não conferem.");
                    return;
                }
                const botao = formularioNovaSenha.querySelector("button[type=submit]");
                alternarCarregamento(botao, true, "Alterando...");
                try {
                    await requisitar("/api/auth/recuperacao/alterar", {
                        method: "POST",
                        body: JSON.stringify({
                            token_redefinicao: token,
                            nova_senha: novaSenha,
                            confirmar_senha: confirmaSenha,
                        }),
                    });
                    sessionStorage.removeItem(RECUPERACAO_EMAIL_KEY);
                    sessionStorage.removeItem(RECUPERACAO_DESAFIO_KEY);
                    sessionStorage.removeItem(REDEFINICAO_TOKEN_KEY);
                    window.location.href = "/?senha=alterada";
                } catch (erro) {
                    mostrarMensagem(erro.message);
                } finally {
                    alternarCarregamento(botao, false, "Alterar senha");
                }
            });
        }
    }

    function configurarConsultaUniversidade() {
        const botao = document.getElementById("consultar-emec");
        const codigo = document.getElementById("codigo-emec");
        if (!botao || !codigo) return;

        botao.addEventListener("click", async () => {
            const mensagem = document.getElementById("emec-message");
            const resultado = document.getElementById("emec-result");
            mensagem.hidden = true;
            mensagem.classList.remove("is-success");
            resultado.hidden = true;
            resultado.replaceChildren();
            const valor = codigo.value.trim();
            if (!/^\d{1,10}$/.test(valor)) {
                mensagem.textContent = "Informe um código e-MEC numérico válido.";
                mensagem.hidden = false;
                return;
            }

            alternarCarregamento(botao, true, "Consultando...");
            try {
                const instituicao = await requisitar(`/api/universidades/emec/${encodeURIComponent(valor)}`);
                const nome = document.createElement("strong");
                nome.textContent = instituicao.nome;
                resultado.append(nome);
                const detalhes = [instituicao.sigla, instituicao.situacao].filter(Boolean).join(" · ");
                if (detalhes) {
                    const paragrafo = document.createElement("p");
                    paragrafo.textContent = detalhes;
                    resultado.append(paragrafo);
                }
                const campus = (instituicao.campus || []).slice(0, 5).map((item) =>
                    [item.nome, item.cidade, item.uf].filter(Boolean).join(" · "),
                ).filter(Boolean);
                if (campus.length) {
                    const paragrafo = document.createElement("p");
                    paragrafo.textContent = `Campus: ${campus.join("; ")}`;
                    resultado.append(paragrafo);
                }
                resultado.hidden = false;
                mensagem.textContent = "Instituição encontrada.";
                mensagem.classList.add("is-success");
                mensagem.hidden = false;
            } catch (erro) {
                mensagem.textContent = erro.message;
                mensagem.hidden = false;
            } finally {
                alternarCarregamento(botao, false, "Consultar");
            }
        });
    }

    function configurar2FA() {
        const formulario = document.getElementById("form-2fatores");
        if (!formulario) return;
        const configuracao = lerConfiguracao2FA();
        const desafio = sessionStorage.getItem(DESAFIO_2FA_KEY);
        if (!configuracao && !desafio) {
            window.location.replace("/");
            return;
        }

        if (configuracao) {
            document.getElementById("2fa-titulo").textContent = "Proteja sua conta";
            document.getElementById("2fa-instrucao").textContent = "Escaneie o QR Code no aplicativo autenticador e informe o primeiro código de seis números.";
            document.getElementById("2fa-setup").hidden = false;
            document.getElementById("2fa-qrcode").src = configuracao.qr_code;
            document.getElementById("2fa-segredo").textContent = configuracao.segredo;
            document.getElementById("2fa-botao").textContent = "Ativar e entrar";
        }

        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            limparMensagem();
            const botao = formulario.querySelector("button[type=submit]");
            alternarCarregamento(botao, true, "Verificando...");
            try {
                const url = configuracao ? "/api/auth/2fa/ativar-cadastro" : "/api/auth/2fa/validar";
                const token = configuracao?.configuracao_token || desafio;
                const resposta = await requisitar(url, {
                    method: "POST",
                    body: JSON.stringify({
                        desafio_token: token,
                        codigo: document.getElementById("code").value.trim(),
                        lembrar_conectado: sessionStorage.getItem(LEMBRAR_CONECTADO_KEY) === "true",
                    }),
                });
                sessionStorage.removeItem(DESAFIO_2FA_KEY);
                sessionStorage.removeItem(CONFIGURACAO_2FA_KEY);
                concluirLogin(resposta);
            } catch (erro) {
                mostrarMensagem(erro.message);
            } finally {
                alternarCarregamento(botao, false, "Próximo");
            }
        });
    }

    function iniciarConfiguracao2FA(resposta) {
        if (!resposta.requer_configuracao_2fa || !resposta.configuracao_token || !resposta.qr_code || !resposta.segredo) {
            throw new Error("O servidor não retornou a configuração do autenticador.");
        }
        sessionStorage.removeItem(DESAFIO_2FA_KEY);
        sessionStorage.setItem(
            CONFIGURACAO_2FA_KEY,
            JSON.stringify({
                configuracao_token: resposta.configuracao_token,
                segredo: resposta.segredo,
                qr_code: resposta.qr_code,
            }),
        );
        window.location.href = "/2fatores";
    }

    function lerConfiguracao2FA() {
        const valor = sessionStorage.getItem(CONFIGURACAO_2FA_KEY);
        if (!valor) return null;
        try {
            const configuracao = JSON.parse(valor);
            if (!configuracao.configuracao_token || !configuracao.segredo || !configuracao.qr_code) {
                throw new Error("Configuração incompleta");
            }
            return configuracao;
        } catch (_) {
            sessionStorage.removeItem(CONFIGURACAO_2FA_KEY);
            return null;
        }
    }

    function configurarAlternanciaSenha() {
        document.querySelectorAll("[data-password-toggle]").forEach((botao) => {
            botao.addEventListener("click", () => {
                const campo = document.getElementById(botao.dataset.passwordToggle);
                if (!campo) return;
                const mostrar = campo.type === "password";
                campo.type = mostrar ? "text" : "password";
                botao.textContent = mostrar ? "Ocultar" : "Mostrar";
                botao.setAttribute("aria-label", `${mostrar ? "Ocultar" : "Mostrar"} ${campo.labels?.[0]?.textContent?.toLowerCase() || "senha"}`);
                botao.setAttribute("aria-pressed", String(mostrar));
            });
        });
    }

    function emailValido(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    function mensagemErroApi(detalhe) {
        if (typeof detalhe === "string") return detalhe;
        if (Array.isArray(detalhe)) {
            const erro = detalhe.find((item) => typeof item?.msg === "string");
            if (erro) {
                const campo = erro.loc?.at(-1);
                if (campo === "email") return "Informe um e-mail válido, como nome@exemplo.com.";
                if (campo === "confirmar_senha") return "As senhas não conferem.";
                return erro.msg.replace(/^Value error,\s*/i, "");
            }
        }
        return "Não foi possível concluir a operação. Confira os dados e tente novamente.";
    }

    async function requisitar(url, opcoes = {}) {
        const resposta = await fetch(url, {
            ...opcoes,
            headers: { "Content-Type": "application/json", ...(opcoes.headers || {}) },
        });
        const dados = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(mensagemErroApi(dados.detail));
        return dados;
    }

    function concluirLogin(resposta) {
        if (!resposta.access_token || !resposta.usuario?.tipo_usuario) {
            throw new Error("A autenticação não foi concluída. Tente novamente.");
        }
        localStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(LEMBRAR_CONECTADO_KEY);
        const destino = resposta.usuario?.tipo_usuario === "administrador" ? "/home_admin" : "/home_usuario";
        window.location.href = destino;
    }

    function mostrarMensagem(texto, erro = true) {
        const mensagem = document.getElementById("auth-message");
        if (!mensagem) return;
        mensagem.textContent = texto;
        mensagem.hidden = false;
        mensagem.classList.toggle("is-success", !erro);
    }

    function limparMensagem() {
        const mensagem = document.getElementById("auth-message");
        if (mensagem) mensagem.hidden = true;
    }

    function alternarCarregamento(botao, carregando, texto) {
        if (!botao) return;
        botao.disabled = carregando;
        botao.textContent = texto;
    }
})();
