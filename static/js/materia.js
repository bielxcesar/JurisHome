(() => {
    'use strict';
    function iniciar() {
        document.body.classList.toggle('modo-claro', document.documentElement.dataset.theme === 'light');
        const data = document.getElementById('data-atual');
        if (data) data.textContent = new Intl.DateTimeFormat('pt-BR').format(new Date());
        const copiar = document.getElementById('btn-copiar-link');
        const mensagem = document.getElementById('msg-copiado');
        copiar.addEventListener('click', async () => {
            copiar.disabled = true;
            try {
                const endereco = new URL(location.href); endereco.hash = '';
                await navigator.clipboard.writeText(endereco.href);
                mensagem.textContent = 'Link copiado!';
            } catch { mensagem.textContent = 'O navegador não permitiu copiar. Copie o endereço na barra do navegador.'; }
            finally { mensagem.hidden = false; copiar.disabled = false; }
        });
        let tamanho = 18;
        const diminuir = document.getElementById('materia-font-decrease');
        const aumentar = document.getElementById('materia-font-increase');
        function ajustar(valor) {
            tamanho = Math.max(16, Math.min(24, tamanho + valor));
            document.body.style.setProperty('--materia-reading-size', `${tamanho}px`);
            diminuir.disabled = tamanho === 16;
            aumentar.disabled = tamanho === 24;
        }
        diminuir.addEventListener('click', () => ajustar(-2));
        aumentar.addEventListener('click', () => ajustar(2));
        document.querySelectorAll('.btn-desconectar').forEach(link => link.addEventListener('click', async evento => {
            evento.preventDefault();
            try { const resposta = await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'}); if (!resposta.ok) throw new Error(); location.assign('/'); }
            catch { const alerta = document.getElementById('materia-alert'); alerta.textContent = 'Não foi possível encerrar a sessão. Tente novamente.'; alerta.hidden = false; alerta.scrollIntoView({block: 'nearest'}); }
        }));
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar, {once: true});
    else iniciar();
})();
