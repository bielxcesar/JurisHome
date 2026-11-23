# Usuários fictícios em banco isolado

O gerador usa somente `tests/dados_gerados/usuarios_ficticios.sqlite3`, um SQLite dedicado, e não lê nem altera dados do banco da aplicação. Ele exige `JURISHOME_TEST_MODE=1`, recusa indicadores de produção ou Railway e configuração de banco não SQLite. Se já existir um arquivo que não tenha a marca do gerador, a operação é recusada. Nunca execute em produção.

Com as dependências do projeto instaladas, no PowerShell, na raiz do projeto:

```powershell
$env:JURISHOME_TEST_MODE = '1'
python scripts/usuarios_ficticios.py criar
```

Informe duas vezes uma frase secreta de pelo menos 16 caracteres. O programa cria até 100 estudantes com nomes fictícios e endereços de `usuario001@example.invalid` a `usuario100@example.invalid`. A mesma execução pode ser repetida sem duplicar contas. Cada senha é diferente e derivada da frase; só o hash é armazenado. Guarde a frase fora do repositório. Para exibir a senha de uma conta no terminal privado, informe o número e a mesma frase:

```powershell
python scripts/usuarios_ficticios.py senha --numero 1
```

Não compartilhe a saída nem a frase. O gerador não ativa o segundo fator e não registra aceites em nome de pessoas: ao usar as contas com a aplicação apontada explicitamente para esse banco isolado, é necessário completar o fluxo normal de configuração do autenticador e os aceites aplicáveis. Estas contas são para dados fictícios, não representam consentimento real.

Para remover somente as contas rastreadas pelo gerador:

```powershell
python scripts/usuarios_ficticios.py remover
```

Se as contas tiverem registros relacionados, as restrições do banco podem impedir a remoção; nesse caso a transação é revertida e os dados devem ser analisados no banco de teste. O arquivo SQLite fica ignorado pelo Git. O gerador não inicia automaticamente com a aplicação.
