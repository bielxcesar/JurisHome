"""Respostas de erro sem detalhes internos e sem depender de acesso ao banco."""
import uuid
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory='templates')
MENSAGENS = {
    400: ('Não conseguimos entender este pedido', 'Alguma informação chegou incompleta ou em um formato inesperado.', 'Volte à página anterior, confira os campos e tente novamente.'),
    401: ('Sua sessão precisa ser renovada', 'O período de acesso pode ter terminado ou o login ainda não foi concluído.', 'Entre novamente para continuar usando o JurisHome.'),
    403: ('Não foi possível abrir esta página', 'Este conteúdo não está disponível para esta conta.', 'Volte ao início e use as opções disponíveis no seu menu.'),
    404: ('Não encontramos esta página', 'O endereço pode estar incompleto, ter mudado ou não estar disponível para esta conta.', 'Confira o endereço ou volte ao início para continuar navegando.'),
    405: ('Esta ação não está disponível aqui', 'A página recebeu uma ação diferente da que esperava.', 'Abra a página pelo menu do site e tente novamente.'),
    408: ('A resposta demorou mais que o esperado', 'A conexão ou o processamento demorou demais para concluir o pedido.', 'Confira sua conexão e tente novamente em alguns instantes.'),
    409: ('Uma informação mudou durante a ação', 'A página pode ter sido atualizada em outra aba ou o registro já pode ter sido alterado.', 'Atualize a página e confira as informações antes de continuar.'),
    413: ('O arquivo enviado é grande demais', 'O envio ultrapassou o tamanho aceito pelo site.', 'Escolha um arquivo menor e confira o limite indicado no formulário.'),
    422: ('Precisamos que você confira os dados', 'Um campo pode estar faltando ou ter um valor que o site não consegue aceitar.', 'Volte ao formulário e confira as informações antes de reenviar.'),
    429: ('Vamos aguardar um pouco', 'Foram feitas várias tentativas em um intervalo curto.', 'Espere alguns minutos antes de tentar novamente.'),
    500: ('Algo deu errado por aqui', 'O JurisHome encontrou um problema interno ao processar este pedido.', 'Tente novamente em alguns instantes. Se estava enviando um formulário, confira se a ação foi concluída antes de reenviar.'),
    502: ('Uma parte do serviço não respondeu como esperado', 'A comunicação entre os serviços que atendem o site encontrou um problema.', 'Aguarde um pouco e tente abrir a página novamente.'),
    503: ('O serviço está temporariamente indisponível', 'O site pode estar em manutenção ou com dificuldade para atender neste momento.', 'Tente novamente em alguns instantes.'),
    504: ('O serviço demorou para responder', 'Uma parte do sistema não respondeu dentro do tempo esperado.', 'Aguarde um pouco e tente novamente.'),
    505: ('Não foi possível concluir a comunicação', 'O servidor não aceitou a versão de comunicação usada neste pedido.', 'Atualize a página ou tente usar um navegador atualizado. Se continuar, tente novamente mais tarde.'),
}


def eh_pagina(request):
    if request.method not in {'GET', 'HEAD'} or request.url.path.startswith(('/api/', '/static/')):
        return False
    accept = request.headers.get('accept', '')
    return 'text/html' in accept or not accept or '*/*' in accept


def resposta_erro(request, codigo):
    padrao = ('Não foi possível concluir agora', 'O site encontrou uma dificuldade para atender este pedido.', 'Volte ao início ou tente novamente mais tarde.')
    titulo, explicacao, orientacao = MENSAGENS.get(codigo, padrao)
    referencia = getattr(request.state, 'correlacao_id', None) or str(uuid.uuid4())
    perfil = getattr(request.state, 'tipo_usuario', None)
    inicio = '/home_admin' if perfil == 'administrador' else '/home_usuario' if perfil == 'estudante' else '/'
    headers = {'Cache-Control': 'no-store, max-age=0', 'Pragma': 'no-cache',
               'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
               'Referrer-Policy': 'strict-origin-when-cross-origin', 'X-Correlation-ID': referencia,
               'Permissions-Policy': 'camera=(), geolocation=(), microphone=()'}
    if not eh_pagina(request):
        return JSONResponse(status_code=codigo, content={'detail': titulo, 'referencia': referencia}, headers=headers)
    return templates.TemplateResponse(request=request, name='erro.html', status_code=codigo, headers=headers, context={
        'codigo': codigo, 'titulo': titulo, 'explicacao': explicacao, 'orientacao': orientacao,
        'referencia': referencia, 'inicio': inicio, 'pode_tentar': codigo >= 500 or codigo == 408,
    })
