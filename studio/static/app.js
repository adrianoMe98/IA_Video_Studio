/* IA Video Studio — interface sem dependências externas */
'use strict';
const $ = (id) => document.getElementById(id);
const esc = (text) => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let selected = null;
let lastStatus = null;
let polling = null;
let viewMode = 'active';
let activeProjects = [];
let trashedProjects = [];
let assets = [];
let imageEnabled = false;
let imageJob = null;
let imagePanelOpen = false;
let editingAsset = null;
let projectLoad = 0;
let imageRefresh = 0;
const exampleDiagram = {
  nodes: [{id:'olt', label:'OLT'}, {id:'splitter', label:'Splitter'}, {id:'ontA', label:'ONT A'}, {id:'ontB', label:'ONT B'}],
  edges: [{source:'olt', target:'splitter'}, {source:'splitter', target:'ontA'}, {source:'splitter', target:'ontB'}],
};
const layouts = {auto:'Automático',hero_cover:'Capa',learning_objectives:'Objetivos',concept_explainer:'Conceito',two_column_explanation:'Texto + imagem',comparison_table:'Comparação',step_by_step:'Passo a passo',diagram_slide:'Topologia / diagrama',practical_example:'Exemplo prático',quiz_slide:'Quiz / exercício',summary_slide:'Resumo'};
const files = ['video.mp4','video_legendas.mp4','slides.pdf','slides.pptx','slides.md','legendas.srt'];

