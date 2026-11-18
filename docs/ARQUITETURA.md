# IA Video Studio v1.3 — arquitetura funcional e técnica

## Visão geral

Núcleo da plataforma: projeto (`project.json`) → cenas (título + tópicos + narração + bloco) → modelo de layout declarativo (formas/textos/imagens) → pré-visualização SVG, imagens PNG, PDF e apresentação PPTX com objetos editáveis. O motor audiovisual usa as imagens PNG para compor cenas com Piper e FFmpeg. A compatibilidade de dados é preservada: propriedades novas têm defaults.

```text
Browser HTML/JS
  | criação, edição, blocos, mídia, prévia
  v
FastAPI (app.py) --- diretórios studio-data/projects/<ID>/
  |                                      \--- assets/*.png (biblioteca privada por projeto)
  +--- Slide Studio (slide_studio.py) --> layout_plan JSON
       | SVG instantâneo (prévia)
       | CairoSVG --> PNG e PDF
       | PptxGenJS --> PPTX com textos e formas nativas
       +--- core.py -> Piper TTS -> FFmpeg -> MP4 + SRT
  +--- Ollama (opcional, sem acesso externo por padrão)
  +--- ComfyUI/Wan (serviço GPU opcional)
```

## Blocos e temas

Blocos são `hero_cover`, `learning_objectives`, `concept_explainer`, `two_column_explanation`, `comparison_table`, `step_by_step`, `diagram_slide`, `practical_example`, `quiz_slide`, `summary_slide`. Cada bloco aplica regras de distribuição fixas em canvas 1280×720. Temas são `tech_blue`, `corporate_clean`, `creative_course`, `minimal_focus`; definem cores do canvas, painéis, textos e destaques. O campo `layout=auto` utiliza classificação heurística de título e tópicos. Nenhum fato é criado pelo classificador.

Dados novos em `project.json`:

```json
{
  "slide_theme": "tech_blue",
  "scenes": [
    {
      "title": "Arquitetura GPON",
      "layout": "diagram_slide",
      "bullets": ["OLT", "Splitter", "ONT"],
      "image": "",
      "narration": "Na arquitetura GPON a OLT..."
    }
  ]
}
```

`image` é um nome de asset no formato `<24 dígitos hexadecimais>.png`, vinculado ao projeto. Não são permitidos caminhos arbitrários nem URL externa de imagem.

## Rotas HTTP adicionadas

| Método e rota | Função |
|---|---|
| `GET /api/slide-studio/catalog` | Blocos e temas disponíveis |
| `GET /api/projects/{id}/slides/{index}/preview` | SVG do slide, indexado a partir de 0 |
| `POST /api/projects/{id}/slides/auto-layout` | Salva classificação heurística dos slides |
| `POST /api/projects/{id}/slides/export` | PDF/PPTX mesmo sem voz Piper |
| `GET /api/projects/{id}/assets` | Lista as imagens do projeto |
| `POST /api/projects/{id}/assets` | Upload multipart; PNG/JPG/WebP até 6 MB |
| `GET /api/projects/{id}/assets/{asset}` | Devolve PNG validado |

Rotas CRUD, importação, sugestões Ollama, renderização, job, downloads e lixeira são preservadas da v1.2.

## Fluxo do usuário

1. Criar ou abrir projeto; projeto antigo obtém tema padrão `tech_blue`.
2. Escolher um tema. Criar/editar cenas e narração.
3. Escolher um bloco por cena ou acionar “Organizar slides”.
4. Adicionar PNG/JPG/WebP próprio e vincular a cada cena quando necessário.
5. Salvar e visualizar cena; repetir até aprovar os slides.
6. Exportar só apresentação ou gerar vídeo completo.
7. Artefatos e dados persistem no volume `/data`.

## Confiabilidade e segurança

- Escrita atômica de `project.json` via arquivo temporário e `replace`.
- IDs dos projetos validados por regex; imagens são regravadas em PNG e limitadas por tipo, tamanho e dimensões.
- Exclusão bloqueada durante renderização; lixeira guarda o diretório inteiro.
- Código do usuário nunca é interpretado como HTML ou comando de shell; textos são escapados no SVG.
- Sem autenticação: usar bind `127.0.0.1` e túnel SSH/proxy autenticado para acesso remoto.

## Roadmap técnico

- **v1.4:** editor de diagramas mais expressivo (Mermaid/D2), conectores opcionais para geração local de imagens (SD 1.5/ComfyUI) e galeria aprovada, com trilha de procedência da imagem.
- **v1.5:** prévia interativa drag-and-drop, rearranjo visual, biblioteca global reutilizável, animações sutis para videoaulas.
- **v1.6:** integração de narrador/avatar, seleção de cenas para o Studio Cinema.
- **v2.0:** motor audiovisual unificado, timeline, filas e processamento local/remoto sem mudar o formato de projeto.

## Limites honestos

Não é um gerador de apresentações com imagens fotográficas inventadas automaticamente nesta versão. A classificação de layouts é heurística, não uma IA de design treinada. PDF deriva do SVG e PPTX deriva dos mesmos blocos, portanto pode haver pequenas diferenças visuais de renderização entre fontes instaladas. Slide Studio não é um editor gráfico livre/drag-and-drop ainda.
