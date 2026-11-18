# IA Video Studio — contexto técnico para continuidade

> Documento de contexto **público**, para continuidade entre Codex no VS Code, ChatGPT e revisão pelo Gemini. Não é um log de conversas, nem substitui verificação do repositório.
>
> Atualizado inicialmente em **2026-11-18**, com base em `README.md` e `docs/ARQUITETURA.md` da branch `main`. Revalidar antes de novas implementações.

## Resumo do produto

Plataforma local baseada em Docker para criação de videoaulas, apresentações, slides editáveis e arquivos de exportação. O Slide Studio oferece blocos de layout, temas, prévia SVG, imagens PNG, exportação PDF e PPTX; narração Piper/FFmpeg e integração opcional com Ollama e ComfyUI/Wan são descritas no README.

## Estado conhecido (conforme documentação existente)

- **Base documentada:** IA Video Studio v1.3 — Slide Studio.
- **Compatibilidade:** dados de projetos antigos devem continuar sendo carregados sem migração destrutiva; `studio-data` contém dados persistentes.
- **Testes relatados no README:** 16 testes locais aprovados; esses testes **não foram executados nesta atualização de documentação**.
- **Validação ainda pendente, conforme README:** build completo via Docker Compose e síntese real com Piper no notebook.
- **Limitação descrita:** importação de imagens para slides é suportada, mas geração de novas fotografias por modelo de difusão não é parte da v1.3.

## Organização do trabalho com IA

- **Codex:** agente principal para analisar, implementar, testar e documentar.
- **Gemini/Antigravity:** revisão independente, com foco em bugs, segurança e arquitetura.
- **GitHub:** registro versionado e ponto de consulta do contexto técnico.
- **ChatGPT no celular:** pode consultar esta documentação publicada com acesso ao repositório, mas não recebe automaticamente o texto integral das conversas do Codex.

## Decisões registradas

| Data | Decisão | Motivo |
| --- | --- | --- |
| 2026-11-18 | Criar um arquivo de continuidade versionado | Permitir retomar trabalho em diferentes interfaces sem recontar todo o projeto |
| 2026-11-18 | Armazenar somente contexto técnico publicável | O repositório é público; proteger dados pessoais, credenciais e ambientes internos |
| 2026-11-18 | Não enviar commits ou deploys automaticamente | Manter revisão e aprovação humana antes de efeitos externos |

## Trabalho em andamento

- **Objetivo:** estabelecer fluxo de retomada de contexto entre VS Code, GitHub e ChatGPT.
- **Alterações propostas:** `AGENTS.md`, este arquivo e `docs/FLUXO_CHATGPT_CODEX.md`.
- **Estado:** documentação inicial preparada em branch separada, sujeita a revisão e integração.
- **Próximo passo:** revisar o pull request, integrar as instruções e experimentar a primeira atualização após uma tarefa real no Codex.
- **Não validado:** sincronização de mensagens completas ou atualização automática remota, pois não são implementadas por esses arquivos.

## Modelo para próximas atualizações

### AAAA-MM-DD — [título da tarefa]

- **Estado:** concluído / em andamento / bloqueado.
- **Objetivo e decisão:** …
- **Arquivos ou componentes:** …
- **Verificação observada:** comando, resultado, ambiente ou “não executada”.
- **Pendências / riscos:** …
- **Próximo passo:** …
- **Referência Git:** PR ou commit, se já existir.

Ao acrescentar novos registros, consolide decisões duradouras e remova duplicação; preserve apenas o contexto necessário para retomada. Não publique dados privados.
