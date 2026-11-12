(function () {
    "use strict";

    const service = window.FeedbackService;
    if (!service) {
        console.error("Serviço de feedback indisponível.");
        return;
    }

    document.addEventListener("DOMContentLoaded", iniciar);

    function iniciar() {
        aplicarTemaSalvo();
        preencherDataAtual();
        configurarMenuPerfil();
        configurarFormulario();
        document.getElementById("feedback-history-refresh")?.addEventListener("click", carregarHistorico);
        carregarHistorico();
    }

    function aplicarTemaSalvo() {
        document.body.classList.toggle("modo-claro", window.localStorage.getItem("tema_juris") === "claro");
    }

    function preencherDataAtual() {
        const alvo = document.getElementById("data-atual");
        if (alvo) alvo.textContent = new Intl.DateTimeFormat("pt-BR").format(new Date());
    }

    function configurarMenuPerfil() {
        const botao = document.getElementById("btn-perfil");
        const menu = document.getElementById("dropdown-perfil");
        if (!botao || !menu) return;
        document.querySelectorAll(".btn-desconectar").forEach(link => link.addEventListener("click", async evento => {
            evento.preventDefault();
            try {
                const resposta = await window.fetch('/api/auth/logout', {method: 'POST'});
                if (!resposta.ok) throw new Error();
                window.location.assign('/');
            } catch { window.alert('Não foi possível encerrar a sessão. Tente novamente.'); }
        }));

        const fecharMenu = () => {
            menu.classList.remove("ativo");
            botao.setAttribute("aria-expanded", "false");
        };

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
    }

    function configurarFormulario() {
        const form = document.getElementById("feedback-form");
        const assunto = document.getElementById("feedback-assunto");
        const mensagem = document.getElementById("feedback-mensagem");
        const tipo = document.getElementById("feedback-tipo");
        const radios = Array.from(document.querySelectorAll('input[name="avaliacao"]'));

        assunto.addEventListener("input", () => {
            atualizarContador(assunto, "contador-assunto", 120);
            if (assunto.value.trim().length >= 5) limparErro(assunto, "erro-assunto");
        });

        mensagem.addEventListener("input", () => {
            atualizarContador(mensagem, "contador-mensagem", 2000);
            if (mensagem.value.trim().length >= 10) limparErro(mensagem, "erro-mensagem");
        });

        tipo.addEventListener("change", () => {
            if (tipo.value) limparErro(tipo, "erro-tipo");
        });

        radios.forEach((radio) => {
            radio.setAttribute('aria-label', `${radio.value} estrela(s)`);
            radio.addEventListener("change", atualizarEstrelas);
        });
        form.addEventListener("submit", enviarFeedback);
    }

    function atualizarContador(campo, contadorId, limite) {
        document.getElementById(contadorId).textContent = `${campo.value.length}/${limite}`;
    }

    function atualizarEstrelas() {
        const selecionado = Number(document.querySelector('input[name="avaliacao"]:checked')?.value || 0);
        document.querySelectorAll(".feedback-stars label").forEach((rotulo, indice) => {
            rotulo.classList.toggle("is-selected", indice < selecionado);
            rotulo.classList.toggle("selecionada", indice < selecionado);
        });
    }

    function validarFormulario() {
        const tipo = document.getElementById("feedback-tipo");
        const assunto = document.getElementById("feedback-assunto");
        const mensagem = document.getElementById("feedback-mensagem");
        const invalidos = [];

        validarCampo(tipo, "erro-tipo", Boolean(tipo.value), "Escolha o motivo do contato.", invalidos);

        const tamanhoAssunto = assunto.value.trim().length;
        validarCampo(
            assunto,
            "erro-assunto",
            tamanhoAssunto >= 5 && tamanhoAssunto <= 120,
            "O assunto deve ter entre 5 e 120 caracteres.",
            invalidos
        );

        const tamanhoMensagem = mensagem.value.trim().length;
        validarCampo(
            mensagem,
            "erro-mensagem",
            tamanhoMensagem >= 10 && tamanhoMensagem <= 2000,
            "A mensagem deve ter entre 10 e 2.000 caracteres.",
            invalidos
        );

        if (invalidos.length) invalidos[0].focus();
        return invalidos.length === 0;
    }

    function validarCampo(campo, erroId, valido, mensagem, invalidos) {
        if (valido) {
            limparErro(campo, erroId);
            return;
        }
        definirErro(campo, erroId, mensagem);
        invalidos.push(campo);
    }

    function definirErro(campo, erroId, mensagem) {
        campo.setAttribute("aria-invalid", "true");
        document.getElementById(erroId).textContent = mensagem;
        campo.setAttribute("aria-describedby", erroId);
    }

    function limparErro(campo, erroId) {
        campo.removeAttribute("aria-invalid");
        document.getElementById(erroId).textContent = "";
    }

    async function enviarFeedback(evento) {
        evento.preventDefault();
        const sucesso = document.getElementById("feedback-sucesso");
        const erroGeral = document.getElementById("feedback-erro-geral");
        sucesso.hidden = true;
        sucesso.classList.add("hidden");
        erroGeral.hidden = true;
        erroGeral.classList.add("hidden");
        if (!validarFormulario()) return;

        const form = evento.currentTarget;
        const botao = document.getElementById("feedback-enviar");
        if (botao.disabled) return;
        const textoBotao = botao.querySelector(".feedback-button-text");
        botao.disabled = true;
        botao.classList.add("is-loading");
        textoBotao.textContent = "Enviando...";

        try {
            const criado = await service.criar({
                tipo: document.getElementById("feedback-tipo").value,
                assunto: document.getElementById("feedback-assunto").value,
                mensagem: document.getElementById("feedback-mensagem").value,
                avaliacao: Number(document.querySelector('input[name="avaliacao"]:checked')?.value || 0) || null
            });

            form.reset();
            atualizarContador(document.getElementById("feedback-assunto"), "contador-assunto", 120);
            atualizarContador(document.getElementById("feedback-mensagem"), "contador-mensagem", 2000);
            atualizarEstrelas();
            sucesso.textContent = `Feedback enviado! Protocolo: ${criado.protocolo}.`;
            sucesso.hidden = false;
            sucesso.classList.remove("hidden");
            sucesso.scrollIntoView({ behavior: "smooth", block: "nearest" });
            await carregarHistorico();
        } catch (erro) {
            erroGeral.textContent = erro.message || "Não foi possível enviar agora. Tente de novo.";
            erroGeral.hidden = false;
            erroGeral.classList.remove("hidden");
        } finally {
            botao.disabled = false;
            botao.classList.remove("is-loading");
            textoBotao.textContent = "Enviar feedback";
        }
    }

    let carregandoHistorico = false;
    async function carregarHistorico() {
        const lista = document.getElementById('feedback-history-list');
        if (!lista || carregandoHistorico) return;
        carregandoHistorico = true;
        const estado = document.getElementById('feedback-history-state');
        const botao = document.getElementById('feedback-history-refresh');
        botao.disabled = true;
        lista.setAttribute('aria-busy', 'true');
        estado.textContent = 'Carregando seus atendimentos…';
        try {
            const registros = await service.listarMeus();
            lista.replaceChildren();
            registros.forEach(feedback => {
                const detalhes = document.createElement('details');
                detalhes.className = 'feedback-history-item';
                const resumo = document.createElement('summary');
                resumo.textContent = `${feedback.protocolo} · ${feedback.assunto} — ${feedback.status}`;
                detalhes.append(resumo);
                const original = document.createElement('p');
                original.textContent = feedback.mensagem;
                detalhes.append(original);
                (feedback.respostas || []).forEach(resposta => {
                    const artigo = document.createElement('article');
                    artigo.className = 'feedback-history-response';
                    const autor = document.createElement('strong');
                    autor.textContent = resposta.autor || 'Equipe JurisHome';
                    const texto = document.createElement('p');
                    texto.textContent = resposta.mensagem;
                    artigo.append(autor, texto);
                    detalhes.append(artigo);
                });
                if (!feedback.respostas?.length) {
                    const espera = document.createElement('small');
                    espera.textContent = 'Aguardando resposta da equipe.';
                    detalhes.append(espera);
                }
                if (!feedback.arquivado) {
                    const form = document.createElement('form');
                    form.className = 'feedback-followup';
                    const label = document.createElement('label');
                    const id = 'continuar-' + feedback.id;
                    label.htmlFor = id;
                    label.textContent = 'Complementar este atendimento';
                    const campo = document.createElement('textarea');
                    campo.id = id; campo.required = true; campo.maxLength = 2000; campo.rows = 3;
                    campo.placeholder = 'Envie mais informações ou responda à equipe.';
                    const enviar = document.createElement('button');
                    enviar.type = 'submit'; enviar.className = 'feedback-secondary-button';
                    enviar.textContent = 'Enviar mensagem';
                    const retorno = document.createElement('p'); retorno.setAttribute('role', 'status');
                    form.append(label, campo, enviar, retorno);
                    form.addEventListener('submit', async evento => {
                        evento.preventDefault(); if (enviar.disabled) return;
                        if (!campo.value.trim()) { retorno.textContent = 'Digite uma mensagem.'; return; }
                        enviar.disabled = true;
                        try { await service.complementar(feedback.id, campo.value.trim()); campo.value = ''; retorno.textContent = 'Mensagem enviada. A equipe receberá sua atualização.'; await carregarHistorico(); }
                        catch (erro) { retorno.textContent = erro.message; }
                        finally { enviar.disabled = false; }
                    });
                    detalhes.append(form);
                }
                lista.append(detalhes);
            });
            estado.textContent = registros.length ? `${registros.length} atendimento(s). Abra um protocolo para ver as respostas.` : 'Você ainda não enviou nenhum feedback.';
        } catch (erro) {
            estado.textContent = `${erro.message} Use Atualizar para tentar novamente.`;
        } finally {
            lista.setAttribute('aria-busy', 'false');
            botao.disabled = false;
            carregandoHistorico = false;
        }
    }
})();
