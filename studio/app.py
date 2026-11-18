"""API local do IA Video Studio 1.3 / Slide Studio."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import threading
import uuid
from urllib import error as urlerror, request as urlrequest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi.responses import Response
from slide_studio import LAYOUTS, THEMES, as_svg, build_slide, render_slides, suggest_layout

from core import VOICES, draft_from_text, export_project

BASE = Path(os.environ.get('STUDIO_DATA', '/data'))
PROJECTS = BASE / 'projects'
TRASH = BASE / 'trash'
VOICES_DIR = Path(os.environ.get('STUDIO_VOICES', str(BASE / 'voices')))
STATIC = Path(__file__).parent / 'static'
PROJECTS.mkdir(parents=True, exist_ok=True)
TRASH.mkdir(parents=True, exist_ok=True)

# Um job interrompido por reinicialização do container não é retomado silenciosamente.
for old_job in PROJECTS.glob('*/job.json'):
    try:
        saved = json.loads(old_job.read_text(encoding='utf-8'))
        if saved.get('status') in ('queued', 'running'):
            old_job.write_text(json.dumps({
                'status': 'error', 'message': 'Renderização interrompida pelo reinício do serviço. Inicie novamente.',
                'percent': 0,
            }, ensure_ascii=False), encoding='utf-8')
    except (OSError, ValueError):
        pass


app = FastAPI(title='IA Video Studio', version='1.3.0', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='render')
job_lock = threading.Lock()
running_projects: set[str] = set()


class RenameProject(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConfirmRemoval(BaseModel):
    confirm: str


class Scene(BaseModel):
    layout: str = 'auto'
    image: str = ''
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(default_factory=list, max_length=8)
    narration: str = Field(min_length=1, max_length=4000)


class Project(BaseModel):
    slide_theme: str = 'tech_blue'
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=400)
    voice: str = Field(default='faber')
    quality: str = Field(default='720')
    burn_subtitles: bool = False
    scenes: list[Scene] = Field(min_length=1, max_length=30)


def clean_project(project: Project, owner: Path | None = None) -> dict:
    data = project.model_dump()
    if data['voice'] not in VOICES:
        raise HTTPException(400, 'Voz não reconhecida.')
    if data['quality'] not in ('720', '1080'):
        raise HTTPException(400, 'Resolução inválida.')
    if data['slide_theme'] not in THEMES:
        raise HTTPException(400, 'Tema visual inválido.')
    for scene in data['scenes']:
        if scene['layout'] != 'auto' and scene['layout'] not in LAYOUTS:
            raise HTTPException(400, 'Bloco de slide inválido.')
        image = scene.get('image', '')
        if image and (not re.fullmatch(r'[0-9a-f]{24}\.png', image) or owner is None or not (owner / 'assets' / image).is_file()):
            raise HTTPException(400, 'A imagem deve pertencer à biblioteca deste projeto.')
        if not scene['narration'].strip() or not scene['title'].strip():
            raise HTTPException(400, 'Título e narração são obrigatórios.')
        scene['bullets'] = [x[:250] for x in scene['bullets'] if x.strip()]
    return data


def valid_pid(pid: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{12}', pid):
        raise HTTPException(404, 'Projeto não encontrado.')
    return pid


def directory(pid: str) -> Path:
    path = PROJECTS / valid_pid(pid)
    if path.is_symlink() or not path.is_dir() or not (path / 'project.json').is_file():
        raise HTTPException(404, 'Projeto não encontrado.')
    return path


def trash_directory(pid: str) -> Path:
    path = TRASH / valid_pid(pid)
    if path.is_symlink() or not path.is_dir() or not (path / 'project.json').is_file():
        raise HTTPException(404, 'Projeto não encontrado na lixeira.')
    return path


def ensure_not_rendering(pid: str) -> None:
    if pid in running_projects:
        raise HTTPException(409, 'Aguarde a conclusão da renderização antes de mover o projeto.')


def project_summary(folder: Path, deleted: bool = False) -> dict:
    data = load_json(folder / 'project.json')
    pid = folder.name
    result = {
        'id': pid, 'title': data['title'], 'description': data.get('description', ''),
        'scenes': len(data.get('scenes', [])), 'updated_at': data.get('updated_at', ''),
    }
    if deleted:
        meta = folder / 'trash.json'
        result['deleted_at'] = load_json(meta).get('deleted_at', '') if meta.is_file() else ''
    else:
        job = folder / 'job.json'
        result['job'] = load_json(job) if job.is_file() else None
    return result


def save_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def starter() -> dict:
    return {
        'title': 'GPON — Introdução',
        'description': 'Aula demonstrativa: arquitetura de redes ópticas passivas.',
        'voice': 'faber', 'quality': '720', 'burn_subtitles': False, 'slide_theme': 'tech_blue',
        'scenes': [
            {'layout': 'hero_cover', 'title': 'O que é GPON?',
             'bullets': ['Rede óptica passiva', 'OLT na operadora', 'ONT no assinante'],
             'narration': 'GPON é uma tecnologia de rede óptica passiva. Ela permite distribuir conectividade de uma OLT para múltiplos assinantes, utilizando divisores ópticos sem alimentação elétrica no trajeto.'},
            {'layout': 'diagram_slide', 'title': 'Elementos da rede',
             'bullets': ['OLT', 'Splitter óptico', 'Rede de distribuição', 'ONT ou ONU'],
             'narration': 'A OLT concentra e gerencia o acesso. O splitter divide o sinal óptico. Na extremidade da rede, a ONT realiza a conexão do cliente.'},
            {'layout': 'step_by_step', 'title': 'Planejamento da implantação',
             'bullets': ['Orçamento óptico', 'Dimensionamento', 'Identificação e documentação'],
             'narration': 'Para implantar uma rede GPON, precisamos analisar o orçamento óptico, dimensionar a rede e documentar corretamente todos os elementos de campo.'},
        ],
    }


@app.get('/', response_class=HTMLResponse)
def home():
    return (STATIC / 'index.html').read_text(encoding='utf-8')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '1.3.0', 'voices': {
        key: (VOICES_DIR / f'{name}.onnx').is_file() and (VOICES_DIR / f'{name}.onnx.json').is_file()
        for key, name in VOICES.items()
    }}


@app.get('/api/projects')
def list_projects(q: str = Query(default='', max_length=120)):
    needle = q.casefold().strip()
    result = []
    for folder in PROJECTS.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[0-9a-f]{12}', folder.name):
            continue
        try:
            item = project_summary(folder)
            if not needle or needle in (item['title'] + ' ' + item['description']).casefold():
                result.append(item)
        except (ValueError, KeyError, OSError, TypeError):
            pass
    return sorted(result, key=lambda x: x['updated_at'], reverse=True)


@app.get('/api/trash')
def list_trash(q: str = Query(default='', max_length=120)):
    needle = q.casefold().strip()
    result = []
    for folder in TRASH.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[0-9a-f]{12}', folder.name):
            continue
        try:
            item = project_summary(folder, deleted=True)
            if not needle or needle in (item['title'] + ' ' + item['description']).casefold():
                result.append(item)
        except (ValueError, KeyError, OSError, TypeError):
            pass
    return sorted(result, key=lambda x: x.get('deleted_at', ''), reverse=True)


@app.post('/api/projects', status_code=201)
def create_project(project: Project):
    data = clean_project(project)
    pid = uuid.uuid4().hex[:12]
    folder = PROJECTS / pid
    folder.mkdir(parents=True, exist_ok=False)
    data['id'] = pid
    data['updated_at'] = now()
    save_json(folder / 'project.json', data)
    return data


@app.get('/api/sample')
def sample():
    return starter()


@app.get('/api/projects/{pid}')
def get_project(pid: str):
    return load_json(directory(pid) / 'project.json')


@app.put('/api/projects/{pid}')
def update_project(pid: str, project: Project):
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        data = clean_project(project, folder)
        data['id'] = pid
        data['updated_at'] = now()
        save_json(folder / 'project.json', data)
    return data


@app.patch('/api/projects/{pid}/rename')
def rename_project(pid: str, request: RenameProject):
    title = request.title.strip()
    if not title:
        raise HTTPException(400, 'Informe um título válido.')
    with job_lock:
        folder = directory(pid)
        data = load_json(folder / 'project.json')
        data['title'] = title
        data['updated_at'] = now()
        save_json(folder / 'project.json', data)
    return data


@app.post('/api/projects/{pid}/duplicate', status_code=201)
def duplicate_project(pid: str):
    with job_lock:
        data = load_json(directory(pid) / 'project.json')
        original = Project.model_validate(data)
        copy = clean_project(original, directory(pid))
        copy['title'] = (data['title'][:112].rstrip() + ' (cópia)')[:120]
        # Não copiar job/build/exports: a cópia não é renderizada.
        copy['id'] = uuid.uuid4().hex[:12]
        copy['updated_at'] = now()
        target = PROJECTS / copy['id']
        target.mkdir(parents=False, exist_ok=False)
        source_assets = directory(pid) / 'assets'
        if source_assets.is_dir():
            shutil.copytree(source_assets, target / 'assets')
        save_json(target / 'project.json', copy)
    return copy


@app.delete('/api/projects/{pid}')
def move_to_trash(pid: str):
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        destination = TRASH / pid
        if destination.exists() or destination.is_symlink():
            raise HTTPException(409, 'Este ID já existe na lixeira. Contate o administrador.')
        save_json(folder / 'trash.json', {'deleted_at': now()})
        folder.rename(destination)  # Move atômico no mesmo volume (preserva arquivos exportados).
    return {'status': 'trashed', 'id': pid}


@app.post('/api/trash/{pid}/restore')
def restore_project(pid: str):
    with job_lock:
        folder = trash_directory(pid)
        destination = PROJECTS / pid
        if destination.exists() or destination.is_symlink():
            raise HTTPException(409, 'Já existe um projeto com este ID.')
        folder.rename(destination)
        meta = destination / 'trash.json'
        if meta.exists():
            meta.unlink()
        data = load_json(destination / 'project.json')
    return data


@app.delete('/api/trash/{pid}')
def permanently_delete(pid: str, request: ConfirmRemoval):
    if request.confirm != 'EXCLUIR':
        raise HTTPException(400, 'Digite EXCLUIR para confirmar a exclusão permanente.')
    with job_lock:
        folder = trash_directory(pid)
        # Apenas diretórios ID validado dentro da lixeira; nunca aceitar caminhos arbitrários.
        shutil.rmtree(folder)
    return {'status': 'deleted', 'id': pid}


# Slide Studio: prévia, recursos visuais e exportação independente da voz.
@app.get('/api/slide-studio/catalog')
def slide_catalog():
    return {'themes': [{'id': k, 'name': v['name']} for k,v in THEMES.items()],
            'layouts': [{'id': k, 'name': v} for k,v in LAYOUTS.items()]}


@app.get('/api/projects/{pid}/slides/{index}/preview')
def slide_preview(pid: str, index: int):
    folder = directory(pid)
    project = load_json(folder / 'project.json')
    if index < 0 or index >= len(project['scenes']):
        raise HTTPException(404, 'Slide não encontrado.')
    svg = as_svg(build_slide(project, project['scenes'][index], index, folder))
    return Response(content=svg, media_type='image/svg+xml', headers={
        'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    })


@app.get('/api/projects/{pid}/assets')
def list_assets(pid: str):
    folder = directory(pid) / 'assets'
    if not folder.is_dir(): return []
    return [{'id': path.name, 'bytes': path.stat().st_size} for path in sorted(folder.iterdir())
            if path.is_file() and not path.is_symlink() and re.fullmatch(r'[0-9a-f]{24}\.png', path.name)]


@app.get('/api/projects/{pid}/assets/{asset}')
def get_asset(pid: str, asset: str):
    if not re.fullmatch(r'[0-9a-f]{24}\.png', asset):
        raise HTTPException(404, 'Imagem inválida.')
    path = directory(pid) / 'assets' / asset
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, 'Imagem não encontrada.')
    return FileResponse(path, media_type='image/png', headers={'Cache-Control':'private, max-age=3600'})


@app.post('/api/projects/{pid}/assets', status_code=201)
async def upload_asset(pid: str, file: UploadFile = File(...)):
    # Aceita apenas imagem raster; reprocessa para PNG para descartar metadados.
    content = await file.read(6 * 1024 * 1024 + 1)
    if len(content) > 6 * 1024 * 1024:
        raise HTTPException(413, 'Imagem maior que 6 MB.')
    try:
        img = Image.open(io.BytesIO(content))
        if img.format not in ('PNG', 'JPEG', 'WEBP') or img.width > 4000 or img.height > 4000 or img.width*img.height > 12_000_000:
            raise ValueError('Imagem inválida ou muito grande.')
        img = ImageOps.exif_transpose(img).convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        if buffer.tell() > 8 * 1024 * 1024:
            raise ValueError('Imagem PNG resultante muito grande.')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(422, 'Envie PNG, JPG ou WebP válido, até 4000px.') from exc
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        assets = folder / 'assets'
        assets.mkdir(exist_ok=True)
        if len(list(assets.glob('*.png'))) >= 40:
            raise HTTPException(400, 'Limite de 40 imagens por projeto.')
        filename = uuid.uuid4().hex[:24] + '.png'
        (assets / filename).write_bytes(buffer.getvalue())
    return {'id':filename, 'bytes':buffer.tell()}


@app.post('/api/projects/{pid}/slides/auto-layout')
def auto_layout(pid: str):
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        project = load_json(folder / 'project.json')
        for i, scene in enumerate(project['scenes']):
            scene['layout'] = suggest_layout(scene['title'], scene.get('bullets', []), i, len(project['scenes']))
        project['updated_at'] = now()
        save_json(folder / 'project.json', project)
    return project


@app.post('/api/projects/{pid}/slides/export')
def export_only_slides(pid: str):
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        running_projects.add(pid)
        project = load_json(folder / 'project.json')
    try:
        result = render_slides(project, folder)
        return {'status':'done', 'slides':result['slides'], 'files':['slides.pdf','slides.pptx']}
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(500, str(exc)[:600]) from exc
    finally:
        with job_lock:
            running_projects.discard(pid)


@app.post('/api/projects/import', status_code=201)
async def import_document(file: UploadFile = File(...)):
    filename = Path(file.filename or '').name
    ext = Path(filename).suffix.lower()
    if ext not in {'.pdf', '.md', '.txt'}:
        raise HTTPException(400, 'Formatos permitidos: PDF, Markdown ou TXT.')
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Limite de 5 MB excedido.')
    try:
        if ext == '.pdf':
            reader = PdfReader(io.BytesIO(content))
            if len(reader.pages) > 30:
                raise ValueError('PDF muito longo: máximo de 30 páginas para importação.')
            text = '\f'.join(p.extract_text() or '' for p in reader.pages)
        else:
            text = content.decode('utf-8-sig')
        title = Path(filename).stem[:110].replace('_', ' ').strip() or 'Aula importada'
        scenes = draft_from_text(text, title)
    except Exception as exc:
        raise HTTPException(422, f'Falha ao ler o documento: {str(exc)[:300]}') from exc
    payload = Project(title=title, description='Rascunho importado; revise antes de renderizar.', scenes=scenes)
    return create_project(payload)


def run_render(pid: str, project: dict) -> None:
    folder = PROJECTS / pid
    def update(message: str, percent: int):
        save_json(folder / 'job.json', {'status': 'running', 'message': message, 'percent': percent})
    try:
        result = export_project(project, folder, VOICES_DIR, update)
        save_json(folder / 'job.json', {'status': 'done', 'message': 'Exportação concluída', 'percent': 100, 'result': result})
    except Exception as exc:
        save_json(folder / 'job.json', {'status': 'error', 'message': str(exc)[:1600], 'percent': 0})
    finally:
        with job_lock:
            running_projects.discard(pid)


@app.post('/api/projects/{pid}/suggest')
def suggest(pid: str, project: Project):
    """Sugestão facultativa de roteiro pelo Ollama local, nunca publicada sem revisão."""
    directory(pid)
    p = clean_project(project)
    lines = [f'TEMA: {p["title"]}', f'CONTEXTO: {p["description"]}']
    for slide in p['scenes'][:8]:
        lines.append(f'- {slide["title"]}: {slide["narration"][:450]}')
    prompt = (
        'Você cria roteiros para videoaulas técnicas em português do Brasil. '
        'Use o conteúdo fornecido como referência, sem inventar normas, especificações, equipamentos ou comandos. '
        'Retorne APENAS um JSON com propriedade "scenes": lista de 3 a 5 itens. '
        'Cada item deve conter "title" (título curto), "bullets" (2 a 4 tópicos curtos) '
        'e "narration" (3 a 5 frases didáticas em português). '
        'Caso faltem fatos, mantenha explicações introdutórias genéricas. '
        'Os textos serão revisados por um especialista.\n\n' + '\n'.join(lines)
    )
    payload = json.dumps({
        'model': os.environ.get('OLLAMA_MODEL', 'qwen2.5:1.5b'),
        'prompt': prompt, 'stream': False, 'format': 'json', 'keep_alive': 0,
        'options': {'temperature': 0.3, 'num_predict': 1600, 'num_ctx': 4096},
    }).encode('utf-8')
    url = os.environ.get('OLLAMA_URL', 'http://ollama:11434').rstrip('/') + '/api/generate'
    try:
        req = urlrequest.Request(url, payload, headers={'Content-Type':'application/json'}, method='POST')
        with urlrequest.urlopen(req, timeout=240) as resp:
            result = json.loads(resp.read(1_000_000))
        suggestion = json.loads(result['response'])
        scenes = [Scene.model_validate(item).model_dump() for item in suggestion.get('scenes', [])[:6]]
        if not scenes:
            raise ValueError('O modelo não retornou cenas válidas.')
        return {'scenes': scenes, 'model': os.environ.get('OLLAMA_MODEL', 'qwen2.5:1.5b')}
    except (urlerror.URLError, TimeoutError) as exc:
        raise HTTPException(503, 'Ollama indisponível. Use ./scripts/iniciar-roteiro-ia.sh para ativar.') from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, 'Não foi possível interpretar as sugestões. Tente novamente.') from exc


@app.post('/api/projects/{pid}/render', status_code=202)
def render(pid: str):
    with job_lock:
        folder = directory(pid)
        project = load_json(folder / 'project.json')
        if pid in running_projects:
            raise HTTPException(409, 'Este projeto já está em renderização.')
        running_projects.add(pid)
        save_json(folder / 'job.json', {'status': 'queued', 'message': 'Na fila de renderização', 'percent': 0})
    executor.submit(run_render, pid, project)
    return {'status': 'queued', 'id': pid}


@app.get('/api/projects/{pid}/job')
def get_job(pid: str):
    folder = directory(pid)
    path = folder / 'job.json'
    return load_json(path) if path.is_file() else {'status': 'none', 'message': 'Ainda não renderizado', 'percent': 0}


FILES = {'video.mp4': 'video/mp4', 'video_legendas.mp4': 'video/mp4',
         'slides.pdf': 'application/pdf', 'slides.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
         'slides.md': 'text/markdown', 'legendas.srt': 'application/x-subrip'}


@app.get('/api/projects/{pid}/files/{filename}')
def download(pid: str, filename: str):
    folder = directory(pid)
    if filename not in FILES:
        raise HTTPException(404, 'Arquivo não permitido.')
    path = folder / 'exports' / filename
    if not path.is_file():
        raise HTTPException(404, 'Arquivo ainda não gerado.')
    return FileResponse(path, media_type=FILES[filename], filename=filename if filename != 'video.mp4' else None)
