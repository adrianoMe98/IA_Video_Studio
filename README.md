# IA Video Studio v1.4 — Slide Studio

Plataforma Docker de produção de **videoaulas, cursos e apresentações profissionais em PT-BR**, com blocos inteligentes e layout customizado. Derivada da v1.2, preserva o módulo de videoaulas e o **Wan/ComfyUI** opcional.

**Alvo inicial:** Debian Sid, Lenovo IdeaPad Gaming 3i, i5-10300H, 16 GB RAM, GTX 1650 4 GB. O **Slide Studio e as videoaulas usam CPU**, sem exigir a GPU. ComfyUI permanece um serviço GPU separado.

## Novidades v1.4

- **Ilustrações educativas com IA opcional** via ComfyUI local, com fila de uma geração, prévia, aprovação e registro de procedência.
- **Diagramas técnicos** com nós, conexões direcionadas, ramificações, rótulos e grupos identificados. As formas e os textos continuam editáveis no PPTX.
- **Biblioteca por projeto** com miniaturas, busca, filtros por origem, edição de detalhes e proteção contra exclusão de imagens em uso.

### Atualizar da v1.3

Na mesma pasta de instalação, pare os serviços com `docker compose down` usando a configuração original. Faça backup de `studio-data`, `data`, `.env` e, se usado, do volume nomeado do Ollama. Atualize os arquivos da aplicação e execute `./scripts/preparar.sh && docker compose up -d --build studio`. O script preserva o `.env` existente. Mantenha o diretório de instalação e os caminhos das montagens, ou copie os dados para o novo diretório antes de iniciar. Use o backup para voltar à v1.3, pois editar projetos com o schema anterior pode descartar campos da v1.4.

### Ativar ilustrações educativas

1. Coloque um checkpoint **SD 1.5** em formato `.safetensors` de uma fonte confiável em `data/models/checkpoints/`. Confira a licença e a revisão antes de usar. O Studio usa os arquivos já baixados pelo operador.
2. Configure `COMFY_IMAGE_URL=http://comfyui:8188` e `COMFY_IMAGE_CHECKPOINT=nome-do-arquivo.safetensors` no `.env`. Para registrar a revisão ou o SHA-256 do checkpoint nas imagens aprovadas, preencha também `COMFY_IMAGE_MODEL_REVISION`. Para ativar os serviços, execute:

   ```bash
   docker compose -f compose.yaml -f compose.comfy.yaml --profile imagens-ia up -d --build studio comfyui
   ```

3. Em uma cena, clique **Gerar imagem**, revise o prompt e aguarde a prévia. Aprove após conferir a fidelidade técnica. Selecione a imagem na cena e escolha um bloco que exiba imagens, como **Texto + imagem**. O botão **Descartar** abandona o resultado no Studio. Um job já submetido pode terminar no ComfyUI, que grava sua saída em `data/output/studio-educativo/`.
4. Para desativar, deixe os dois campos vazios e recrie o serviço `studio`. Imagens aprovadas permanecem no projeto e seguem disponíveis nas exportações.

O preset inicial usa 512 × 512 e lote 1. Na GTX 1650 de 4 GB, execute geração de imagem e jobs Wan em sessões separadas. O Studio verifica se o ComfyUI está ocioso antes de submeter. Verifique o driver, o Toolkit, o pico de VRAM e a inferência real no notebook antes de adotar o preset para produção.

### Editar um diagrama técnico

Abra **Diagrama técnico** na cena e use **Preencher exemplo GPON** para começar. O JSON contém `nodes` (com `id`, `label` e `group` opcional) e `edges` (com `source`, `target` e `label` opcional). Use IDs únicos e conexões sem ciclos. O layout aceita até 12 nós, 16 conexões e quatro colunas com até quatro nós cada. Salvando uma fonte válida, a cena usa o bloco de diagrama. Limpe o campo para voltar ao bloco selecionado.

## Recursos introduzidos na v1.3

- Novo painel **Slide Studio** no editor existente, com pré-visualização por slide em SVG.
- **10 blocos inteligentes:** Capa, Objetivos, Conceito, Texto+Imagem, Comparação, Passo a Passo, Diagrama, Exemplo, Quiz e Resumo.
- **4 temas visuais:** Tech Blue, Corporate Clean, Creative Course e Minimal Focus.
- **Organizar slides**: heurística local seleciona blocos conforme o título, quantidade de tópicos e posição (não inventa informações).
- **Biblioteca de imagens por projeto**: upload PNG/JPG/WebP, normalizado em PNG, atribuição por cena e persistência.
- **PptxGenJS**: exportação PPTX com textos, caixas e diagramas nativos **editáveis**. Imagens importadas permanecem imagens raster.
- **PDF vetorial** e PNG de cada cena gerados a partir da mesma estrutura de desenho do SVG.
- **Exportar PPTX + PDF sem voz**: não é preciso baixar o Piper para criar apresentações.
- Renderização MP4 passa a utilizar os novos slides e preserva áudio Piper e SRT.
- Projetos antigos continuam carregando sem alteração de JSON; novos campos têm valores padrão.
- Renomear, duplicar (inclusive mídias), pesquisar, excluir, lixeira e restaurar continuam funcionando.

