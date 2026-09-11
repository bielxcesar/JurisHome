// 1. Aplicação imediata do tema salvo no localStorage para evitar oscilação (flicker)
(function aplicarTemaInicial() {
  const temaSalvo = localStorage.getItem("tema_juris");
  
  if (temaSalvo === "claro") {
    document.body?.classList.add("modo-claro");
    document.documentElement.classList.remove("dark");
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.body?.classList.remove("modo-claro");
    document.documentElement.classList.add("dark");
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();

document.addEventListener("DOMContentLoaded", () => {
  carregarTemaSalvo();
  exibirDataAtual();
  configurarMenuPerfil();
  configurarLinksExternos();
});

/**
 * Carrega e aplica o tema configurado ("tema_juris")
 */
function carregarTemaSalvo() {
  const temaSalvo = localStorage.getItem("tema_juris");

  if (temaSalvo === "claro") {
    document.body.classList.add("modo-claro");
    document.documentElement.classList.remove("dark");
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.body.classList.remove("modo-claro");
    document.documentElement.classList.add("dark");
    document.documentElement.setAttribute("data-theme", "dark");
  }
}

/**
 * Exibe a data formatada (DD/MM/AAAA) no elemento com ID "data-atual"
 */
function exibirDataAtual() {
  const dataElemento = document.getElementById("data-atual");
  if (dataElemento) {
    const hoje = new Date();
    dataElemento.textContent = hoje.toLocaleDateString("pt-BR");
  }
}

/**
 * Controla a exibição do dropdown do perfil
 */
function configurarMenuPerfil() {
  const btnPerfil = document.getElementById("btn-perfil");
  const dropdownPerfil = document.getElementById("dropdown-perfil");

  if (!btnPerfil || !dropdownPerfil) return;

  // Alterna visibilidade ao clicar no ícone do perfil
  btnPerfil.addEventListener("click", (e) => {
    e.stopPropagation();
    
    // Remove o 'hidden' do Tailwind e alterna classes de estado
    const estaOculto = dropdownPerfil.classList.contains("hidden");

    if (estaOculto) {
      dropdownPerfil.classList.remove("hidden");
      dropdownPerfil.classList.add("ativo", "active", "block");
    } else {
      dropdownPerfil.classList.add("hidden");
      dropdownPerfil.classList.remove("ativo", "active", "block");
    }
  });

  // Fecha o menu se o usuário clicar fora dele
  document.addEventListener("click", (e) => {
    if (!dropdownPerfil.contains(e.target) && !btnPerfil.contains(e.target)) {
      dropdownPerfil.classList.add("hidden");
      dropdownPerfil.classList.remove("ativo", "active", "block");
    }
  });
}

/**
 * Configura links externos HTTP/HTTPS para abrir em nova aba
 */
function configurarLinksExternos() {
  const linksExternos = document.querySelectorAll('a[href^="http"]');
  linksExternos.forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });
}
// Adicione dentro de document.addEventListener("DOMContentLoaded", () => { ... })
configurarBotaoCopiarLink();

/**
 * Copia a URL atual para a área de transferência e exibe o aviso
 */
function configurarBotaoCopiarLink() {
  const btnCopiar = document.getElementById("btn-copiar-link");
  const msgCopiado = document.getElementById("msg-copiado");

  if (!btnCopiar || !msgCopiado) return;

  btnCopiar.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      
      // Exibe a mensagem "Link copiado com sucesso"
      msgCopiado.classList.remove("hidden");

      // Esconde o aviso automaticamente após 3 segundos
      setTimeout(() => {
        msgCopiado.classList.add("hidden");
      }, 3000);
    } catch (err) {
      console.error("Erro ao copiar o link: ", err);
    }
  });
}