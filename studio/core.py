"""Núcleo do IA Video Studio: artefatos, narração e sincronização por frases.

Processa dados locais apenas. Não executa texto de usuário em shell.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Callable

VOICES = {
    'faber': 'pt_BR-faber-medium',
    'edresson': 'pt_BR-edresson-low',
}


def text_sentences(text: str) -> list[str]:
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    result = re.split(r'(?<=[.!?])\s+', text)
    parts = []
    for item in result:
        if len(item) <= 150:
            parts.append(item)
            continue
        # Dividir preferencialmente em vírgulas; não forçar corte em palavras.
        pieces = re.split(r'(?<=,)\s+', item)
        buffer = ''
        for piece in pieces:
            if buffer and len(buffer) + len(piece) > 150:
                parts.append(buffer.strip())
                buffer = piece
            else:
                buffer = f'{buffer} {piece}'.strip()
        if buffer:
            parts.append(buffer.strip())
    return [x for x in parts if x]


def timestamp_srt(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def write_srt(cues: list[tuple[float, float, str]], target: Path) -> None:
    out = []
    for idx, (a, b, text) in enumerate(cues, 1):
        out.append(f'{idx}\n{timestamp_srt(a)} --> {timestamp_srt(b)}\n{text}\n')
    target.write_text('\n'.join(out) + '\n', encoding='utf-8')


def escape_marp(text: str) -> str:
    # Markdown do usuário deve ser texto, não instruções Marp/HTML.
    escaped = html.escape(text, quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', escaped).replace('\n', ' ')


def make_deck(project: dict) -> str:
    slides = project['scenes']
    result = [
        '---',
        'marp: true',
        'theme: default',
        'size: 16:9',
        'paginate: true',
        'style: |',
        '  section { font-family: "Noto Sans", "DejaVu Sans", sans-serif; background: #101a30; color: #e8f1ff; padding: 70px 85px; }',
        '  section h1 { color: #5fd6ed; font-size: 1.75em; margin-bottom: 30px; }',
        '  section li { margin-bottom: 18px; font-size: 0.89em; line-height: 1.4; }',
        '  section::after { color: #9db3cd; }',
        '---',
    ]
    for i, scene in enumerate(slides):
        if i:
            result.append('---')
        result += [f'# {escape_marp(scene["title"])}', '']
        bullets = scene.get('bullets', [])
        if bullets:
            result.extend('- ' + escape_marp(x) for x in bullets if x.strip())
        else:
            result.append(escape_marp(scene['narration'][:180]))
        result.append('')
    return '\n'.join(result)


def run(command: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=3600,
        check=False,
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip()[-2200:]
        raise RuntimeError(f'{command[0]} retornou código {result.returncode}: {details}')
    return result.stdout


def ffprobe_duration(file: Path) -> float:
    data = run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(file),
    ])
    value = float(data.strip())
    if value <= 0:
        raise RuntimeError(f'Áudio com duração inválida: {file.name}')
    return value


def concat_manifest(paths: list[Path], manifest: Path) -> None:
    # Escape aspas simples conforme especificação do concat demuxer.
    def quote(path: Path) -> str:
        return str(path.resolve()).replace("'", "'\\''")
    manifest.write_text(
        ''.join("file '" + quote(file) + "'\n" for file in paths),
        encoding='utf-8',
    )


def export_project(project: dict, project_dir: Path, voices_dir: Path,
                   progress: Callable[[str, int], None]) -> dict:
    voice_key = project['voice']
    if voice_key not in VOICES:
        raise RuntimeError('Voz não reconhecida.')
    model = voices_dir / (VOICES[voice_key] + '.onnx')
    config = voices_dir / (VOICES[voice_key] + '.onnx.json')
    if not model.is_file() or not config.is_file():
        raise RuntimeError(f'Voz {voice_key} não baixada. Execute ./scripts/baixar-voz.sh.')

    exports = project_dir / 'exports'
    work = project_dir / 'build'
    # Remover somente conteúdo gerado. Preservar JSON do projeto.
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)
    frame_dir = work / 'frames'
    frame_dir.mkdir(exist_ok=True)
    audio_dir = work / 'audio'
    audio_dir.mkdir(exist_ok=True)

    # v1.3 — um único motor de slides alimenta prévia, PDF, PPTX e vídeo.
    from slide_studio import render_slides
    progress('Criando slides profissionais com Slide Studio', 8)
    package = render_slides(project, project_dir, lambda message, percent: progress(message, 8 + round(percent * 0.20)))
    images = package['frames']
    deck = work / 'deck.md'
    deck.write_text(make_deck(project), encoding='utf-8')
    shutil.copy2(deck, exports / 'slides.md')

    progress('Carregando a voz PT-BR na memória', 30)
    from piper import PiperVoice  # opcional no host; instalado na imagem Docker
    voice_engine = PiperVoice.load(str(model))
    progress('Gerando narração em português', 31)
    cues: list[tuple[float, float, str]] = []
    scene_audio: list[tuple[Path, float]] = []
    clock = 0.0
    for scene_idx, scene in enumerate(project['scenes']):
        segments = text_sentences(scene['narration'])
        if not segments:
            raise ValueError('A narração de uma das cenas está vazia.')
        wavs = []
        slide_duration = 0.0
        for seg_idx, sentence in enumerate(segments):
            target = audio_dir / f'{scene_idx:03}_{seg_idx:03}.wav'
            with wave.open(str(target), 'wb') as wav_file:
                voice_engine.synthesize_wav(sentence, wav_file)
            duration = ffprobe_duration(target)
            cues.append((clock, clock + duration, sentence))
            clock += duration
            slide_duration += duration
            wavs.append(target)
        manifest = audio_dir / f'concat_{scene_idx:03}.txt'
        concat_manifest(wavs, manifest)
        together = audio_dir / f'scene_{scene_idx:03}.wav'
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
             '-f', 'concat', '-safe', '0', '-i', str(manifest),
             '-c:a', 'pcm_s16le', str(together)])
        scene_audio.append((together, slide_duration))
        progress(f'Narração {scene_idx + 1}/{len(project["scenes"])}', 30 + round(35 * (scene_idx + 1) / len(project['scenes'])))

    write_srt(cues, exports / 'legendas.srt')
    progress('Montando vídeo e legendas com FFmpeg', 70)
    scenes_mp4 = []
    width, height = (1920, 1080) if project.get('quality') == '1080' else (1280, 720)
    for idx, (audio, duration) in enumerate(scene_audio):
        output = work / f'scene_{idx:03}.mp4'
        run([
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-loop', '1', '-framerate', '24', '-i', str(images[idx]),
            '-i', str(audio),
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
            '-t', f'{duration:.3f}', '-c:v', 'libx264', '-preset', 'veryfast',
            '-crf', '24', '-r', '24', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output),
        ])
        scenes_mp4.append(output)
        progress(f'Cena {idx + 1}/{len(scene_audio)}', 70 + round(22 * (idx + 1) / len(scene_audio)))
    manifest = work / 'videos.txt'
    concat_manifest(scenes_mp4, manifest)
    base_video = work / 'video_base.mp4'
    video = exports / 'video.mp4'
    # Concat sem re-encode; MP4 final recebe legenda selecionável (mov_text).
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
         '-f', 'concat', '-safe', '0', '-i', str(manifest), '-c', 'copy',
         '-movflags', '+faststart', str(base_video)])
    run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
         '-i', str(base_video), '-i', str(exports / 'legendas.srt'),
         '-map', '0:v:0', '-map', '0:a:0', '-map', '1:0',
         '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text',
         '-metadata:s:s:0', 'language=por', '-movflags', '+faststart',
         str(video)])
    if project.get('burn_subtitles', False):
        progress('Aplicando legendas no vídeo', 94)
        burned = exports / 'video_legendas.mp4'
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
             '-i', 'video.mp4', '-vf', 'subtitles=legendas.srt:force_style=FontName=DejaVu Sans',
             '-map', '0:v:0', '-map', '0:a:0', '-sn',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24',
             '-c:a', 'copy', '-movflags', '+faststart', 'video_legendas.mp4'], cwd=exports)
        # Ambos são mantidos para facilitar reedição.
        final_name = burned.name
    else:
        final_name = video.name
    progress('Concluído', 100)
    return {'video': final_name, 'duration_seconds': round(clock, 1), 'slides': len(images)}


def draft_from_text(raw: str, title: str) -> list[dict]:
    """Heurística transparente: não inventa conteúdo nem invoca LLM."""
    chunks = [x.strip() for x in re.split(r'\n\s*---\s*\n|\f', raw) if x.strip()]
    if len(chunks) == 1:
        paras = [x.strip() for x in re.split(r'\n\s*\n', raw) if x.strip()]
        chunks = ['\n'.join(paras[i:i + 2]) for i in range(0, min(len(paras), 20), 2)]
    scenes = []
    for i, chunk in enumerate(chunks[:12]):
        lines = [re.sub(r'^\s*#+\s*', '', x.strip()) for x in chunk.splitlines() if x.strip()]
        if not lines:
            continue
        candidate = lines[0][:75] if len(lines[0]) < 90 else f'{title} — Parte {i + 1}'
        bullets = [x.lstrip('•-* ').strip()[:160] for x in lines[1:5] if x.strip()]
        if not bullets:
            bullets = [chunk[:140].replace('\n', ' ')]
        scenes.append({'title': candidate, 'bullets': bullets, 'narration': re.sub(r'\s+', ' ', chunk)[:2400]})
    if not scenes:
        raise ValueError('Não encontramos texto legível no documento.')
    return scenes
