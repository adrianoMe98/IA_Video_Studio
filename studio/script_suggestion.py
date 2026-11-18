"""Sugestões de narração em blocos curtos para o Ollama local."""
from __future__ import annotations

import json
import re
import time
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

WORDS_PER_MINUTE = 130
SCENES_PER_BLOCK = 3
MIN_TARGET_RATIO = .85
WORD = re.compile(r"\b\w+(?:[-'’]\w+)*\b")

STAGES = {
    1: ('Introduza o tema, explique o conceito principal com um exemplo e faça uma revisão breve.',),
    2: (
        'Apresente o objetivo, o contexto e os conceitos necessários para acompanhar a aula.',
        'Aplique os conceitos em um exemplo, discuta um erro comum e retome o objetivo no encerramento.',
    ),
    3: (
        'Apresente o objetivo e explique os conceitos fundamentais.',
        'Aprofunde os conceitos com um exemplo didático e mostre seu raciocínio passo a passo.',
        'Discuta um erro comum, proponha uma questão de revisão e encerre com uma síntese.',
    ),
}


class SceneDraft(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(default_factory=list, max_length=8)
    narration: str = Field(min_length=1, max_length=4000)


def word_count(scenes: list[SceneDraft]) -> int:
    return sum(len(WORD.findall(scene.narration)) for scene in scenes)


def source_context(project: dict) -> str:
    limit = min(450, 3300 // len(project['scenes']))
    scenes = []
    for scene in project['scenes']:
        topics = ' / '.join(scene['bullets'])
        scenes.append(f"- {scene['title'][:75]}: {topics[:limit // 3]} {scene['narration'][:limit]}")
    return '\n'.join([f"TEMA: {project['title']}", f"CONTEXTO: {project['description']}", *scenes])


def request_block(url: str, model: str, prompt: str, target: int, timeout: float) -> list:
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'keep_alive': '1m',
        'options': {'temperature': 0.3, 'num_predict': target * 3 + 240, 'num_ctx': 4096},
    }
    request = Request(url, json.dumps(payload).encode('utf-8'), {'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read(1_000_000))
    items = json.loads(result['response'])['scenes']
    if not isinstance(items, list):
        raise ValueError('Lista de cenas ausente.')
    return items[:SCENES_PER_BLOCK]


def valid_scenes(items: list, seen: set[str]) -> list[SceneDraft]:
    scenes = []
    for item in items:
        try:
            scene = SceneDraft.model_validate(item)
        except ValidationError:
            continue
        scene.title = scene.title.strip()
        scene.bullets = [bullet.strip()[:250] for bullet in scene.bullets if bullet.strip()]
        scene.narration = scene.narration.strip()
        words = WORD.findall(scene.narration.casefold())
        key = ' '.join(words)
        if scene.title and words and key not in seen:
            seen.add(key)
            scenes.append(scene)
    return scenes


def suggest_script(project: dict, duration_minutes: int, model: str, url: str) -> list[SceneDraft]:
    block_count = (duration_minutes + 2) // 2
    stages = STAGES[block_count]
    target = round(duration_minutes * WORDS_PER_MINUTE / block_count)
    per_scene = round(target / SCENES_PER_BLOCK)
    context = source_context(project)
    deadline = time.monotonic() + 240
    result: list[SceneDraft] = []
    for index, stage in enumerate(stages, 1):
        covered = ', '.join(scene.title for scene in result) or 'nenhum'
        prompt = (
            'Escreva um roteiro de videoaula em português do Brasil, com explicações para falar em voz alta. '
            f'Este é o bloco {index} de {block_count}. {stage}\n'
            f'Entregue {SCENES_PER_BLOCK} cenas, cada uma com cerca de {per_scene} palavras de narração '
            f'e cerca de {target} palavras de narração no bloco. '
            'Use parágrafos completos e exemplos diretamente ligados ao material. '
            'Evite frases de enchimento, repetições e fatos técnicos sem apoio no contexto. '
            'Se houver poucas referências, aprofunde com explicações conceituais e exemplos hipotéticos.\n'
            f'Títulos já abordados na aula: {covered}.\n'
            'Responda em JSON com a chave "scenes", uma lista de objetos com "title", '
            '"bullets" (2 a 4 tópicos curtos) e "narration" (texto corrido).\n\n'
            f'Material de referência:\n{context}'
        )
        best: list[SceneDraft] = []
        seen = {' '.join(WORD.findall(scene.narration.casefold())) for scene in result}
        for attempt in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Tempo de sugestão excedido.')
            instruction = prompt
            if attempt:
                instruction += (
                    f'\nRefaça o bloco completo. A tentativa anterior teve {word_count(best)} palavras válidas. '
                    f'Desenvolva o raciocínio de cada cena até cerca de {per_scene} palavras.'
                )
            try:
                items = request_block(url, model, instruction, target, remaining)
            except (ValueError, KeyError, TypeError):
                continue
            candidate = valid_scenes(items, seen.copy())
            if (min(word_count(candidate), target), len(candidate)) > (min(word_count(best), target), len(best)):
                best = candidate
            if len(best) == SCENES_PER_BLOCK and word_count(best) >= target * MIN_TARGET_RATIO:
                break
        if not best:
            raise ValueError('O modelo não retornou cenas válidas para o bloco.')
        result.extend(best)
    return result
