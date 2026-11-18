"""Slide Studio v1.3 — layout declarativo, SVG preview, PDF, PNG e PPTX.

Sem URLs externas, HTML de usuário ou comandos shell. Elementos são textos,
formas e imagens PNG de uma biblioteca local validada.
"""
from __future__ import annotations

import base64
import io
import json
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from PIL import Image, ImageFont, ImageOps

W, H = 1280, 720
LAYOUTS = {
    'hero_cover': 'Capa de abertura',
    'learning_objectives': 'Objetivos da aula',
    'concept_explainer': 'Explicação de conceito',
    'two_column_explanation': 'Texto + imagem',
    'comparison_table': 'Comparação',
    'step_by_step': 'Passo a passo',
    'diagram_slide': 'Diagrama / topologia',
    'practical_example': 'Exemplo prático',
    'quiz_slide': 'Pergunta / exercício',
    'summary_slide': 'Resumo da aula',
}
THEMES = {
    'tech_blue': {'name': 'Tech Blue', 'bg': '#081629', 'panel': '#122B44', 'soft': '#1B3850', 'fg': '#F2F8FF', 'muted': '#A8C2D7', 'accent': '#3ADAE4', 'secondary': '#7A96FF', 'outline': '#36556E'},
    'corporate_clean': {'name': 'Corporate Clean', 'bg': '#F6F8FC', 'panel': '#FFFFFF', 'soft': '#E7EEF9', 'fg': '#17253B', 'muted': '#566982', 'accent': '#176BBD', 'secondary': '#1292A0', 'outline': '#CBD7E4'},
    'creative_course': {'name': 'Creative Course', 'bg': '#21142B', 'panel': '#362045', 'soft': '#4C2B53', 'fg': '#FFF6F7', 'muted': '#DAC5D9', 'accent': '#FFAF70', 'secondary': '#F37DA6', 'outline': '#714C69'},
    'minimal_focus': {'name': 'Minimal Focus', 'bg': '#F9F9F6', 'panel': '#FFFFFF', 'soft': '#E9EBE5', 'fg': '#1E2927', 'muted': '#58655E', 'accent': '#167A69', 'secondary': '#C78C38', 'outline': '#CBD4CD'},
}
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def _font(size: int, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _wrap(text: str, size: int, width: int, max_lines: int, bold=False) -> list[str]:
    """Pré-quebra em linhas para renderização equivalente em SVG e PowerPoint."""
    value = re.sub(r'\s+', ' ', str(text)).strip()
    if not value:
        return []
    font = _font(size, bold)
    words = value.split(' ')
    lines, current = [], ''
    for word in words:
        proposal = (current + ' ' + word).strip()
        if font.getlength(proposal) <= width or not current:
            current = proposal
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.getlength(last + '…') > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + '…'
    return lines


def _rect(items, x, y, w, h, fill, radius=0, stroke=None, sw=1):
    items.append({'type':'rect','x':x,'y':y,'w':w,'h':h,'fill':fill,'radius':radius,'stroke':stroke,'sw':sw})


def _circle(items, x, y, d, fill):
    items.append({'type':'ellipse','x':x,'y':y,'w':d,'h':d,'fill':fill})


def _line(items, x1, y1, x2, y2, color, size=2):
    items.append({'type':'line','x':x1,'y':y1,'x2':x2,'y2':y2,'stroke':color,'sw':size})


def _text(items, value, x, y, w, size=26, color='#FFFFFF', bold=False,
          max_lines=3, align='left', line_h=None):
    line_h = line_h or round(size * 1.34)
    lines = _wrap(value, size, w, max_lines, bold)
    if lines:
        items.append({'type':'text','x':x,'y':y,'w':w,'h':len(lines)*line_h+8,
                      'fontSize':size,'color':color,'bold':bool(bold),'align':align,
                      'lineHeight':line_h,'lines':lines})
    return len(lines)*line_h


def _image(items, asset: str, project_dir: Path, x, y, w, h):
    if not re.fullmatch(r'[0-9a-f]{24}\.png', asset or ''):
        return False
    source = project_dir / 'assets' / asset
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 8*1024*1024:
        return False
    # Encaixar sem distorção no mesmo canvas nos três formatos (SVG/PDF/PPTX).
    with Image.open(source) as original:
        target_w, target_h = max(1, round(w)), max(1, round(h))
        resized = ImageOps.contain(original.convert('RGBA'), (target_w,target_h))
        canvas = Image.new('RGBA', (target_w,target_h), (0,0,0,0))
        canvas.alpha_composite(resized, ((target_w-resized.width)//2,(target_h-resized.height)//2))
        out=io.BytesIO();canvas.save(out,format='PNG')
    b64 = base64.b64encode(out.getvalue()).decode('ascii')
    items.append({'type':'image','x':x,'y':y,'w':w,'h':h,'data':'data:image/png;base64,'+b64})
    return True


def _bullets(items, bullets, palette, x, y, w, limit=5, size=27, gap=13):
    cursor = y
    for bullet in bullets[:limit]:
        lines = _wrap(bullet, size, w-46, 2)
        height = len(lines)*round(size*1.34)
        if cursor + height > 622:
            break
        _circle(items, x, cursor+12, 12, palette['accent'])
        _text(items, bullet, x+34, cursor, w-38, size, palette['fg'], max_lines=2)
        cursor += height+gap
    return cursor


def _section(items, label, p, n, title):
    _rect(items, 0, 0, W, H, p['bg'])
    _rect(items, 0, 0, W, 10, p['accent'])
    _text(items, 'SLIDE STUDIO  /  ' + label.upper(), 64, 40, 900, 16, p['accent'], True, 1)
    _text(items, title, 64, 88, 1150, 43, p['fg'], True, 2)
    _line(items, 64, 668, 1216, 668, p['outline'], 1)
    _text(items, f'IA VIDEO STUDIO    •    {n:02d}', 64, 683, 1100, 13, p['muted'], False, 1)


def _visual_hint(items, p, x, y, w, h):
    _rect(items, x, y, w, h, p['soft'], 18, p['outline'])
    _circle(items, x+w/2-37, y+h/2-75, 74, p['outline'])
    _text(items, 'INSIRA UMA IMAGEM', x+20, y+h/2+10, w-40, 17, p['muted'], True, 1, 'center')
    _text(items, 'Biblioteca de mídia → selecionar', x+20, y+h/2+46, w-40, 14, p['muted'], max_lines=1, align='center')


def suggest_layout(title: str, bullets: list[str], index: int, total: int) -> str:
    t = title.casefold()
    if index == 0 and total > 1 and any(x in t for x in ['introdução', 'curso', 'aula', 'boas-vindas']):
        return 'hero_cover'
    if any(x in t for x in ['objetivo', 'aprender']): return 'learning_objectives'
    if any(x in t for x in ['compar', 'diferença', 'versus', ' vs ']): return 'comparison_table'
    if any(x in t for x in ['topologia', 'arquitetura', 'diagrama', 'fluxo']): return 'diagram_slide'
    if any(x in t for x in ['passo', 'configur', 'procedimento', 'etapa']): return 'step_by_step'
    if any(x in t for x in ['exemplo', 'prática', 'cenário']): return 'practical_example'
    if any(x in t for x in ['quiz', 'pergunta', 'exercício', 'teste']): return 'quiz_slide'
    if any(x in t for x in ['resumo', 'conclus', 'revisão']): return 'summary_slide'
    if len(bullets) > 3: return 'learning_objectives'
    return 'concept_explainer'


def build_slide(project: dict, scene: dict, index: int, project_dir: Path) -> dict:
    theme = project.get('slide_theme', 'tech_blue')
    p = THEMES.get(theme, THEMES['tech_blue'])
    layout = scene.get('layout')
    if layout not in LAYOUTS:
        layout = suggest_layout(scene.get('title',''), scene.get('bullets',[]), index, len(project.get('scenes', [])))
    title = scene.get('title', '')
    bullets = [str(x) for x in scene.get('bullets', []) if str(x).strip()][:8]
    desc = str(scene.get('narration', ''))
    item = []
    asset = scene.get('image', '')
    image_ok = bool(asset and re.fullmatch(r'[0-9a-f]{24}\.png', asset) and (project_dir/'assets'/asset).is_file())

    if layout == 'hero_cover':
        _rect(item, 0, 0, W, H, p['bg'])
        _rect(item, 770, 0, 510, H, p['panel'])
        _rect(item, 815, 70, 402, 580, p['soft'], 28)
        if not _image(item, asset, project_dir, 815, 70, 402, 580):
            _circle(item, 870, 180, 250, p['outline'])
            _circle(item, 940, 255, 160, p['secondary'])
            _rect(item, 875, 440, 280, 10, p['accent'], 5)
        _rect(item, 75, 104, 135, 7, p['accent'], 3)
        _text(item, 'CURSO • MATERIAL DIDÁTICO', 75, 135, 660, 18, p['accent'], True, 1)
        _text(item, title, 75, 236, 660, 60, p['fg'], True, 4, line_h=72)
        _text(item, project.get('description') or 'Aprenda com clareza, exemplos e prática.', 78, 540, 635, 25, p['muted'], False, 3)
        _text(item, 'IA VIDEO STUDIO', 75, 662, 520, 16, p['muted'], True, 1)
    else:
        _section(item, LAYOUTS[layout], p, index+1, title)
        if layout in ('learning_objectives','summary_slide'):
            _rect(item, 64, 213, 1152, 421, p['panel'], 24)
            _bullets(item, bullets or [desc[:180]], p, 99, 257, 1020, 6, 31, 18)
        elif layout == 'concept_explainer':
            _rect(item, 64, 215, 830, 397, p['panel'], 22)
            _rect(item, 923, 215, 293, 397, p['soft'], 22)
            _rect(item, 100, 253, 7, 286, p['accent'], 4)
            _text(item, bullets[0] if bullets else desc, 133, 262, 720, 35, p['fg'], True, 6, line_h=50)
            _text(item, 'CONCEITO-CHAVE', 945, 292, 250, 18, p['accent'], True, 2, 'center')
            _text(item, bullets[1] if len(bullets)>1 else 'Observe o exemplo durante a narração.', 948, 365, 245, 23, p['muted'], False, 6, 'center')
        elif layout == 'two_column_explanation':
            _rect(item, 64, 213, 560, 416, p['panel'], 22)
            _bullets(item, bullets or [desc[:180]], p, 96, 259, 489, 5, 26, 13)
            if not _image(item, asset, project_dir, 651, 213, 565, 416):
                _visual_hint(item, p, 651, 213, 565, 416)
        elif layout == 'comparison_table':
            _rect(item, 64, 218, 556, 397, p['panel'], 22)
            _rect(item, 657, 218, 559, 397, p['panel'], 22)
            _rect(item, 64, 218, 556, 74, p['accent'], 18)
            _rect(item, 657, 218, 559, 74, p['secondary'], 18)
            _text(item, (bullets[0] if bullets else 'Opção A')[:55], 90, 240, 506, 25, p['bg'], True, 2, 'center')
            _text(item, (bullets[1] if len(bullets)>1 else 'Opção B')[:55], 685, 240, 506, 25, '#FFFFFF', True, 2, 'center')
            _text(item, bullets[2] if len(bullets)>2 else 'Características, recursos e aplicações', 98, 325, 485, 27, p['fg'], False, 6)
            _text(item, bullets[3] if len(bullets)>3 else 'Vantagens, limites e casos de uso', 688, 325, 486, 27, p['fg'], False, 6)
        elif layout == 'step_by_step':
            values = bullets or ['Preparação', 'Execução', 'Validação']
            count = min(4, len(values))
            for j, val in enumerate(values[:count]):
                x = 64+j*(1152/count)
                col_w = 1152/count-16
                _rect(item,x,265,col_w,297,p['panel'],19)
                _circle(item,x+24,288,65,p['accent'])
                _text(item,str(j+1),x+26,300,62,29,p['bg'],True,1,'center')
                _text(item,val,x+24,397,col_w-42,25,p['fg'],True,5)
                if j<count-1:
                    _text(item,'→',x+col_w-5,405,34,28,p['accent'],True,1)
        elif layout == 'diagram_slide':
            labels = (bullets or ['Origem', 'Processo', 'Resultado'])[:4]
            count = len(labels)
            bw = min(250, 1010/count-28)
            start = (W-(count*bw+(count-1)*38))/2
            for j, val in enumerate(labels):
                x = start+j*(bw+38)
                _rect(item,x,315,bw,165,p['panel'],18,p['outline'],2)
                _rect(item,x,315,bw,11,p['accent'],7)
                _text(item,val,x+15,357,bw-30,24,p['fg'],True,3,'center')
                if j<count-1:
                    _line(item,x+bw+7,398,x+bw+31,398,p['accent'],5)
                    _text(item,'›',x+bw+6,367,32,30,p['accent'],True,1,'center')
            _text(item,'FLUXO DE REFERÊNCIA  •  esquema ilustrativo',64,557,1150,16,p['muted'],False,1,'center')
        elif layout == 'practical_example':
            _rect(item, 64, 218, 1152, 397, p['panel'],22)
            _rect(item, 94, 250, 173, 43, p['accent'], 12)
            _text(item,'NA PRÁTICA',108,259,146,19,p['bg'],True,1,'center')
            if image_ok and _image(item,asset,project_dir,704,280,455,285):
                _bullets(item,bullets or [desc[:160]],p,101,325,540,4,25,12)
            else:
                _bullets(item,bullets or [desc[:160]],p,101,325,1050,5,28,14)
        elif layout == 'quiz_slide':
            _rect(item,64,215,1152,130,p['panel'],18)
            _text(item,bullets[0] if bullets else title,104,251,1050,31,p['fg'],True,2)
            for j, val in enumerate(bullets[1:5]):
                x = 64+(j%2)*588
                y = 366+(j//2)*117
                _rect(item,x,y,560,98,p['soft'],16,p['outline'])
                _circle(item,x+20,y+24,42,p['accent'])
                _text(item,'ABCD'[j],x+30,y+32,26,16,p['bg'],True,1,'center')
                _text(item,val,x+80,y+24,455,23,p['fg'],False,2)
        else:
            _bullets(item,bullets,p,80,260,1120)
    return {'width':W,'height':H,'theme':theme,'layout':layout,'elements':item,'title':title}


def as_svg(plan: dict) -> str:
    shapes = []
    for e in plan['elements']:
        k=e['type'];x=e['x'];y=e['y']
        if k=='rect':
            stroke = f' stroke="{e["stroke"]}" stroke-width="{e["sw"]}"' if e.get('stroke') else ''
            shapes.append(f'<rect x="{x}" y="{y}" width="{e["w"]}" height="{e["h"]}" rx="{e["radius"]}" fill="{e["fill"]}"{stroke}/>')
        elif k=='ellipse':
            shapes.append(f'<ellipse cx="{x+e["w"]/2}" cy="{y+e["h"]/2}" rx="{e["w"]/2}" ry="{e["h"]/2}" fill="{e["fill"]}"/>')
        elif k=='line':
            shapes.append(f'<line x1="{x}" y1="{y}" x2="{e["x2"]}" y2="{e["y2"]}" stroke="{e["stroke"]}" stroke-width="{e["sw"]}"/>')
        elif k=='text':
            weight='700' if e['bold'] else '400'
            anchor={'center':'middle','right':'end','left':'start'}.get(e['align'],'start')
            tx=x+(e['w']/2 if e['align']=='center' else e['w'] if e['align']=='right' else 0)
            tspans=''.join(f'<tspan x="{tx}" y="{y+e["fontSize"]+(i*e["lineHeight"])}">{xml_escape(line)}</tspan>' for i,line in enumerate(e['lines']))
            shapes.append(f'<text fill="{e["color"]}" font-family="DejaVu Sans, sans-serif" font-size="{e["fontSize"]}" font-weight="{weight}" text-anchor="{anchor}">{tspans}</text>')
        elif k=='image':
            shapes.append(f'<image x="{x}" y="{y}" width="{e["w"]}" height="{e["h"]}" preserveAspectRatio="xMidYMid meet" href="{e["data"]}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + '\n'.join(shapes) + '</svg>'


def render_slides(project: dict, folder: Path, progress=None) -> dict:
    """Exportação independente do Piper: SVG, frames PNG, PDF vetor e PPTX editável."""
    import cairosvg
    from pypdf import PdfWriter

    work=folder/'build'/'slide_studio'
    exports=folder/'exports'
    work.mkdir(parents=True,exist_ok=True)
    exports.mkdir(parents=True,exist_ok=True)
    slides=[]; plans=[]; pdf_parts=[]
    scenes=project['scenes']
    for i,scene in enumerate(scenes):
        plan=build_slide(project,scene,i,folder)
        plans.append(plan)
        svg=as_svg(plan).encode('utf-8')
        name=work/f'slide-{i+1:03d}.svg'
        name.write_bytes(svg)
        png=work/f'slide-{i+1:03d}.png'
        cairosvg.svg2png(bytestring=svg,write_to=str(png),output_width=1280,output_height=720)
        part=work/f'slide-{i+1:03d}.pdf'
        cairosvg.svg2pdf(bytestring=svg,write_to=str(part))
        pdf_parts.append(part)
        slides.append(png)
        if progress:progress(f'Criando slide {i+1}/{len(scenes)}', 10+int(60*(i+1)/len(scenes)))
    writer=PdfWriter()
    for part in pdf_parts:writer.append(str(part))
    with (exports/'slides.pdf').open('wb') as out:writer.write(out)
    data=work/'slides.json'
    data.write_text(json.dumps(plans,ensure_ascii=False),encoding='utf-8')
    cmd=['node',str(Path(__file__).parent/'renderer'/'export_pptx.cjs'),str(data),str(exports/'slides.pptx')]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if result.returncode:
        raise RuntimeError('Falha no PptxGenJS: '+(result.stderr or result.stdout)[-900:])
    if progress:progress('Slides e apresentações concluídos',95)
    return {'slides':len(slides),'pdf':'slides.pdf','pptx':'slides.pptx','frames':slides}
