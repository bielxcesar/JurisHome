(() => {
'use strict';
const $=id=>document.getElementById(id);
let administrador=JSON.parse($('admin-perfil-dados').textContent),salvando=false;
$('admin-perfil-form').addEventListener('submit',async evento=>{
 evento.preventDefault();if(salvando)return;
 const nome=$('admin-nome').value.trim(),email=$('admin-email').value.trim();
 const senha=$('admin-nova-senha').value;
 const dados={nome,email,versao:administrador.versao,encerrar_sessoes:$('admin-encerrar').checked,resetar_2fa:$('admin-reset-2fa').checked};
 if(senha)dados.nova_senha=senha;
 salvando=true;$('admin-perfil-salvar').disabled=true;$('admin-perfil-retorno').hidden=true;
 try{
  const resposta=await fetch('/api/admin/administradores/'+encodeURIComponent(administrador.uuid),{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados)});
  const corpo=await resposta.json().catch(()=>({}));
  if(!resposta.ok)throw new Error(typeof corpo.detail==='string'?corpo.detail:Array.isArray(corpo.detail)?corpo.detail.map(item=>item.msg.replace(/^Value error, /,'')).join(' '):'Não foi possível salvar. Tente novamente.');
  administrador=corpo.administrador;
  $('admin-nome').value=administrador.nome;$('admin-email').value=administrador.email;
  $('admin-nome-resumo').textContent=administrador.nome;$('admin-email-resumo').textContent=administrador.email;
  $('admin-2fa-status').textContent=administrador.is_2fa_enabled?'Ativa':'Configuração pendente';$('admin-sessoes').textContent=administrador.sessoesAtivas;
  $('admin-nova-senha').value='';$('admin-encerrar').checked=false;$('admin-reset-2fa').checked=false;
  $('admin-perfil-retorno').textContent=corpo.mensagem;
 }catch(erro){$('admin-perfil-retorno').textContent=erro.message;}
 finally{salvando=false;$('admin-perfil-salvar').disabled=false;$('admin-perfil-retorno').hidden=false;$('admin-perfil-retorno').focus();}
});
})();
