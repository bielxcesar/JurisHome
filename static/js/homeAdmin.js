document.addEventListener("DOMContentLoaded", () => {
    carregarTemaSalvo();
    exibirDataAtual();
    carregarConteudosHome();
    configurarMenuPerfil();
});

function carregarTemaSalvo() {
    const temaSalvo = localStorage.getItem("tema_juris");
    if (temaSalvo === "claro") {
        document.body.classList.add("modo-claro");
    } else {
        document.body.classList.remove("modo-claro");
    }
}

function exibirDataAtual() {
    const hoje = new Date();
    const dia = String(hoje.getDate()).padStart(2, '0');
    const mes = String(hoje.getMonth() + 1).padStart(2, '0');
    const ano = hoje.getFullYear();
    document.getElementById("data-atual").innerText = `${dia}/${mes}/${ano}`;
}

async function carregarConteudosHome() {
    try {
        const resposta = await fetch("/api/conteudos");
        const conteudos = await resposta.json();

        if (!conteudos || conteudos.length === 0) return;

        if (conteudos[0]) {
            document.getElementById("hero-titulo-1").innerText = conteudos[0].titulo;
            document.getElementById("hero-cat-1").innerText = "Direito Trabalhista";
        }

        if (conteudos[1]) {
            document.getElementById("hero-titulo-2").innerText = conteudos[1].titulo;
            document.getElementById("hero-cat-2").innerText = "Direito Trabalhista";
        } else if (conteudos[0]) {
            document.getElementById("hero-titulo-2").innerText = "Justiça reverte justa causa de funcionária após discussão no refeitório;";
            document.getElementById("hero-cat-2").innerText = "Direito Trabalhista";
        }

        if (conteudos[2]) {
            document.getElementById("hero-titulo-3").innerText = conteudos[2].titulo;
            document.getElementById("hero-cat-3").innerText = "Direito Trabalhista";
        } else {
            document.getElementById("hero-titulo-3").innerText = "Empresa é condenada a pagar indenização após chefe cobrar metas pelo WhatsApp";
            document.getElementById("hero-cat-3").innerText = "Direito Trabalhista";
        }

        const gridRecomendados = document.getElementById("grid-voce-pode-gostar");
        const itensRecomendados = conteudos.slice(3);
        
        if (itensRecomendados.length > 0) {
            gridRecomendados.innerHTML = itensRecomendados.map(item => `
                <article class="card-item">
                    <span class="categoria-tag">Direito Trabalhista</span>
                    <h4>${item.titulo}</h4>
                </article>
            `).join('');
        } else {
            gridRecomendados.innerHTML = `
                <article class="card-item"></article>
                <article class="card-item"></article>
                <article class="card-item"></article>
            `;
        }

    } catch (erro) {
        console.error("Erro ao carregar os dados:", erro);
    }
}

function configurarMenuPerfil() {
    const btnPerfil = document.getElementById("btn-perfil");
    const dropdown = document.getElementById("dropdown-perfil");

    if (!btnPerfil || !dropdown) return;

    btnPerfil.addEventListener("click", (e) => {
        e.stopPropagation();
        dropdown.classList.toggle("ativo");
    });

    document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target) && !btnPerfil.contains(e.target)) {
            dropdown.classList.remove("ativo");
        }
    });
}