## Migrar a partir da v1.2

Coloque as pastas de versão lado a lado em `~/Downloads`. **Nunca use `docker compose down -v`, nem apague `studio-data`**.

```bash
# 1) Pare a versão antiga sem remover dados
cd ~/Downloads/ia-video-studio-v1.2
docker compose down

# 2) Backup preventivo
mkdir -p ~/Backups
tar -czf "$HOME/Backups/ia-video-v1.2-$(date +%F).tar.gz" studio-data

# 3) Migre para a pasta nova
cd ~/Downloads/ia-video-studio-v1.4
./scripts/migrar-v1.2.sh ../ia-video-studio-v1.2
# Use --comfy no final se quiser copiar também os modelos, workflows e saídas Wan.

# 4) Inicie o estúdio
./scripts/preparar.sh
docker compose up -d --build studio
docker compose ps
curl -f http://127.0.0.1:8787/api/health
```

Se o projeto antigo estiver em outro diretório, informe seu caminho absoluto a `migrar-v1.2.sh`. O script **não sobrescreve** projetos com IDs existentes no destino e mantém a pasta v1.2 original intacta. Se a v1.4 já tiver um container homônimo, pare-o antes de migrar. As vozes são copiadas; não precisam ser baixadas novamente.

### Instalação do zero

```bash
cd ia-video-studio-v1.4
./scripts/preparar.sh
docker compose build studio
./scripts/baixar-voz.sh    # necessário apenas para narração
# Se a voz falhar por DNS: confira a resolução do Hugging Face pelo Docker.
docker compose up -d studio
```

Acesse **http://127.0.0.1:8787** no notebook. A aplicação só publica a porta no localhost por padrão e **não tem autenticação**: não a exponha à internet.

## Como usar o Slide Studio

1. Entre no projeto existente ou clique **Criar** para abrir as 3 cenas GPON de exemplo.
2. No painel **Slide Studio**, escolha um dos quatro temas.
3. Escolha um **bloco visual** em cada cena; ou use **Organizar slides** para sugestões automáticas de blocos, que podem ser alteradas manualmente.
4. Se desejar ilustrar a cena com foto ou print de equipamento, use **Adicionar imagem à biblioteca** e escolha a imagem no seletor da cena. O bloco **Texto + imagem** usa o visual à direita. O bloco **Diagrama / topologia** constrói formas automaticamente com base nos tópicos, sem depender de imagens externas.
5. Clique **Prévia** na cena para salvar e abrir sua representação visual. As edições ainda podem ser feitas na sequência.
6. Clique **Exportar PPTX + PDF** para criar a apresentação sem voz; ou **Gerar videoaula** para compor MP4 narrado com legendas.
7. Baixe os arquivos em **Arquivos exportados** ou em `studio-data/projects/<ID>/exports/`.

As **imagens são por projeto**: ao duplicar um projeto, sua biblioteca visual também é copiada. Formatos aceitos: PNG, JPEG e WebP até **6 MB por envio**, largura/altura até **4000 px** e no máximo **40 imagens por projeto**. Arquivos são validados e regravados para PNG. Em vez de buscar automaticamente imagens de marcas/equipamentos (o que pode gerar ilustrações falsas), a primeira versão do Slide Studio deixa você selecionar a referência real.

### Demonstração de slides GPON incluída

Há um exemplo de três slides em `examples/demo-gpon/`, com os arquivos `exports/slides.pdf`, `exports/slides.pptx` e `slide-01.png` a `slide-03.png`. É material ilustrativo gerado pelo próprio Slide Studio para mostrar o padrão visual; **não é um curso completo**.

**Atenção à fidelidade:** PPTX contém caixas, textos e formas editáveis; SVG/PNG/PDF vêm do motor vetorial que desenha a mesma estrutura. Diferenças pequenas de fonte ou quebras de linha podem ocorrer entre aplicativos PowerPoint/LibreOffice e o SVG de prévia. Revise apresentações antes da publicação.

## Videoaulas, TTS e legendas