function toast(text) {
  $('toast').textContent = text;
  $('toast').classList.add('show');
  setTimeout(() => $('toast').classList.remove('show'), 4500);
}
async function request(url, opts = {}) {
  const response = await fetch(url, opts);
  let json;
  try { json = await response.json(); } catch { json = null; }
  if (!response.ok) {
    const detail = json?.detail;
    throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join(' ') : detail || `HTTP ${response.status}`);
  }
  return json;
}
function jsonOpt(method, data) {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)};
}
function renderProjectList() {
  const q = $('project-search').value.trim().toLocaleLowerCase('pt-BR');
  const values = viewMode === 'active' ? activeProjects : trashedProjects;
  const filtered = values.filter(p => `${p.title} ${p.description || ''}`.toLocaleLowerCase('pt-BR').includes(q));
  $('active-count').textContent = `(${activeProjects.length})`;
  $('trash-count').textContent = `(${trashedProjects.length})`;
  $('tab-active').classList.toggle('active', viewMode === 'active');
  $('tab-trash').classList.toggle('active', viewMode === 'trash');
  $('tab-active').setAttribute('aria-pressed', String(viewMode === 'active'));
  $('tab-trash').setAttribute('aria-pressed', String(viewMode === 'trash'));
  $('projects').innerHTML = filtered.length ? filtered.map(p => {
    const detail = `${p.scenes} cena(s) · ${p.deleted_at?.slice(0, 10) || p.updated_at?.slice(0, 10) || ''}`;
    return `<div class="project-entry ${p.id === selected && viewMode === 'active' ? 'active' : ''}">
      <button type="button" class="project-card" data-act="${viewMode === 'active' ? 'open' : 'none'}" data-project="${esc(p.id)}" ${viewMode === 'trash' ? 'disabled' : ''}><b>${esc(p.title)}</b><small>${esc(detail)}</small></button>
      <div class="project-tools">${viewMode === 'active' ? `
        <button type="button" data-act="rename" data-project="${esc(p.id)}" title="Renomear projeto" aria-label="Renomear ${esc(p.title)}">Renomear</button>
        <button type="button" data-act="duplicate" data-project="${esc(p.id)}" title="Duplicar projeto" aria-label="Duplicar ${esc(p.title)}">Duplicar</button>
        <button type="button" class="danger" data-act="trash" data-project="${esc(p.id)}" title="Enviar para lixeira" aria-label="Excluir ${esc(p.title)}">Excluir</button>` : `
        <button type="button" data-act="restore" data-project="${esc(p.id)}" aria-label="Restaurar ${esc(p.title)}">Restaurar</button>
        <button type="button" class="danger" data-act="erase" data-project="${esc(p.id)}" aria-label="Excluir definitivamente ${esc(p.title)}">Apagar definitivamente</button>`}
      </div>
    </div>`;
  }).join('') : `<p class="empty-list">${q ? 'Nenhum projeto corresponde à pesquisa.' : viewMode === 'trash' ? 'A lixeira está vazia.' : 'Nenhuma videoaula ainda.'}</p>`;
}
async function refreshList() {
  [activeProjects, trashedProjects] = await Promise.all([request('/api/projects'), request('/api/trash')]);
  renderProjectList();
}
function projectName(id) {
  return [...activeProjects, ...trashedProjects].find(p => p.id === id)?.title || 'Projeto';
}
function askDialog({title, description, label = '', value = '', confirmText = 'Confirmar', danger = false}) {
  return new Promise(resolve => {
    const dialog = $('action-dialog');
    $('dialog-title').textContent = title;
    $('dialog-desc').textContent = description;
    $('dialog-confirm').textContent = confirmText;
    $('dialog-confirm').classList.toggle('danger-button', danger);
    const input = $('dialog-input');
    const showInput = Boolean(label);
    input.classList.toggle('hidden', !showInput);
    $('dialog-label').classList.toggle('hidden', !showInput);
    $('dialog-label').textContent = label;
    input.value = value;
    input.required = showInput;
    const onClose = () => {
      dialog.removeEventListener('close', onClose);
      const accepted = dialog.returnValue === 'confirm';
      resolve(accepted ? (showInput ? input.value.trim() : true) : null);
    };
    dialog.addEventListener('close', onClose);
    dialog.returnValue = 'cancel';
    dialog.showModal();
    if (showInput) input.focus();
  });
}
function clearEditor() {
  projectLoad++;
  selected = null;
  assets = [];
  $('preview-panel').classList.add('hidden');
  lastStatus = null;
  $('editor').classList.add('hidden');
  $('welcome').classList.remove('hidden');
  $('video').pause();
  $('video').removeAttribute('src');
  $('video').load();
}
async function actionOnProject(action, id) {
  if (!id || !/^[0-9a-f]{12}$/.test(id)) return;
  if (action === 'open') return loadProject(id);
  const title = projectName(id);
  if (action === 'rename') {
    const name = await askDialog({title:'Renomear projeto', description:'O novo nome será atualizado no projeto salvo.', label:'Novo nome', value:title, confirmText:'Salvar nome'});
    if (!name) return;
    const updated = await request(`/api/projects/${id}/rename`, jsonOpt('PATCH', {title:name}));
    if (selected === id) $('title').value = updated.title;
    toast('Nome atualizado.');
  } else if (action === 'duplicate') {
    const copy = await request(`/api/projects/${id}/duplicate`, {method:'POST'});
    viewMode = 'active';
    await loadProject(copy.id);
    toast('Cópia criada. Renderize a cópia para gerar novos arquivos.');
    return;
  } else if (action === 'trash') {
    const ok = await askDialog({title:'Mover para a lixeira?', description:`O projeto “${title}” e seus arquivos serão preservados na lixeira e poderão ser restaurados.`, confirmText:'Mover para lixeira', danger:true});
    if (!ok) return;
    await request(`/api/projects/${id}`, {method:'DELETE'});
    if (selected === id) clearEditor();
    toast('Projeto movido para a lixeira.');
  } else if (action === 'restore') {
    await request(`/api/trash/${id}/restore`, {method:'POST'});
    viewMode = 'active';
    toast('Projeto restaurado com seus arquivos.');
  } else if (action === 'erase') {
    const answer = await askDialog({title:'Exclusão definitiva', description:`Você está prestes a apagar “${title}”, seus slides, narrações e vídeos exportados. Essa ação não pode ser desfeita.`, label:'Digite EXCLUIR para confirmar', confirmText:'Apagar definitivamente', danger:true});
    if (answer === null) return;
    if (answer !== 'EXCLUIR') {toast('Exclusão cancelada: digite EXCLUIR exatamente.');return;}
    await request(`/api/trash/${id}`, jsonOpt('DELETE', {confirm:'EXCLUIR'}));
    toast('Projeto apagado definitivamente.');
  } else return;
  await refreshList();
}

