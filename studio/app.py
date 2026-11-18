"""API local do IA Video Studio."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from urllib import error as urlerror, request as urlrequest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints
from pypdf import PdfReader
from PIL import Image

import image_generation
from core import VOICES, draft_from_text, export_project
from diagrams import Diagram
from media import MAX_UPLOAD, add_asset, asset_info, asset_path, normalize_image
from slide_studio import LAYOUTS, THEMES, as_svg, build_slide, render_slides, suggest_layout

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


app = FastAPI(title='IA Video Studio', version='1.4.0', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='render')
job_lock = threading.Lock()
running_projects: set[str] = set()
image_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='image')
image_slot = threading.Lock()
IMAGE_JOB = 'image-job.json'
IMAGE_DRAFT = 'image-draft.png'

class RenameProject(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConfirmRemoval(BaseModel):
    confirm: str


class Scene(BaseModel):
    layout: str = 'auto'
    image: str = ''
    diagram: Diagram | None = None
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
    data = project.model_dump(exclude_none=True)
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
        if image and (owner is None or asset_path(owner, image) is None):
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


for old_job in PROJECTS.glob(f'*/{IMAGE_JOB}'):
    try:
        saved = json.loads(old_job.read_text(encoding='utf-8'))
        if saved.get('status') in ('queued', 'running'):
            saved.update(status='error', message='Geração interrompida pelo reinício.')
            save_json(old_job, saved)
    except (OSError, ValueError):
        pass


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
    return {'status': 'ok', 'version': app.version, 'voices': {
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
        if read_image_job(folder)['status'] in ('queued', 'running'):
            raise HTTPException(409, 'Aguarde ou descarte a geração de imagem.')
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


class AssetMetadata(BaseModel):
    title: str = Field(default='', max_length=100)
    alt: str = Field(default='', max_length=200)
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]] = Field(
        default_factory=list, max_length=10)
    license: str = Field(default='', max_length=120)


@app.get('/api/projects/{pid}/assets')
def list_assets(pid: str):
    with job_lock:
        project = directory(pid)
        return [asset_info(path) for item in sorted((project / 'assets').glob('*.png'))
                if (path := asset_path(project, item.name))]


def existing_asset(pid: str, name: str) -> Path:
    path = asset_path(directory(pid), name)
    if path is None:
        raise HTTPException(404, 'Imagem não encontrada.')
    return path


@app.get('/api/projects/{pid}/assets/{asset}')
def get_asset(pid: str, asset: str):
    return FileResponse(existing_asset(pid, asset), media_type='image/png',
                        headers={'Cache-Control': 'private, max-age=3600'})


@app.post('/api/projects/{pid}/assets', status_code=201)
async def upload_asset(pid: str, file: UploadFile = File(...)):
    try:
        png = normalize_image(await file.read(MAX_UPLOAD + 1))
    except OverflowError as exc:
        raise HTTPException(413, 'Imagem maior que 6 MB.') from exc
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, 'Envie PNG, JPG ou WebP válido, até 4000px.') from exc
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        try:
            return add_asset(folder, uuid.uuid4().hex[:24] + '.png', png,
                             {'origin': 'upload', 'created_at': now()}, save_json)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc


@app.patch('/api/projects/{pid}/assets/{asset}')
def edit_asset(pid: str, asset: str, metadata: AssetMetadata):
    with job_lock:
        ensure_not_rendering(pid)
        path = existing_asset(pid, asset)
        info = asset_info(path)
        info.pop('id')
        info.pop('bytes')
        details = metadata.model_dump(exclude_unset=True)
        if 'tags' in details:
            details['tags'] = list(dict.fromkeys(tag for tag in metadata.tags if tag))
        save_json(path.with_suffix('.json'), info | details)
        return asset_info(path)


@app.delete('/api/projects/{pid}/assets/{asset}')
def delete_asset(pid: str, asset: str):
    with job_lock:
        ensure_not_rendering(pid)
        path = existing_asset(pid, asset)
        project = load_json(directory(pid) / 'project.json')
        scenes = [index for index, scene in enumerate(project['scenes'], 1) if scene.get('image') == asset]
        if scenes:
            raise HTTPException(409, 'Desvincule a imagem dos slides ' + ', '.join(map(str, scenes)) + '.')
        path.unlink()
        path.with_suffix('.json').unlink(missing_ok=True)
    return {'status': 'deleted'}


class ImagePrompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)


def read_image_job(folder: Path):
    path = folder / IMAGE_JOB
    return load_json(path) if path.is_file() else {'status': 'none'}


def matching_image_job(folder: Path, job_id: str):
    job = read_image_job(folder)
    if job.get('id') != job_id:
        raise HTTPException(404, 'Geração não encontrada.')
    return job


def run_image_job(pid, job_id, url, model, prompt):
    folder = PROJECTS / pid
    path = folder / IMAGE_JOB

    def active():
        return read_image_job(folder).get('status') == 'running'

    try:
        with job_lock:
            job = matching_image_job(folder, job_id)
            if job['status'] != 'queued':
                return
            save_json(path, job | {'status': 'running'})
        prompt_id, seed = image_generation.submit(url, model, prompt, job_id)
        with job_lock:
            job = matching_image_job(folder, job_id)
            save_json(path, job | {'prompt_id': prompt_id, 'seed': seed})
        result = image_generation.wait_image(url, prompt_id, active)
        if result is None:
            return
        png = normalize_image(result)
        with job_lock:
            if active():
                (folder / IMAGE_DRAFT).write_bytes(png)
                job = matching_image_job(folder, job_id)
                save_json(path, job | {'status': 'ready'})
    except (OSError, KeyError, TypeError, ValueError, HTTPException, Image.DecompressionBombError) as exc:
        with job_lock:
            if path.is_file() and active():
                message = str(exc)[:250] if isinstance(exc, (ValueError, TimeoutError)) else (
                    'Falha no ComfyUI. Confira disponibilidade, checkpoint e memória.')
                save_json(path, read_image_job(folder) | {'status': 'error', 'message': message})
    finally:
        image_slot.release()


@app.get('/api/image-generation')
def image_capability():
    return {'enabled': image_generation.settings() is not None}


@app.get('/api/projects/{pid}/image-job')
def get_image_job(pid: str):
    return read_image_job(directory(pid))


@app.post('/api/projects/{pid}/image-job', status_code=202)
def start_image_job(pid: str, request: ImagePrompt):
    config = image_generation.settings()
    if config is None:
        raise HTTPException(503, 'Geração de imagens desativada.')
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(400, 'Escreva o prompt da ilustração.')
    with job_lock:
        folder = directory(pid)
        if read_image_job(folder)['status'] == 'ready':
            raise HTTPException(409, 'Aprove ou descarte a imagem pendente.')
        if not image_slot.acquire(blocking=False):
            raise HTTPException(409, 'Já existe uma geração de imagem em andamento.')
        try:
            (folder / IMAGE_DRAFT).unlink(missing_ok=True)
            job = {'id': uuid.uuid4().hex[:24], 'status': 'queued', 'prompt': prompt,
                   'model': config[1], 'created_at': now(), 'workflow': image_generation.REVISION,
                   'model_revision': os.environ.get('COMFY_IMAGE_MODEL_REVISION', '').strip()[:160]}
            save_json(folder / IMAGE_JOB, job)
            image_executor.submit(run_image_job, pid, job['id'], *config, prompt)
        except Exception:
            image_slot.release()
            raise
    return job


@app.get('/api/projects/{pid}/image-job/{job_id}/preview')
def preview_image_job(pid: str, job_id: str):
    with job_lock:
        folder = directory(pid)
        draft = folder / IMAGE_DRAFT
        if matching_image_job(folder, job_id)['status'] != 'ready' or not draft.is_file():
            raise HTTPException(404, 'Imagem ainda indisponível.')
        preview = draft.read_bytes()
    return Response(preview, media_type='image/png', headers={'Cache-Control': 'no-store'})


@app.post('/api/projects/{pid}/image-job/{job_id}/approve')
def approve_image_job(pid: str, job_id: str):
    with job_lock:
        folder = directory(pid)
        job = matching_image_job(folder, job_id)
        name = job_id + '.png'
        if job['status'] == 'approved':
            return asset_info(existing_asset(pid, name))
        if job['status'] != 'ready':
            raise HTTPException(409, 'A imagem ainda não pode ser aprovada.')
        ensure_not_rendering(pid)
        metadata = {
            'origin': 'ai', 'title': 'Ilustração educativa', 'created_at': job['created_at'],
            'prompt': job['prompt'], 'model': job['model'], 'seed': job['seed'],
            'model_revision': job.get('model_revision', ''),
            'workflow': job['workflow'], 'width': image_generation.WIDTH,
            'height': image_generation.HEIGHT, 'steps': image_generation.STEPS,
            'cfg': image_generation.CFG, 'sampler': 'euler',
        }
        try:
            asset = add_asset(folder, name, (folder / IMAGE_DRAFT).read_bytes(), metadata, save_json)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        save_json(folder / IMAGE_JOB, job | {'status': 'approved'})
        (folder / IMAGE_DRAFT).unlink(missing_ok=True)
        return asset


@app.delete('/api/projects/{pid}/image-job/{job_id}')
def discard_image_job(pid: str, job_id: str):
    with job_lock:
        folder = directory(pid)
        job = matching_image_job(folder, job_id)
        if job['status'] not in ('queued', 'running', 'ready', 'cancelled'):
            raise HTTPException(409, 'Esta geração não pode ser descartada.')
        job['status'] = 'cancelled'
        save_json(folder / IMAGE_JOB, job)
        (folder / IMAGE_DRAFT).unlink(missing_ok=True)
    return job


@app.post('/api/projects/{pid}/slides/auto-layout')
def auto_layout(pid: str):
    with job_lock:
        folder = directory(pid)
        ensure_not_rendering(pid)
        project = load_json(folder / 'project.json')
        for i, scene in enumerate(project['scenes']):
            scene['layout'] = ('diagram_slide' if scene.get('diagram') else
                               suggest_layout(scene['title'], scene.get('bullets', []), i, len(project['scenes'])))
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
            reader = PdfReader(BytesIO(content))
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
    p = clean_project(project, directory(pid))
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
