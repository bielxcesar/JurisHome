(() => {
    'use strict';
    document.querySelectorAll('input[type="password"][id]').forEach(input => {
        if(input.closest('.password-input-wrap, .senha-control')) return;
        const wrap = document.createElement('div');wrap.className='senha-control';
        input.before(wrap);wrap.append(input);
        const button = document.createElement('button');button.type='button';button.textContent='Mostrar';
        button.setAttribute('aria-controls',input.id);button.setAttribute('aria-pressed','false');
        button.setAttribute('aria-label','Mostrar '+(input.labels?.[0]?.textContent || 'senha').trim());
        wrap.append(button);
        const ocultar = () => {input.type='password';button.textContent='Mostrar';button.setAttribute('aria-pressed','false');button.setAttribute('aria-label','Mostrar '+(input.labels?.[0]?.textContent || 'senha').trim());};
        button.addEventListener('click',()=>{const mostrar=input.type==='password';input.type=mostrar?'text':'password';button.textContent=mostrar?'Ocultar':'Mostrar';button.setAttribute('aria-pressed',String(mostrar));button.setAttribute('aria-label',(mostrar?'Ocultar ':'Mostrar ')+(input.labels?.[0]?.textContent || 'senha').trim());});
        input.form?.addEventListener('reset',ocultar);
    });
})();
