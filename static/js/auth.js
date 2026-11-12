(function () {
    "use strict";

    const TOKEN_KEY = "jurishome_access_token";
    const DESAFIO_2FA_KEY = "jurishome_desafio_2fa";
    const CONFIGURACAO_2FA_KEY = "jurishome_configuracao_2fa";
    const LEMBRAR_CONECTADO_KEY = "jurishome_lembrar_conectado";
    const RECUPERACAO_EMAIL_KEY = "jurishome_recuperacao_email";
    const RECUPERACAO_DESAFIO_KEY = "jurishome_recuperacao_desafio";
    const REDEFINICAO_TOKEN_KEY = "jurishome_redefinicao_token";

    let bloqueioFim = 0, relogio;
    const botoesAuth = () => [...document.querySelectorAll('#form-login button[type=submit],#form-2fatores button[type=submit],#form-recuperacao-codigo button[type=submit]')];
    function mostrarEspera(segundos) {
        if (!Number.isFinite(segundos) || segundos <= 0) return;
        bloqueioFim = performance.now() + segundos * 1000;
        let painel = document.getElementById('auth-bloqueio');
        if (!painel) {
            painel = document.createElement('div');painel.id='auth-bloqueio';painel.className='auth-lock-panel';
            const texto=document.createElement('p');texto.textContent='Muitas tentativas seguidas. Aguarde para tentar novamente.';
            const tempo=document.createElement('strong');tempo.id='auth-bloqueio-tempo';tempo.setAttribute('aria-live','off');
            const dica=document.createElement('small');dica.textContent='A espera continua mesmo se você atualizar a página. Seu acesso será liberado automaticamente.';
            painel.append(texto,tempo,dica);document.getElementById('auth-message')?.after(painel);
        }
        painel.hidden=false;
        function atualizar(){
            const restante=Math.max(0,Math.ceil((bloqueioFim-performance.now())/1000));
            document.getElementById('auth-bloqueio-tempo').textContent=String(Math.floor(restante/60)).padStart(2,'0')+':'+String(restante%60).padStart(2,'0');
            for(const b of botoesAuth()){if(!b.dataset.textoLivre)b.dataset.textoLivre=b.textContent;b.disabled=restante>0;}
            if(!restante){clearInterval(relogio);painel.hidden=true;bloqueioFim=0;if(document.getElementById('form-2fatores')||document.getElementById('form-recuperacao-codigo')){sessionStorage.removeItem(DESAFIO_2FA_KEY);sessionStorage.removeItem(CONFIGURACAO_2FA_KEY);location.replace('/?bloqueio=encerrado');return;}mostrarMensagem('Você já pode tentar entrar novamente.',false);verificarEspera();}
        }
        clearInterval(relogio);atualizar();relogio=setInterval(atualizar,1000);
    }
    async function verificarEspera(){
        if(!botoesAuth().length)return;
        try{const r=await fetch('/api/auth/limite',{credentials:'same-origin',cache:'no-store'});if(!r.ok)return;const d=await r.json();if(d.bloqueado)mostrarEspera(Number(d.aguardeSegundos));}catch(_){}
    }

    function inicializarAutenticacao() {
        const parametros = new URLSearchParams(window.location.search);
        if (parametros.has("sessao")) {
            localStorage.removeItem(TOKEN_KEY);
            mostrarMensagem("Sua sessão terminou. Entre novamente.");
        } else if (parametros.get("senha") === "alterada") {
            mostrarMensagem("Senha alterada com sucesso. Entre com a nova senha.", false);
        }
        if(parametros.get('bloqueio')==='encerrado')mostrarMensagem('Tempo de espera encerrado. Entre novamente para continuar.',false);
        configurarAlternanciaSenha();
        configurarLogin();
        configurarCadastro();
        configurar2FA();
        configurarRecuperacaoSenha();
        verificarEspera();
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
            if(evento.currentTarget.dataset.enviando==='true')return;
            if(bloqueioFim > performance.now())return;
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

    function senhaValida(valor) {
        return [...valor].length >= 8 && [...valor].length <= 25 && /\p{Lu}/u.test(valor) && /[0-9]/.test(valor) && /[^\p{L}\p{N}\s]/u.test(valor) && !/[\r\n\t]/.test(valor) && new TextEncoder().encode(valor).length <= 72;
    }

    function configurarCadastro() {
        const formulario = document.getElementById("form-cadastro");
        if (!formulario) return;
        sessionStorage.setItem(LEMBRAR_CONECTADO_KEY, "false");

        formulario.addEventListener("submit", async (evento) => {
            evento.preventDefault();
            if(evento.currentTarget.dataset.enviando==='true')return;
            limparMensagem();
            const nome = document.getElementById("cadastro-nome").value.trim();
            const sobrenome = document.getElementById("cadastro-sobrenome").value.trim();
            const interesse = document.getElementById("cadastro-interesse").value;
            const email = document.getElementById("cadastro-email").value.trim().toLowerCase();
            const senha = document.getElementById("cadastro-senha").value;
            const confirmarSenha = document.getElementById("cadastro-confirma-senha").value;
            if (!/^[\p{L} ]{2,40}$/u.test(nome)) {
                mostrarMensagem("Informe seu nome com 2 a 40 letras, acentos e espaços.");
                document.getElementById("cadastro-nome").focus();
                return;
            }
            if (!emailValido(email)) {
                mostrarMensagem("Informe um e-mail válido, como nome@exemplo.com.");
                document.getElementById("cadastro-email").focus();
                return;
            }
            if (!/^[\p{L} ]{2,50}$/u.test(sobrenome) || !interesse) {
                mostrarMensagem('Preencha o sobrenome (2 a 50 letras) e escolha sua área de interesse.');
                return;
            }
            if (!senhaValida(senha)) {
                mostrarMensagem("Use de 8 a 25 caracteres, com maiúscula, número e caractere especial.");
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
                        sobrenome,
                        interesse,
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
            if(evento.currentTarget.dataset.enviando==='true')return;
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
            if(evento.currentTarget.dataset.enviando==='true')return;
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
            if(evento.currentTarget.dataset.enviando==='true')return;
                limparMensagem();
                const novaSenha = document.getElementById("recuperacao-nova-senha").value;
                const confirmaSenha = document.getElementById("recuperacao-confirma-senha").value;
                if (!senhaValida(novaSenha)) {
                    mostrarMensagem("Use de 8 a 25 caracteres, incluindo uma letra maiúscula, um número e um caractere especial.");
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
            if(evento.currentTarget.dataset.enviando==='true')return;
            limparMensagem();
            if(bloqueioFim > performance.now())return;
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
        if (!resposta.ok) {
            const erro=new Error(mensagemErroApi(dados.detail));
            const espera=Number(resposta.headers.get('Retry-After'));
            if(resposta.status===429 && espera>0)mostrarEspera(espera);
            throw erro;
        }
        return dados;
    }

    function concluirLogin(resposta) {
        if (!resposta.autenticado || !resposta.usuario?.tipo_usuario) {
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
        const form=botao.closest('form');if(form)form.dataset.enviando=String(carregando);
        botao.disabled = carregando || bloqueioFim > performance.now();
        botao.textContent = texto;
    }
})();
