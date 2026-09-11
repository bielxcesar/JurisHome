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

function exibirDataAtual() {
  const dataElemento = document.getElementById("data-atual");
  if (dataElemento) {
    const hoje = new Date();
    dataElemento.textContent = hoje.toLocaleDateString("pt-BR");
  }
}

function configurarMenuPerfil() {
  const btnPerfil = document.getElementById("btn-perfil");
  const dropdownPerfil = document.getElementById("dropdown-perfil");

  if (!btnPerfil || !dropdownPerfil) return;

  btnPerfil.addEventListener("click", (e) => {
    e.stopPropagation();
    
    const estaOculto = dropdownPerfil.classList.contains("hidden");

    if (estaOculto) {
      dropdownPerfil.classList.remove("hidden");
      dropdownPerfil.classList.add("ativo", "active", "block");
    } else {
      dropdownPerfil.classList.add("hidden");
      dropdownPerfil.classList.remove("ativo", "active", "block");
    }
  });

  document.addEventListener("click", (e) => {
    if (!dropdownPerfil.contains(e.target) && !btnPerfil.contains(e.target)) {
      dropdownPerfil.classList.add("hidden");
      dropdownPerfil.classList.remove("ativo", "active", "block");
    }
  });
}

function configurarLinksExternos() {
  const linksExternos = document.querySelectorAll('a[href^="http"]');
  linksExternos.forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });
}

configurarBotaoCopiarLink();

function configurarBotaoCopiarLink() {
  const btnCopiar = document.getElementById("btn-copiar-link");
  const msgCopiado = document.getElementById("msg-copiado");

  if (!btnCopiar || !msgCopiado) return;

  btnCopiar.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      
      msgCopiado.classList.remove("hidden");

      setTimeout(() => {
        msgCopiado.classList.add("hidden");
      }, 3000);
    } catch (err) {
      console.error("Erro ao copiar o link: ", err);
    }
  });
}