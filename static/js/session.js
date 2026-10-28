/* O navegador envia apenas cookies HttpOnly; a renovação é serializada entre abas. */
(() => {
    const originalFetch = window.fetch.bind(window);
    let pendente;
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
            || url.pathname.startsWith('/api/auth/')) return resposta;
        const renovacao = await renovar();
        return renovacao.ok ? originalFetch(copia) : resposta;
    };
    window.JurisHomeRenovarSessao = renovar;
})();
