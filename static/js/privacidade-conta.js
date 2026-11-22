(() => {
    'use strict';
    const form=document.getElementById('form-revogar-aceite');if(!form)return;
    const button=form.querySelector('button[type=submit]'),message=document.getElementById('revogacao-retorno');
    form.addEventListener('submit',async event=>{
        event.preventDefault();if(button.disabled||!form.reportValidity())return;
        button.disabled=true;message.hidden=true;
        try{
            const response=await fetch('/api/usuarios/me/aceite',{method:'DELETE',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({senha:document.getElementById('senha-revogacao').value,confirmacao:'REVOGAR'})});
            const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível revogar o aceite. Tente novamente.');
            form.reset();location.replace('/?aceite=revogado');
        }catch(error){message.textContent=error.message;message.hidden=false;button.disabled=false;}
    });
})();
