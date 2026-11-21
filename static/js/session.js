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
    async function confirmarPresenca() {
        if (verificando || encerrada) return;
        verificando = true;
        try {
            const resposta = await originalFetch('/api/auth/presenca', {
                method: 'POST', credentials: 'same-origin',
            });
            if (resposta.status === 401) {
                encerrada = true;
                clearInterval(presencaTimer);
                if (document.querySelector('.home-shell, .admin-tabelas, #form-perfil')) {
                    location.replace('/?sessao=expirada');
                }
            }
        } catch {
            // O servidor encerra a sessão após o prazo sem confirmação.
        } finally {
            verificando = false;
        }
    }
    const presencaTimer = setInterval(confirmarPresenca, 30000);
    window.addEventListener('pageshow', confirmarPresenca);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) confirmarPresenca();
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
        if (resposta.status !== 401 || url.origin !== location.origin
            || url.pathname.startsWith('/api/auth/') || url.pathname === '/api/solicitar-reset-2fa') return resposta;
        const renovacao = await renovar();
        return renovacao.ok ? originalFetch(copia) : resposta;
    };
    window.JurisHomeRenovarSessao = renovar;
})();
