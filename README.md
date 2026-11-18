# IA Video Studio v1.3 — Slide Studio

Plataforma Docker de produção de **videoaulas, cursos e apresentações profissionais em PT-BR**, com blocos inteligentes e layout customizado. Derivada da v1.2, preserva o módulo de videoaulas e o **Wan/ComfyUI** opcional.

**Alvo inicial:** Debian Sid, Lenovo IdeaPad Gaming 3i, i5-10300H, 16 GB RAM, GTX 1650 4 GB. O **Slide Studio e as videoaulas usam CPU**, sem exigir a GPU. ComfyUI permanece um serviço GPU separado.

**Status:** 16 testes automatizados locais aprovados, incluindo geração efetiva de **PDF com 3 páginas**, **PPTX editável com 3 slides**, importação de PNG, prévia e regressão da API v1.2. O funcionamento completo do `docker compose build` e a síntese real com Piper ainda precisam ser testados no notebook. Não atribuir aos slides a condição de “imagens geradas por IA”: a versão 1.3 suporta upload de imagens, diagrama automático e desenho procedural, mas **não gera novas fotografias por modelo de difusão** (planejado para v1.4).

## Novidades v1.3

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

## Atualizar v1.2 → v1.3, sem perder projetos

Coloque as pastas de versão lado a lado em `~/Downloads`. **Nunca use `docker compose down -v`, nem apague `studio-data`**.

```bash
# 1) Pare a versão antiga sem remover dados
cd ~/Downloads/ia-video-studio-v1.2
docker compose down

# 2) Backup preventivo
mkdir -p ~/Backups
tar -czf "$HOME/Backups/ia-video-v1.2-$(date +%F).tar.gz" studio-data

# 3) Migre para a pasta nova
cd ~/Downloads/ia-video-studio-v1.3
./scripts/migrar-v1.2.sh ../ia-video-studio-v1.2
# Use --comfy no final se quiser copiar também os modelos, workflows e saídas Wan.

# 4) Inicie o estúdio
./scripts/preparar.sh
docker compose up -d --build studio
docker compose ps
curl -f http://127.0.0.1:8787/api/health
```

Se o projeto antigo estiver em outro diretório, informe seu caminho absoluto a `migrar-v1.2.sh`. O script **não sobrescreve** projetos com IDs existentes no destino e mantém a pasta v1.2 original intacta. Se a v1.3 já tiver um container homônimo, pare-o antes de migrar. As vozes são copiadas; não precisam ser baixadas novamente.

### Instalação do zero

```bash
cd ia-video-studio-v1.3
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
- Sugestão de roteiros com Ollama/Qwen2.5 1.5B opcional: `./scripts/iniciar-roteiro-ia.sh`. O módulo não precisa permanecer em execução enquanto renderiza.

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
ia-video-studio-v1.3/
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
├── tests/                            # 16 testes automatizados
└── data/                             # modelos Wan opcionais
```

**Persistência:** os volumes são diretórios externos à imagem. `docker compose down` mantém os dados, mas `docker compose down -v` pode remover volumes nomeados do Ollama.

## Administração e testes

```bash
docker compose ps
docker compose logs -f --tail=100 studio
docker stats ia-video-studio
./scripts/diagnostico.sh

# Após instalar dependências Python de studio/requirements.txt e PptxGenJS no HOST:
NODE_PATH=$(npm root -g) python3 -m unittest discover -s tests -v

# Recomendado após build: executar testes usando dependências da própria imagem
docker compose run --rm --no-deps --entrypoint python studio -m unittest discover -s /opt/tests -v
node --check studio/static/app.js
for f in scripts/*.sh; do bash -n "$f"; done

# Parar sem perder dados
docker compose down
```

**Testes executados nesta entrega:** testes da API (projetos, importação, mídia, layouts), validação de PPTX com conteúdo nativo e PDF de múltiplas páginas. **Não houve execução completa com voz real no Lenovo**, nem benchmark com GTX 1650. O build Docker e a experiência de navegação precisam ser validados na máquina de destino. Se o container acusar permissão em `studio-data`, confira `PUID`/`PGID` no `.env` e permissões de diretórios.

## Limitações conhecidas / próximo ciclo

- A IA **ainda não produz fotografias novas**: integração opcional de ComfyUI/Flux/SD na v1.4, com verificação humana de representações técnicas.
- Preview é **por slide salvo**, não drag-and-drop; o próprio usuário escolhe o bloco de layout e a imagem.
- A exportação PPTX preserva texto e formas editáveis, mas utiliza fontes disponíveis no ambiente; revise aparência em PowerPoint e LibreOffice.
- Diagramas têm fluxo simples da esquerda para a direita; diagramas complexos e editor gráfico ficam para o próximo ciclo.
- A renderização de slides está limitada aos 30 slides por projeto herdados da v1.2. Expandir esse limite exigirá atualização dos fluxos e testes de memória.
- O export de slides usa CPU e pode consumir recursos por alguns segundos em apresentações longas. Não execute múltiplas renderizações simultâneas.

## Segurança

Instalação destinada a **uso local pessoal**. Não publique a porta sem autenticação. O upload aceita apenas imagens raster validadas; não aceita SVG nem URLs externas arbitrárias. Para material técnico, valide os dados produzidos pela IA antes de publicar. Respeite direitos autorais de imagens e políticas de uso das vozes.
