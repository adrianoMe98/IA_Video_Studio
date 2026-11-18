# IA Video Studio

## Organização do projeto

- `studio/app.py` concentra a API FastAPI, os modelos Pydantic e a gestão de projetos, mídia e jobs. Mantenha validação e acesso a arquivos no backend, mesmo quando houver validação na interface.
- `studio/static/` contém HTML, CSS e JavaScript sem etapa de build. Mantenha a interface, as mensagens de erro e a documentação de uso em português do Brasil. Preserve os IDs técnicos de temas, blocos e recursos usados por projetos salvos.
- `studio/slide_studio.py` monta o plano visual compartilhado pela prévia SVG e pelas saídas PNG e PDF. `studio/renderer/export_pptx.cjs` traduz esse plano para objetos editáveis com PptxGenJS. Ao mudar um elemento visual, confira as quatro saídas e os frames usados no MP4.
- `studio/core.py` cuida da narração Piper, das legendas SRT e da composição FFmpeg em CPU. Mantenha a exportação de apresentações independente de voz, GPU e serviços de IA.
- `compose.yaml` define o Studio e os perfis de voz e roteiro. `compose.comfy.yaml` acrescenta o ComfyUI/Wan opcional. Mantenha a configuração padrão em localhost, o mapeamento `PUID`/`PGID` e o alvo Debian Sid. Dependências de GPU devem ficar no perfil opcional, com validação na GTX 1650 de 4 GB.

## Contratos de armazenamento e API

- Preserve os caminhos das montagens `./studio-data:/data`, `./data/*` do ComfyUI e o volume `ollama-models` associado ao projeto Compose `ia-video`. Ao trabalhar com cópias, mantenha o original e confira os caminhos antes da atualização. Use `docker compose down` para parar os serviços. A opção `-v` remove volumes nomeados e deve ficar fora do fluxo de atualização.
- Leia projetos legados com defaults. Preserve os IDs, as referências de mídia e as rotas existentes. Para campos novos, confira criação, leitura, edição pela interface, duplicação, lixeira e restauração. O `PUT` regrava os dados a partir dos modelos Pydantic e o JavaScript reconstrói o payload das cenas.
- Use os validadores de ID e caminhos do projeto e a escrita atômica de JSON. Coordene alterações de metadados e mídia com o estado das renderizações. Guarde imagens em `assets/<id>.png`, com validação raster e limites de formato, tamanho e dimensões. Trate textos e rótulos como dados ao renderizar HTML, SVG e PPTX.
- Mantenha `.env`, modelos, vozes, projetos e saídas geradas fora do Git. Use diretórios temporários para testes com `STUDIO_DATA` e `STUDIO_VOICES`.

## Validação e revisão

- Execute `./scripts/validar.sh` para validar sintaxe, o workflow Wan e os arquivos Compose. Confira a saída do script para saber se a suíte de testes foi executada na imagem.
- Para rodar a suíte no host, use um ambiente virtual com `studio/requirements.txt` e `httpx` para o `TestClient`, além de Cairo e `pptxgenjs@4.0.0` acessível ao Node. Execute `python3 -m unittest discover -s tests -v` e defina `NODE_PATH` se instalou o pacote Node fora da árvore de resolução padrão.
- Use fixtures geradas em diretórios temporários. A suíte principal deve rodar sem modelos de voz, GPU, downloads de modelos ou serviços de IA. Registre separadamente provas de exportação audiovisual, Compose no Debian Sid e medições na GTX 1650.
- Trabalhe em uma branch `dev/*` e abra um PR com o escopo, os resultados da validação e qualquer alteração nos contratos de API ou persistência. Consulte [Arquitetura da v1.3](docs/ARQUITETURA.md) e [Plano da v1.4](docs/PLANO_V1.4.md).
