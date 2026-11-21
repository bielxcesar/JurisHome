(() => {
    'use strict';
    const form = document.getElementById('legal-acceptance-form');
    if (!form) return;
    const submit = document.getElementById('acceptance-submit');
    const cards = [...form.querySelectorAll('[data-documento]')];
    function atualizar() {
        submit.disabled = !cards.every(card => card.querySelector('input[type=checkbox]').checked && card.querySelector('input[type=hidden]').value);
    }
    for (const card of cards) {
        const reader = card.querySelector('.acceptance-reader');
        const state = card.querySelector('.acceptance-state');
        const check = card.querySelector('input[type=checkbox]');
        const receipt = card.querySelector('input[type=hidden]');
        const retry = card.querySelector('.acceptance-retry');
        let loading = false;
        async function conferir() {
            if (loading || receipt.value || reader.scrollTop + reader.clientHeight < reader.scrollHeight - 4) return;
            loading = true;
            retry.hidden = true;
            state.textContent = 'Registrando a apresentação do documento...';
            try {
                const response = await fetch('/api/legal/documentos/' + card.dataset.documento + '/visualizacao', {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({versao: form.dataset.versao}),
                });
                const data = await response.json();
                if (!response.ok || !data.comprovante) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível registrar a visualização. Tente novamente.');
                receipt.value = data.comprovante;
                card.dataset.visualizado = 'true';
                check.disabled = false;
                state.textContent = 'Você chegou ao final. Se leu o documento, confirme abaixo.';
                atualizar();
            } catch (error) {
                state.textContent = error.message;
                retry.hidden = false;
            } finally { loading = false; }
        }
        reader.addEventListener('scroll', conferir, {passive: true});
        retry.addEventListener('click', conferir);
        check.addEventListener('change', atualizar);
        requestAnimationFrame(conferir);
        if (window.ResizeObserver) new ResizeObserver(conferir).observe(reader);
    }
    form.addEventListener('submit', event => {
        atualizar();
        if (submit.disabled) event.preventDefault();
        else { submit.disabled = true; submit.textContent = 'Confirmando...'; }
    });
})();
