"""Conector opcional para geração local de imagens estáticas no ComfyUI."""
from __future__ import annotations

import json
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from media import MAX_UPLOAD

WIDTH = 512
HEIGHT = 512
STEPS = 20
CFG = 7
REVISION = 'sd15-1'


def settings():
    url = os.environ.get('COMFY_IMAGE_URL', '').strip().rstrip('/')
    model = os.environ.get('COMFY_IMAGE_CHECKPOINT', '').strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if (parsed.scheme == 'http' and parsed.hostname and model and
            not (parsed.username or parsed.password or parsed.query or parsed.fragment)):
        return url, model
    return None


def _request(url, path, payload=None, limit=1_000_000):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url + path, data=body, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=12) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Resposta do gerador acima do limite.')
        return data


def workflow(model, prompt, seed, job_id):
    return {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': model}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {
            'text': 'watermark, illegible text, artifacts', 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {
            'width': WIDTH, 'height': HEIGHT, 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {
            'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
            'latent_image': ['4', 0], 'seed': seed, 'steps': STEPS, 'cfg': CFG,
            'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {
            'images': ['6', 0], 'filename_prefix': 'studio-educativo/' + job_id}},
    }


def submit(url, model, prompt, job_id):
    queue = json.loads(_request(url, '/queue'))
    if queue['queue_running'] or queue['queue_pending']:
        raise ValueError('ComfyUI ocupado. Aguarde os jobs atuais antes de gerar uma imagem.')
    seed = secrets.randbits(32)
    result = json.loads(_request(url, '/prompt', {'prompt': workflow(model, prompt, seed, job_id)}))
    return str(UUID(result['prompt_id'])), seed


def wait_image(url, prompt_id, active):
    deadline = time.monotonic() + 600
    while active() and time.monotonic() < deadline:
        history = json.loads(_request(url, '/history/' + prompt_id)).get(prompt_id)
        if history:
            images = history.get('outputs', {}).get('7', {}).get('images', [])
            if not images:
                raise ValueError('ComfyUI concluiu sem uma imagem. Confira o modelo e a memória disponível.')
            image = images[0]
            if image.get('type') != 'output':
                raise ValueError('Saída inesperada do ComfyUI.')
            query = urlencode({key: image.get(key, '') for key in ('filename', 'subfolder', 'type')})
            return _request(url, '/view?' + query, limit=MAX_UPLOAD)
        time.sleep(1)
    if active():
        raise TimeoutError('Tempo de geração excedido.')
    return None