- Narração Piper offline em **português brasileiro** (vozes Faber e Edresson, baixadas separadamente).
- Sincronização de legendas por **sentença sintetizada**, não por palavra.
- Exportação **H.264/AAC, 720p ou 1080p**, com arquivo SRT e legendas selecionáveis; queima de legendas opcional.
- Duração depende do roteiro da narração, sem limite artificial de cinco segundos por cena; renderização longa pode exigir muito tempo e espaço no notebook.
- Importação PDF (texto extraído), Markdown e TXT para rascunho; não interpreta diagramas, nem aplica OCR. **Revise o material técnico**.
- Para sugerir roteiros com Ollama/Qwen2.5 1.5B, execute `./scripts/iniciar-roteiro-ia.sh`. Escolha uma duração-alvo de 1 a 5 minutos no editor. A sugestão traz uma estimativa de leitura e pode ser aplicada após confirmação. A duração real depende do ritmo da voz Piper e do texto final.

### ComfyUI / Wan opcional

```bash
nvidia-smi
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
./scripts/baixar-modelos.sh
docker compose -f compose.yaml -f compose.comfy.yaml --profile wan up -d comfyui
```

ComfyUI: **http://127.0.0.1:8188**. Os 4 GB da GTX 1650 são limitantes e o Wan pode não conseguir completar a geração. O Slide Studio não depende dele.

## Diretórios

```text
ia-video-studio-v1.4/
├── Dockerfile.studio                 # CPU, CairoSVG, PptxGenJS e Piper
├── Dockerfile.comfy                  # GPU/ComfyUI opcional
├── compose.yaml                     # Studio + voz + Ollama opcional
├── compose.comfy.yaml               # Perfil Wan
├── studio/
│   ├── app.py                       # API de projetos, mídia, prévia e exportação
│   ├── slide_studio.py              # motor vetorial de layouts reutilizáveis
│   ├── renderer/export_pptx.cjs     # saída nativa editável via PptxGenJS
│   ├── core.py                      # áudio, legendas e montagem MP4
│   └── static/                     # interface web
├── studio-data/
│   ├── projects/<ID>/
│   │   ├── project.json             # título, tema, cenas e layouts
│   │   ├── assets/<ID>.png          # imagens do projeto
│   │   ├── build/slide_studio/      # SVG, PNG, PDF intermediário e JSON dos slides
│   │   ├── exports/{slides.pdf,slides.pptx,video.mp4,legendas.srt}
│   │   └── job.json
│   ├── trash/                       # lixeira de projetos
│   └── voices/                      # modelos de voz do Piper
├── docs/ARQUITETURA.md              # API, escolhas técnicas e extensões
├── scripts/migrar-v1.2.sh
├── tests/                            # testes automatizados
└── data/                             # modelos Wan opcionais
```

**Persistência:** os volumes são diretórios externos à imagem. `docker compose down` mantém os dados, mas `docker compose down -v` pode remover volumes nomeados do Ollama.

## Administração e testes

```bash
docker compose ps
docker compose logs -f --tail=100 studio
docker stats ia-video-studio
./scripts/diagnostico.sh

# Após instalar studio/requirements.txt, studio/requirements-test.txt e PptxGenJS no host:
NODE_PATH=$(npm root -g) python3 -m unittest discover -s tests -v

# Recomendado após build: executar testes usando dependências da própria imagem
docker compose run --rm --no-deps --entrypoint python studio -m unittest discover -s /opt/tests -v
node --check studio/static/app.js
for f in scripts/*.sh; do bash -n "$f"; done

# Parar sem perder dados
docker compose down
```

A suíte verifica APIs, mídia, prévia SVG, exportação PDF/PPTX e o fluxo da geração com um ComfyUI simulado. Voz Piper real e inferência em GPU devem ser verificadas no equipamento-alvo. Se o contêiner acusar permissão em `studio-data`, confira `PUID`/`PGID` no `.env` e as permissões do diretório.

## Limitações conhecidas / próximo ciclo

- Preview é **por slide salvo**, não drag-and-drop; o próprio usuário escolhe o bloco de layout e a imagem.
- A exportação PPTX preserva texto e formas editáveis, mas utiliza fontes disponíveis no ambiente; revise aparência em PowerPoint e LibreOffice.
- Diagramas técnicos usam um grafo em JSON e disposição em colunas. O editor gráfico livre e a importação de Mermaid/D2 ficam para um ciclo posterior.
- A renderização de slides está limitada aos 30 slides por projeto herdados da v1.2. Expandir esse limite exigirá atualização dos fluxos e testes de memória.
- O export de slides usa CPU e pode consumir recursos por alguns segundos em apresentações longas. Não execute múltiplas renderizações simultâneas.

## Segurança

Instalação destinada a **uso local pessoal**. Não publique a porta sem autenticação. O upload aceita apenas imagens raster validadas; não aceita SVG nem URLs externas arbitrárias. Para material técnico, valide os dados produzidos pela IA antes de publicar. Respeite direitos autorais de imagens e políticas de uso das vozes.
