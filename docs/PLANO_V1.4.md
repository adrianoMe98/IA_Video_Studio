# Plano de implementação da v1.4

## Base analisada

O commit `98fb989` em `main` identifica a versão 1.3.0. O host-alvo é Debian Sid. A imagem do Studio usa Node 22 sobre Debian Bookworm, com Python em ambiente virtual, FFmpeg, Cairo e fontes locais. O navegador usa HTML, CSS e JavaScript estáticos. A API FastAPI roda com um worker Uvicorn.

| Serviço Compose | Ativação e responsabilidade | Dados persistentes |
| --- | --- | --- |
| `studio` | Padrão, CPU. Serve a interface e a API em `127.0.0.1:8787` por padrão. `/api/health` é usado pelo healthcheck. | Bind `./studio-data:/data` para projetos, lixeira e vozes. |
| `voice-download` | Perfil `tools`. Baixa modelos Piper PT-BR usados pela narração. | Escreve no mesmo `./studio-data`, em `/data/voices`. |
| `ollama` | Perfil `roteiro-ia`. Sugere cenas com Qwen2.5 1.5B por padrão, com revisão do usuário. Porta 11434 interna. | Volume nomeado `ollama-models` em `/root/.ollama`. |
| `comfyui` | Arquivo complementar `compose.comfy.yaml`, perfil `wan`. PyTorch/CUDA e GGUF, com `--lowvram`, `--cpu-vae` e `--force-fp16`. Publica `127.0.0.1:8188` por padrão. | Binds `./data/{models,custom_nodes,user,input,output,temp,cache}`. |
| `model-download` | Mesmo arquivo complementar, perfil `wan-tools`. Baixa o modelo Wan 2.1 1.3B GGUF, o encoder de texto e o VAE. | Reutiliza `./data/models` e `./data/cache`. |

### Slide Studio e vídeo

- O projeto guarda tema e cenas em `project.json`. Cada cena tem título, tópicos, narração, bloco e referência opcional a imagem. O Slide Studio tem quatro temas e dez blocos em canvas de 1280 × 720. A organização automática usa título, tópicos e posição. O bloco `diagram_slide` desenha até quatro etapas em uma linha a partir dos tópicos.
- A interface em `studio/static/app.js` salva o projeto antes da prévia e da exportação. `build_slide()` monta o plano declarativo em `studio/slide_studio.py`. `as_svg()` atende a prévia; CairoSVG gera PNG e páginas vetoriais do PDF; PptxGenJS recebe o mesmo plano para gerar texto e formas nativos no PPTX. A exportação de PDF/PPTX roda sem Piper, Ollama ou ComfyUI.
- A galeria já é por projeto. `GET` e `POST /api/projects/{id}/assets` listam e importam imagens. O upload valida PNG, JPEG e WebP e normaliza para PNG. Cada cena guarda o nome `<24 hex>.png`; duplicar o projeto copia `assets/`. Excluir e restaurar movem o diretório do projeto inteiro.
- Na videoaula, `POST /api/projects/{id}/render` enfileira `export_project()` em um executor de um worker. `job.json` fornece estado e progresso; jobs interrompidos pelo reinício passam para erro. O núcleo usa os frames do Slide Studio e sintetiza a narração por sentença com Piper. `ffprobe` mede os trechos para construir o SRT. FFmpeg compõe H.264/AAC em 720p ou 1080p, inclui legenda selecionável e pode produzir uma segunda versão com legenda queimada.
- O vídeo generativo é executado diretamente no ComfyUI. Os workflows Wan em `workflows/` declaram saídas de vídeo e WebP animado. O preset de 4 GB usa lote unitário, 17 quadros de 320 × 192 a 8 fps. `scripts/webp-para-mp4.sh` oferece conversão auxiliar. A API do Studio ainda não submete gerações ao ComfyUI.

### Cobertura existente

| Suíte | Casos | Cobertura |
| --- | --- | --- |
| `tests/test_api.py` | 3 | Saúde, CRUD, importação TXT e rejeição de voz inválida. |
| `tests/test_core.py` | 6 | Segmentação, tempos e escrita SRT, Markdown, importação e manifesto de concatenação. |
| `tests/test_management.py` | 3 | Busca, renomeação, cópia, lixeira, restauração, confirmação de exclusão e bloqueio durante renderização. |
| `tests/test_slide_studio.py` | 4 | Combinações de tema/bloco, upload e prévia, cópia de mídias, validações, auto-layout e exportação real de PDF/PPTX com texto editável. |

`scripts/validar.sh` também verifica sintaxe, arquivos Compose e consistência entre os dois JSONs Wan. A suíte não cobre síntese com voz real, montagem MP4 ponta a ponta, inferência Wan em GPU nem navegação em navegador. Essas verificações fazem parte da aceitação no equipamento-alvo.

A imagem da v1.3 copia `tests/`, mas `studio/requirements.txt` não inclui a dependência HTTP do `TestClient`. Para reproduzir a suíte, instale `httpx` em um ambiente de teste separado. Na v1.4, explicite as dependências de teste para tornar o comando documentado reproduzível na imagem.

## 1. Imagens educativas com IA, sob demanda

