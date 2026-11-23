/* O navegador envia apenas cookies HttpOnly; a renovação é serializada entre abas. */
(() => {
    if (window.JurisHomeRenovarSessao) return;
    window.addEventListener('pageshow', evento => {
        if (evento.persisted) location.reload();
    });
    const originalFetch = window.fetch.bind(window);
    let pendente;
    let verificando = false;
    let encerrada = false;
    let atividadePendente = !document.hidden;
    let ultimaAtividadeEnviada = 0;
    const paginaProtegida = /^(\/(home_admin|home_usuario|perfil|configuracao|configuracoes-usuario|exibir-mais|categorias|pesquisa|feedback|admin-feedbacks|juridle|conhecimento|curiosidades|nova-materia|aceitar-documentos|glossario|consulta-lei)(\/|$)|\/(admin|materia)\/)/.test(location.pathname);
    function exigirAceite() {
        if (paginaProtegida && location.pathname !== '/aceitar-documentos') location.assign('/aceitar-documentos');
    }
    function encerrar(resposta) {
        if (!paginaProtegida || encerrada) return;
        encerrada = true;
        clearInterval(presencaTimer);
        const motivo = resposta.headers.get('X-Session-Reason') === 'novo_acesso' ? 'substituida' : 'expirada';
        location.replace('/?sessao=' + motivo);
    }
    async function confirmarPresenca() {
        if (verificando || encerrada) return;
        verificando = true;
        const atividade = atividadePendente;
        atividadePendente = false;
        if (atividade) ultimaAtividadeEnviada = Date.now();
        try {
            const resposta = await originalFetch('/api/auth/presenca', {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({atividade}),
            });
            if (resposta.headers.get('X-Legal-Acceptance') === 'required' || resposta.status === 428) exigirAceite();
            if (resposta.status === 401) {
                encerrar(resposta);
            }
        } catch {
            atividadePendente = atividadePendente || atividade;
            // Falhas de rede não removem os limites verificados pelo servidor.
        } finally {
            verificando = false;
        }
    }
    const presencaTimer = setInterval(confirmarPresenca, 15000);
    function registrarAtividade(evento) {
        if (document.hidden || encerrada || (evento && !evento.isTrusted)) return;
        atividadePendente = true;
        // Movimento contínuo não deve gerar uma requisição a cada evento.
        if (Date.now() - ultimaAtividadeEnviada >= 15000) confirmarPresenca();
    }
    ['mousemove', 'pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(tipo => {
        document.addEventListener(tipo, registrarAtividade, {passive: true});
    });
    window.addEventListener('focus', registrarAtividade);
    window.addEventListener('pageshow', registrarAtividade);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) registrarAtividade();
    });
    confirmarPresenca();
    async function renovar() {
        if (!pendente) {
            const executar = () => originalFetch('/api/auth/refresh', {method: 'POST', credentials: 'same-origin'});
            pendente = (navigator.locks ? navigator.locks.request('jurishome-refresh', executar) : executar())
                .finally(() => { pendente = null; });
        }
        return pendente;
    }
    window.fetch = async (input, options) => {
        const request = new Request(input, options);
        const url = new URL(request.url);
        const copia = request.clone();
        const resposta = await originalFetch(request);
        if (url.origin === location.origin && resposta.status === 428) exigirAceite();
        if (resposta.status !== 401 || url.origin !== location.origin
            || url.pathname.startsWith('/api/auth/') || url.pathname === '/api/solicitar-reset-2fa') return resposta;
        const renovacao = await renovar();
        if (!renovacao.ok) {
            encerrar(resposta.headers.get('X-Session-Reason') ? resposta : renovacao);
            return resposta;
        }
        const repetida = await originalFetch(copia);
        if (repetida.status === 428) exigirAceite();
        return repetida;
    };
    window.JurisHomeRenovarSessao = renovar;
})();
