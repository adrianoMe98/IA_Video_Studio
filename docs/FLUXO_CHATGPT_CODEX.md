# Continuidade entre Codex no VS Code e ChatGPT no celular

## O que esta integração faz

Permite recuperar **contexto técnico aprovado e publicado** no GitHub. Não sincroniza automaticamente mensagens, anexos nem históricos privados da extensão do Codex com chats normais do ChatGPT.

- O Codex lê `AGENTS.md` e consulta `docs/CONTEXTO_IA.md` para entender o estado documentado.
- Ao concluir uma implementação relevante, atualiza o contexto com fatos verificáveis.
- O responsável revisa e publica as alterações pelo fluxo habitual de branch e pull request.
- O ChatGPT no Android, com acesso ao repositório pelo GitHub conectado, consulta esse documento para retomar o assunto.

**Importante:** sem push/merge da versão atualizada, o celular só verá a versão já acessível no GitHub. Se o repositório não estiver conectado ao ChatGPT, será necessário conectar o GitHub ou fornecer o documento manualmente.

## No VS Code — após uma mudança relevante

Peça ao Codex:

> Faça um resumo verificável do trabalho realizado nesta sessão e atualize somente as seções pertinentes de `docs/CONTEXTO_IA.md`, seguindo `AGENTS.md`. Registre arquivos envolvidos, decisões, testes executados e pendências. Não copie a conversa completa, não inclua dados sensíveis e não faça commit nem push sem minha aprovação. Mostre o diff para revisão.

Antes de publicar, confira:

```bash
git status
git diff -- docs/CONTEXTO_IA.md
git diff --check
```

Depois de aprovar, faça o commit na branch de trabalho, envie-a ao GitHub e abra um pull request para `main`. Faça o merge quando a revisão estiver concluída. Evite commits automáticos sem inspeção.

## No ChatGPT para Android — retomada do projeto

Com acesso ao GitHub habilitado na conversa, use este pedido:

> Consulte o repositório `adrianoMe98/IA_Video_Studio`, branch `main`. Leia `docs/CONTEXTO_IA.md`, `README.md` e, se necessário, `docs/ARQUITETURA.md`. Explique o estado real, o que está pendente e o próximo passo. Não presuma que anotações substituem testes ou o código atual.

Se a atualização ainda estiver em uma branch ou pull request, informe o nome da branch/PR em vez de `main`.

## De volta ao Codex no VS Code

> Leia `AGENTS.md` e `docs/CONTEXTO_IA.md`. Confira o estado real do Git e os arquivos citados, diferencie implementado de planejado e proponha o próximo passo sem alterar produção ou publicar código automaticamente.

## Revisão com Gemini

> Faça uma revisão independente das alterações desta branch em relação à base. Consulte `AGENTS.md` e `docs/CONTEXTO_IA.md`. Priorize bugs reproduzíveis, regressões, falhas de segurança e inconsistências com o estado registrado. Não edite arquivos até receber autorização.

## Quando usar recursos nativos da OpenAI

- **Codex Cloud:** tarefas em ambiente de nuvem podem ser retomadas em interfaces compatíveis, inclusive mobile, conforme disponibilidade e configuração da conta.
- **Codex Remote:** permite controlar sessões de hosts compatíveis pelo app ChatGPT, quando suportado pelo host e habilitado. Não converte a conversa do Codex em histórico normal do ChatGPT.
- **Debian/VS Code:** não assuma que a extensão local possui pareamento Remote disponível; confira o suporte atual antes de configurar. Este fluxo de arquivos Git independe do Remote.

Referência oficial: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

## Segurança e limites

1. Este repositório é **público**: não publique logs de produção, tokens, credenciais, dados de clientes, IPs internos, conversas integrais nem informações pessoais.
2. O resumo não deve afirmar testes que não foram executados.
3. Contexto remoto só fica atualizado quando o documento atualizado é efetivamente disponibilizado no GitHub.
4. A política de revisão/merge e a proteção de dados têm prioridade sobre conveniência de sincronização.