1. Implementar um conector para ComfyUI local, ativado explicitamente, com endpoint definido pelo operador e inacessível aos campos da cena. Prototipar um workflow fixo e versionado de imagem estática com um checkpoint leve da família SD 1.5, com licença e revisão registradas. Conservar o workflow Wan atual. Manter downloads de modelos em comando explícito, em perfil opcional, fora do build do Studio.
2. No Slide Studio, apresentar uma ação por cena para editar o prompt, enviar, acompanhar e descartar ou aprovar o resultado. Usar estados de geração separados de `job.json` do vídeo. Enviar somente o prompt revisado. Persistir o identificador do job do provedor para consultar o mesmo job e tratar timeout, reinício e resposta atrasada sem duplicar a geração ou vincular o resultado à cena errada.
3. Limitar a uma geração por vez, lote 1, resolução inicial de até 512 × 512 e parâmetros limitados pelo preset. Medir `lowvram` e offload na GTX 1650. No equipamento de 4 GB, usar imagem ou Wan na mesma GPU em sessões separadas. Se o operador habilitar ambos, exigir coordenação da fila antes de liberar uso concorrente. Lidar com indisponibilidade e falta de memória, devolvendo o controle sem travar edição, prévia, upload ou exportação.
4. Validar e reprocessar a saída pelo mesmo caminho raster do upload. Uma imagem pendente fica fora dos assets referenciáveis. Após aprovação, registrar procedência (origem, modelo e revisão, seed, parâmetros, prompt revisado e data), adicionar à biblioteca e permitir atribuição explícita. Rotular o conteúdo gerado como ilustração e exigir revisão humana de fidelidade técnica.

**Aceitação da fase.** Com o recurso desativado ou o provedor fora do ar, o Studio permanece funcional em CPU. Com a opção ativada, uma imagem aprovada aparece na prévia e nas exportações. Repetição da aprovação, cancelamento, timeout, reinício, exclusão do projeto durante a geração e falha de VRAM têm resultados previsíveis, sem sobrescrever uma imagem existente ou deixar uma referência quebrada.

## 2. Diagramas técnicos avançados

1. Adicionar à cena um campo opcional para a fonte do diagrama. Começar por fluxogramas ramificados e topologias com nós, arestas direcionadas, rótulos e agrupamento. Definir limites de complexidade e validar IDs, conexões, rótulos e dimensões no backend. Usar o fluxo atual de tópicos para cenas sem fonte estruturada.
2. Usar um grafo declarativo validado como formato interno. Avaliar importação de um subconjunto de Mermaid ou D2 após a prova de exportação. Converter a fonte em primitivas do plano compartilhado, com layout determinístico, textos legíveis e conectores distinguíveis. Tratar fonte e rótulos como dados, sem buscar URLs ou embutir HTML ou SVG fornecido pelo usuário.
3. Acrescentar edição e prévia na seção de cena. Preservar o campo nos modelos Pydantic e no ciclo `collectScenes()` / `populate()` da interface. Atualizar os renderizadores em conjunto quando o plano ganhar primitivas para conectores ou grupos. Manter nós, rótulos e conectores editáveis no PPTX.

**Aceitação da fase.** Uma topologia GPON com ramificações e um fluxo com decisão persistem após edição e reabertura. SVG, PDF, PPTX e frame de vídeo exibem os mesmos nós, rótulos e conexões. Uma fonte inválida recebe erro de validação e o último diagrama salvo continua disponível.

## 3. Biblioteca de imagens por projeto

1. Evoluir a galeria existente com miniaturas, título, texto alternativo, etiquetas, origem e licença quando conhecida. Adicionar busca e filtros por origem, com atribuição da imagem a qualquer cena do mesmo projeto. Usar a fase 1 para definir o mínimo de metadados de procedência e reaproveitá-lo nesta fase.
2. Manter os PNGs, IDs e rotas atuais. Adicionar metadados opcionais em arquivo auxiliar no diretório `assets/`, com escrita atômica. Listar imagens legadas mesmo sem metadados. Se a escrita de metadados ou a publicação do PNG falhar, repetir com segurança e deixar a galeria sem entradas parciais. Tratar imagens geradas e importadas com os limites de validação do projeto.
3. Permitir editar metadados e informar onde a imagem é usada antes de removê-la. Bloquear a remoção de PNG em uso até a desvinculação explícita, respeitando a trava de renderização. Conferir que a cópia do projeto preserva os metadados e que a lixeira pode ser restaurada com a mesma mídia. A biblioteca global entre projetos segue no ciclo posterior descrito na arquitetura.

**Aceitação da fase.** Uploads existentes permanecem vinculados e exportáveis. Imagens de ambas as origens podem ser localizadas e reutilizadas no projeto. A recriação do contêiner, a duplicação e o ciclo lixeira/restauração preservam mídias e metadados.

## Critérios para liberar a v1.4

- **Regressão automatizada.** Manter os 16 testes atuais. Acrescentar fixtures legadas sem campos novos, ida e volta pela API e pelo formulário, cenários de fila com provedor simulado, validade e editabilidade dos diagramas exportados, e preservação de referências na galeria. Os testes padrão continuam independentes de GPU e modelos.
- **Host Debian Sid.** Validar build e inicialização apenas de `studio`, saúde, navegação, permissão de escrita para `PUID`/`PGID` e exportação PDF/PPTX. Com uma voz Piper já instalada, renderizar um projeto antigo em 720p e 1080p, inspecionar streams com `ffprobe` e conferir SRT e a opção de legenda queimada.
- **GTX 1650 de 4 GB.** Registrar versões de driver, Docker, Toolkit e ComfyUI, pico de VRAM e RAM, tempo por imagem e resultado de gerações consecutivas. Exercitar falha e abandono do job. Rodar o preset Wan separadamente para verificar que a extensão de imagens não alterou o fluxo existente. Só anunciar presets com validação no hardware.
- **Persistência e retorno.** Fazer backup consistente de `studio-data`, `data`, `.env` e do volume Ollama quando usado. Ensaiar atualização e recriação dos contêineres em uma cópia com projetos ativos, lixeira, mídias, exportações e vozes. Manter caminhos, nome do projeto Compose e volume Ollama. Evitar regravação na leitura. Ensaiar retorno à v1.3 usando o backup, pois salvar com o schema antigo pode descartar campos da v1.4.
