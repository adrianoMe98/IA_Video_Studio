# Instruções para agentes de desenvolvimento

Este repositório contém o IA Video Studio. O **Codex é o agente principal** de implementação; o **Gemini/Antigravity é um revisor auxiliar**. O Git e os testes são a fonte de evidência do estado do projeto; respostas de IA não substituem verificações.

## Antes de alterar o projeto

- Consulte `README.md`, `docs/ARQUITETURA.md` e os arquivos relevantes para a tarefa.
- Para trabalhos com continuidade entre VS Code e ChatGPT, leia `docs/CONTEXTO_IA.md`. Ele é um resumo de decisões, **não** um histórico sincronizado de chats.
- Verifique o estado atual do código; não considere um plano ou anotação como prova de funcionalidade implementada.
- Preserve alterações locais e de outros agentes. Não sobrescreva arquivos ou trabalho em andamento sem avaliar as diferenças.

## Desenvolvimento e revisão

- Use português brasileiro nas explicações e na documentação, preservando nomes de APIs, comandos e identificadores técnicos.
- Explique sucintamente o objetivo, as mudanças, os testes efetivamente executados e os riscos.
- Codex: implemente, valide e corrija; Gemini: revise criticamente quando solicitado. Evite edições simultâneas dos mesmos arquivos.
- Mantenha compatibilidade com formatos de projeto existentes e com a persistência de `studio-data`.
- Nunca execute `docker compose down -v`, remova volumes persistentes ou dados de usuários, nem exponha serviços sem autenticação.
- Não realize deploy em produção, commit, push ou merge sem autorização específica da pessoa responsável.

## Continuidade entre sessões

Ao terminar **uma alteração técnica relevante**, proponha ou atualize `docs/CONTEXTO_IA.md`, registrando apenas:

1. Resultado e estado real: concluído, em andamento, pendente ou bloqueado.
2. Arquivos e componentes afetados, quando houver.
3. Decisões arquiteturais e motivos essenciais.
4. Testes realmente executados e resultados observados; identifique claramente o que não foi testado.
5. Pendências, riscos e próximo passo recomendado.

Não registre conversas completas, prompts privados, tokens, credenciais, endereços internos, informações pessoais, dados de clientes ou conteúdo confidencial. **Este repositório é público.** Caso seja necessário preservar contexto sensível, use um armazenamento privado apropriado e peça autorização antes de publicar.

A atualização do documento é parte da tarefa local; a disponibilidade dele no ChatGPT do celular depende de revisão e publicação no GitHub. **Não há sincronização nativa automática de todo o histórico das conversas.**

Consulte `docs/FLUXO_CHATGPT_CODEX.md` para o procedimento de retomada.