function sceneHtml(scene, i) {
  const opts = Object.entries(layouts).map(([id,name]) => `<option value="${id}" ${scene.layout===id?'selected':''}>${esc(name)}</option>`).join('');
  const media = `<option value="">Sem imagem</option>`+assets.map(a=>`<option value="${esc(a.id)}" ${scene.image===a.id?'selected':''}>${esc(a.title || a.id.slice(0,9))}</option>`).join('');
  const diagram = scene.diagramSource ?? (scene.diagram ? JSON.stringify(scene.diagram, null, 2) : '');
  const generate = imageEnabled ? `<button type="button" class="preview-button" data-illustrate="${i}">Gerar imagem</button>` : '';
  return `<div class="scene"><div class="scenehead"><span>CENA ${String(i+1).padStart(2,'0')}</span><div class="rowbuttons"><button type="button" class="preview-button" data-preview="${i}">◧ Prévia</button>${generate}<button data-remove="${i}" aria-label="Excluir cena ${i+1}">Excluir</button></div></div>
    <div class="scene-meta"><label>Bloco visual<select class="scene-layout">${opts}</select></label><label>Imagem da biblioteca<select class="scene-image">${media}</select></label></div>
    <div class="scenebody"><label class="title">Título do slide<input class="stitle" maxlength="120" value="${esc(scene.title)}" placeholder="Título da cena"></label>
    <label>Tópicos do slide (um por linha)<textarea class="bullets" placeholder="Ponto 1&#10;Ponto 2">${esc((scene.bullets || []).join('\n'))}</textarea></label>
    <label>Texto narrado em português<textarea class="narration" placeholder="Digite a explicação que será narrada...">${esc(scene.narration)}</textarea></label></div>
    <details class="diagram-source" ${diagram ? 'open' : ''}>
      <summary>Diagrama técnico</summary>
      <label>Grafo em JSON<textarea class="scene-diagram" spellcheck="false">${esc(diagram)}</textarea></label>
      <button type="button" class="small" data-diagram-example>Preencher exemplo GPON</button>
    </details></div>`;
}
function renderScenes(scenes) {
  $('scenes').innerHTML = scenes.map(sceneHtml).join('');
  $('scenes').querySelectorAll('[data-preview]').forEach(button => button.addEventListener('click', () => previewSlide(Number(button.dataset.preview))));
  $('scenes').querySelectorAll('[data-illustrate]').forEach(button => button.addEventListener('click', () => {
    const scene = collectScenes()[Number(button.dataset.illustrate)];
    imagePanelOpen = true;
    $('image-prompt').value = `Ilustração didática sobre ${scene.title}`.slice(0, 1000);
    renderImageJob();
    ($('image-generation-form').classList.contains('hidden') ? $('image-job-status') : $('image-prompt')).focus();
  }));
  $('scenes').querySelectorAll('[data-diagram-example]').forEach(button => button.addEventListener('click', () => {
    const source = button.closest('details').querySelector('textarea');
    if (!source.value.trim()) source.value = JSON.stringify(exampleDiagram, null, 2);
    source.focus();
  }));
  $('scenes').querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
    const all = collectScenes();
    if (all.length <= 1) { toast('Mantenha ao menos uma cena.'); return; }
    all.splice(Number(button.dataset.remove), 1);
    renderScenes(all);
  }));
}
function collectScenes() {
  return Array.from($('scenes').querySelectorAll('.scene')).map(box => ({
    title: box.querySelector('.stitle').value.trim(),
    bullets: box.querySelector('.bullets').value.split(/\n/).map(v => v.trim()).filter(Boolean),
    narration: box.querySelector('.narration').value.trim(),
    layout: box.querySelector('.scene-layout').value,
    image: box.querySelector('.scene-image').value,
    diagramSource: box.querySelector('.scene-diagram').value,
  }));
}
function payload() {
  return {
    title: $('title').value.trim(),
    description: $('description').value.trim(),
    voice: $('voice').value,
    quality: $('quality').value,
    burn_subtitles: $('burn').checked,
    slide_theme: $('slide-theme').value,
    scenes: collectScenes().map(({diagramSource, ...scene}, i) => {
      if (diagramSource.trim()) {
        try { scene.diagram = JSON.parse(diagramSource); }
        catch { throw new Error(`Revise o JSON do diagrama na cena ${i + 1}.`); }
        if (!scene.diagram || typeof scene.diagram !== 'object' || Array.isArray(scene.diagram)) {
          throw new Error(`Informe um objeto com nós e conexões na cena ${i + 1}.`);
        }
      }
      return scene;
    }),
  };
}
function populate(p) {
  $('welcome').classList.add('hidden');
  $('editor').classList.remove('hidden');
  $('title').value = p.title || '';
  $('description').value = p.description || '';
  $('voice').value = p.voice || 'faber';
  $('quality').value = p.quality || '720';
  $('burn').checked = Boolean(p.burn_subtitles);
  $('slide-theme').value = p.slide_theme || 'tech_blue';
  renderScenes(p.scenes || []);
  $('preview-panel').classList.add('hidden');
  $('slides-only-links').innerHTML = '';
  $('output').classList.add('hidden');
  $('status').classList.add('hidden');
  $('video').removeAttribute('src');
}
async function loadProject(pid) {
  const load = ++projectLoad;
  try {
    const [p, media, capability, job] = await Promise.all([
      request(`/api/projects/${pid}`), request(`/api/projects/${pid}/assets`),
      request('/api/image-generation'), request(`/api/projects/${pid}/image-job`),
    ]);
    if (load !== projectLoad) return;
    selected = pid;
    viewMode = 'active';
    imageRefresh++;
    assets = media;
    imageEnabled = capability.enabled;
    imageJob = job;
    imagePanelOpen = false;
    $('image-prompt').value = '';
    $('asset-search').value = '';
    $('asset-origin').value = '';
    populate(p);
    renderImageJob();
    renderAssetGallery();
    await refreshList();
    await refreshJob();
  } catch (err) { toast(err.message); }
}
async function newProject() {
  try {
    const sample = await request('/api/sample');
    sample.title = 'Minha primeira videoaula';
    const project = await request('/api/projects', jsonOpt('POST', sample));
    await loadProject(project.id);
    toast('Projeto de exemplo criado. Edite as cenas antes de gerar.');
  } catch (err) { toast(err.message); }
}
async function save() {
  if (!selected) throw new Error('Crie ou selecione um projeto primeiro.');
  const data = payload();
  if (!data.title || !data.scenes.every(s => s.title && s.narration)) {
    throw new Error('Preencha o título do projeto e o título/narração de cada cena.');
  }
  await request(`/api/projects/${selected}`, jsonOpt('PUT', data));
  await refreshList();
}
async function saveClick() {
  try { await save(); toast('Projeto salvo.'); } catch (err) { toast(err.message); }
}
async function startRender() {
  try {
    await save();
    $('render').disabled = true;
    await request(`/api/projects/${selected}/render`, {method:'POST'});
    toast('Renderização adicionada à fila.');
    await refreshJob();
  } catch (err) { $('render').disabled = false; toast(err.message); }
}
async function refreshJob() {
  if (!selected) return;
  const id = selected;
  try {
    const job = await request(`/api/projects/${id}/job`);
    if (id !== selected) return;
    lastStatus = job;
    if (job.status === 'none') { $('status').classList.add('hidden'); $('render').disabled=false; return; }
    const running = job.status === 'running' || job.status === 'queued';
    $('render').disabled = running;
    $('status').classList.remove('hidden');
    $('status').classList.toggle('error', job.status==='error');
    $('status').innerHTML = `<strong>${job.status==='done'?'✓ Concluído':job.status==='error'?'Falha':running?'Processando...':'Status'}</strong><div>${esc(job.message || '')}</div><div class="bar"><i style="width:${Math.max(0,Math.min(100,Number(job.percent||0)))}%"></i></div>`;
    if (job.status==='done') showFiles(job.result?.video || 'video.mp4');
    if (job.status==='error') $('output').classList.add('hidden');
  } catch (err) { toast(err.message); }
}
function showFiles(mainVideo) {
  $('output').classList.remove('hidden');
  const names = files.filter(name => name!=='video_legendas.mp4' || mainVideo==='video_legendas.mp4');
  $('links').innerHTML = names.map(name => `<a href="/api/projects/${selected}/files/${name}" target="_blank" rel="noopener" download>${esc(name)}</a>`).join('');
  const url = `/api/projects/${selected}/files/${mainVideo}`;
  if ($('video').getAttribute('src') !== url) $('video').src = url;
}
async function upload() {
  const f = $('upload').files?.[0];
  if (!f) return;
  const fd = new FormData(); fd.append('file', f);
  try {
    toast('Importando texto e gerando rascunho...');
    const project = await request('/api/projects/import', {method:'POST', body:fd});
    await loadProject(project.id);
    toast('Importação concluída. Confira os tópicos e a narração!');
  } catch (err) { toast(err.message); }
  $('upload').value = '';
}
async function checkHealth() {
  try {
    const h = await request('/api/health');
    const installed = Object.values(h.voices).filter(Boolean).length;
    $('health').textContent = `Serviço ativo · ${installed}/2 vozes`;
    if (!installed) toast('Baixe uma voz para renderizar: ./scripts/baixar-voz.sh');
  } catch { $('health').textContent='Serviço indisponível'; }
}
$('new').addEventListener('click', newProject);
$('project-search').addEventListener('input', renderProjectList);
$('tab-active').addEventListener('click', () => {viewMode = 'active';renderProjectList();});
$('tab-trash').addEventListener('click', () => {viewMode = 'trash';renderProjectList();});
$('projects').addEventListener('click', async event => {
  const button = event.target.closest('button[data-act]');
  if (!button || button.disabled) return;
  button.disabled = true;
  try { await actionOnProject(button.dataset.act, button.dataset.project); }
  catch (err) { toast(err.message); }
  finally { button.disabled = false; }
});
$('welcome-new').addEventListener('click', newProject);
$('add').addEventListener('click', () => {
  const scenes = collectScenes();
  scenes.push({title:'Nova cena', bullets:['Ponto principal'], narration:'Escreva aqui a narração desta cena.', layout:'auto', image:''});
  renderScenes(scenes);
  $('scenes').lastElementChild.scrollIntoView({behavior:'smooth',block:'center'});
});
$('save').addEventListener('click', saveClick);
$('render').addEventListener('click', startRender);
$('upload').addEventListener('change', upload);
Promise.all([refreshList(),checkHealth()]).catch(err => toast(err.message));
polling = setInterval(() => {
  if (selected) refreshJob();
  if (selected && ['queued', 'running'].includes(imageJob?.status)) refreshImageJob(selected).catch(err => toast(err.message));
}, 2400);
$('generate').addEventListener('click', async () => {
  if (!selected) return toast('Selecione um projeto.');
  const pid = selected;
  const load = projectLoad;
  const button = $('generate');
  button.disabled = true;
  button.textContent = 'Preparando roteiro…';
  try {
    const project = payload();
    const minutes = $('script-duration').value;
    const draft = await request(`/api/projects/${pid}/suggest?duration_minutes=${minutes}`, jsonOpt('POST', project));
    if (load !== projectLoad) return;
    const seconds = draft.estimated_seconds;
    const estimate = `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
    const short = draft.below_target ? ` A sugestão ficou abaixo dos ${minutes} min solicitados.` : '';
    const accepted = await askDialog({
      title: 'Aplicar roteiro sugerido?',
      description: `${draft.scenes.length} cenas com narração estimada em ${estimate}.${short} Aplicar substitui as cenas no editor. Revise o conteúdo antes de salvar.`,
      confirmText: 'Aplicar roteiro',
    });
    if (!accepted || load !== projectLoad) return;
    renderScenes(draft.scenes);
    $('preview-panel').classList.add('hidden');
    toast('Roteiro aplicado. Revise as cenas antes de salvar ou gerar a videoaula.');
  } catch (err) {
    if (load === projectLoad) toast('Falha na IA local: ' + err.message);
  } finally {
    button.disabled = false;
    button.textContent = '✦ Sugerir cenas com IA';
  }
});

// Biblioteca e geração de ilustrações
function renderAssetGallery() {
  const search = $('asset-search').value.trim().toLocaleLowerCase('pt-BR');
  const origin = $('asset-origin').value;
  const filtered = assets.filter(asset => (!origin || asset.origin === origin) &&
    [asset.title, asset.alt, asset.license, ...(asset.tags || [])].join(' ').toLocaleLowerCase('pt-BR').includes(search));
  $('asset-gallery').innerHTML = filtered.length ? filtered.map(asset => `
    <article class="image-card">
      <img src="/api/projects/${selected}/assets/${encodeURIComponent(asset.id)}" alt="${esc(asset.alt || 'Imagem da biblioteca')}" loading="lazy">
      <b>${esc(asset.title || 'Imagem importada')}</b>
      <small>${asset.origin === 'ai' ? 'Ilustração gerada por IA' : 'Importada'}${asset.tags?.length ? ` · ${esc(asset.tags.join(', '))}` : ''}</small>
      <div class="rowbuttons">
        <button type="button" class="small" data-edit-asset="${esc(asset.id)}">Detalhes</button>
        <button type="button" class="small danger" data-delete-asset="${esc(asset.id)}">Excluir</button>
      </div>
    </article>`).join('') : '<small>Nenhuma imagem encontrada.</small>';
}
async function refreshAssets(pid) {
  const media = await request(`/api/projects/${pid}/assets`);
  if (selected !== pid) return;
  const scenes = collectScenes();
  assets = media;
  renderScenes(scenes);
  renderAssetGallery();
}
function renderImageJob() {
  const status = imageJob?.status;
  const active = ['queued', 'running'].includes(status);
  const ready = status === 'ready';
  $('image-generation').classList.toggle('hidden', !(imagePanelOpen || active || ready || status === 'error'));
  $('image-generation-form').classList.toggle('hidden', !imageEnabled || active || ready);
  $('image-job-status').textContent = {
    queued: 'Ilustração na fila.', running: 'Gerando ilustração localmente…',
    ready: 'Revise a fidelidade técnica da ilustração antes de aprovar.',
    error: imageJob?.message, cancelled: 'Geração descartada.',
  }[status] || '';
  $('approve-image').classList.toggle('hidden', !ready);
  $('discard-image').classList.toggle('hidden', !active && !ready);
  $('image-draft').classList.toggle('hidden', !ready);
  if (ready) $('image-draft').src = `/api/projects/${selected}/image-job/${imageJob.id}/preview`;
  else $('image-draft').removeAttribute('src');
}
async function refreshImageJob(pid) {
  const refresh = ++imageRefresh;
  const job = await request(`/api/projects/${pid}/image-job`);
  if (pid !== selected || refresh !== imageRefresh) return;
  imageJob = job;
  renderImageJob();
}
$('asset-search').addEventListener('input', renderAssetGallery);
$('asset-origin').addEventListener('change', renderAssetGallery);
$('asset-gallery').addEventListener('click', async event => {
  const edit = event.target.closest('[data-edit-asset]');
  const remove = event.target.closest('[data-delete-asset]');
  if (edit) {
    const asset = assets.find(item => item.id === edit.dataset.editAsset);
    editingAsset = {id: asset.id, pid: selected};
    $('asset-title').value = asset.title || '';
    $('asset-alt').value = asset.alt || '';
    $('asset-tags').value = (asset.tags || []).join(', ');
    $('asset-license').value = asset.license || '';
    $('asset-provenance').textContent = asset.origin === 'ai' ? `Gerada por IA · ${asset.model}${asset.model_revision ? ` (${asset.model_revision})` : ''} · seed ${asset.seed} · ${asset.prompt}` : 'Imagem importada';
    $('asset-dialog').showModal();
  }
  if (remove) {
    const pid = selected;
    const id = remove.dataset.deleteAsset;
    const scenes = collectScenes().flatMap((scene, index) => scene.image === id ? [index + 1] : []);
    if (scenes.length) return toast(`Desvincule a imagem das cenas ${scenes.join(', ')} e salve o projeto.`);
    const confirmed = await askDialog({title:'Excluir imagem', description:'A imagem será removida da biblioteca deste projeto.', confirmText:'Excluir', danger:true});
    if (!confirmed || selected !== pid) return;
    try {
      await request(`/api/projects/${pid}/assets/${encodeURIComponent(id)}`, {method:'DELETE'});
      await refreshAssets(pid);
    } catch (err) { toast(err.message); }
  }
});
$('close-asset-dialog').addEventListener('click', () => $('asset-dialog').close());
$('asset-form').addEventListener('submit', async event => {
  event.preventDefault();
  const {pid, id} = editingAsset;
  const metadata = {
    title: $('asset-title').value.trim(), alt: $('asset-alt').value.trim(),
    tags: $('asset-tags').value.split(',').map(tag => tag.trim()).filter(Boolean),
    license: $('asset-license').value.trim(),
  };
  try {
    await request(`/api/projects/${pid}/assets/${encodeURIComponent(id)}`, jsonOpt('PATCH', metadata));
    $('asset-dialog').close();
    await refreshAssets(pid);
  } catch (err) { toast(err.message); }
});
$('image-generation-form').addEventListener('submit', async event => {
  event.preventDefault();
  const pid = selected;
  $('start-image').disabled = true;
  try {
    await request(`/api/projects/${pid}/image-job`, jsonOpt('POST', {prompt: $('image-prompt').value}));
    await refreshImageJob(pid);
  } catch (err) { toast(err.message); }
  finally { $('start-image').disabled = false; }
});
for (const [buttonId, suffix, method] of [
  ['approve-image', '/approve', 'POST'], ['discard-image', '', 'DELETE'],
]) {
  $(buttonId).addEventListener('click', async () => {
    const pid = selected;
    $(buttonId).disabled = true;
    try {
      await request(`/api/projects/${pid}/image-job/${imageJob.id}${suffix}`, {method});
      if (suffix) {
        await refreshAssets(pid);
        toast('Imagem aprovada. Selecione-a na cena e use um bloco como Texto + imagem.');
      }
      await refreshImageJob(pid);
    } catch (err) { toast(err.message); }
    finally { $(buttonId).disabled = false; }
  });
}
async function previewSlide(index) {
  try {
    await save();
    $('preview-panel').classList.remove('hidden');
    $('preview-number').textContent = `Slide ${index+1}`;
    $('slide-preview').src = `/api/projects/${selected}/slides/${index}/preview?ts=${Date.now()}`;
    $('preview-panel').scrollIntoView({behavior:'smooth',block:'center'});
  } catch(err) {toast(err.message);}
}
async function uploadImage() {
  const f = $('image-upload').files?.[0];
  if (!selected || !f) return;
  if (f.size > 6*1024*1024) return toast('Imagem muito grande. Máximo 6 MB.');
  try {
    const pid = selected;
    const fd = new FormData();fd.append('file', f);
    await request(`/api/projects/${pid}/assets`,{method:'POST',body:fd});
    await refreshAssets(pid);
    toast('Imagem recebida. Selecione-a no bloco da cena desejada.');
  } catch(err) {toast(err.message);}
  finally {$('image-upload').value='';}
}
async function autoLayout() {
  try {
    await save();
    const p = await request(`/api/projects/${selected}/slides/auto-layout`,{method:'POST'});
    renderScenes(p.scenes);
    toast('Blocos organizados automaticamente. Revise o resultado.');
  } catch(err) {toast(err.message);}
}
async function exportSlides() {
  if (!selected) return toast('Selecione um projeto.');
  $('export-slides').disabled = true;
  $('export-slides').textContent='Exportando...';
  try {
    await save();
    const result = await request(`/api/projects/${selected}/slides/export`,{method:'POST'});
    $('slides-only-links').innerHTML = result.files.map(name=>`<a href="/api/projects/${selected}/files/${name}" target="_blank" rel="noopener" download>${esc(name)} ↓</a>`).join('');
    toast(`Apresentação com ${result.slides} slides pronta.`);
  } catch(err) {toast(err.message);}
  finally {$('export-slides').disabled=false;$('export-slides').textContent='Exportar PPTX + PDF';}
}
$('image-upload').addEventListener('change', uploadImage);
$('auto-layout').addEventListener('click', autoLayout);
$('export-slides').addEventListener('click', exportSlides);
