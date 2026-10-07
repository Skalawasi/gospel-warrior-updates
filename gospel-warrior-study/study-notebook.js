/* Text anchors use DOM offsets + source fingerprints, never stored HTML. */
const StudyNotebook = (() => {
  let data = { note: '', entries: [] }, studyID = null, selection = null, fingerprint = '';
  const body = () => document.getElementById('articleBody');
  const key = () => `gw-study-notebook:${studyID}`;
  const labels = { highlight: 'Highlight', underline: 'Underlined', bookmark: 'Bookmark' };
  function sourceFingerprint(text) {
    let hash = 2166136261;
    for (let i = 0; i < text.length; i++) { hash ^= text.charCodeAt(i); hash = Math.imul(hash, 16777619); }
    return `${text.length}:${hash >>> 0}`;
  }
  function persist() {
    if (!studyID) return false;
    try {
      localStorage.setItem(key(), JSON.stringify(data));
      document.getElementById('noteStatus').textContent = 'Saved on this device.';
      return true;
    } catch (_) {
      document.getElementById('noteStatus').textContent = 'Could not save: device storage is full. Copy your notes before closing.';
      return false;
    }
  }
  function currentEntries() {
    return data.entries.filter(entry => entry.language === StudyLanguages.displayed?.language && entry.fingerprint === fingerprint &&
      body().textContent.slice(entry.start, entry.end) === entry.quote);
  }
  function updateTools() {
    const available = !!StudyLanguages.displayed && studyID === state.currentPost?.id;
    document.getElementById('studyHighlight').disabled = !available || !selection;
    document.getElementById('studyUnderline').disabled = !available || !selection;
    document.getElementById('studyPassageBookmark').disabled = !available;
    document.getElementById('annotationHint').textContent = selection ? `${selection.quote.length} characters selected` : 'Select study text to highlight or underline.';
  }
  function captureSelection() {
    selection = null;
    const chosen = getSelection();
    if (StudyLanguages.displayed && chosen?.rangeCount && !chosen.isCollapsed) {
      const range = chosen.getRangeAt(0);
      if (body().contains(range.startContainer) && body().contains(range.endContainer)) {
        const before = document.createRange(); before.selectNodeContents(body()); before.setEnd(range.startContainer, range.startOffset);
        const start = before.toString().length;
        before.setEnd(range.endContainer, range.endOffset);
        const end = before.toString().length;
        const quote = body().textContent.slice(start, end);
        if (quote.trim()) selection = { start, end, quote };
      }
    }
    updateTools();
  }
  function applyMarks() {
    const entries = currentEntries();
    const walker = document.createTreeWalker(body(), NodeFilter.SHOW_TEXT);
    const nodes = []; let node, offset = 0;
    while ((node = walker.nextNode())) { nodes.push({ node, start: offset }); offset += node.length; }
    for (const { node, start } of nodes) {
      const end = start + node.length;
      const overlaps = entries.filter(entry => entry.start < end && entry.end > start);
      if (!overlaps.length) continue;
      const points = [...new Set([start, end, ...overlaps.flatMap(entry => [Math.max(start, entry.start), Math.min(end, entry.end)])])].sort((a, b) => a - b);
      const fragment = document.createDocumentFragment();
      for (let i = 0; i < points.length - 1; i++) {
        const left = points[i], right = points[i + 1];
        const text = node.textContent.slice(left - start, right - start);
        const active = overlaps.filter(entry => entry.start <= left && entry.end >= right);
        if (!active.length) fragment.append(document.createTextNode(text));
        else {
          const span = document.createElement('span');
          span.className = [...new Set(active.map(entry => `study-${entry.type}`))].join(' ');
          span.dataset.markIds = active.map(entry => entry.id).join(' ');
          span.textContent = text; fragment.append(span);
        }
      }
      node.replaceWith(fragment);
    }
  }
  function renderLists() {
    const active = new Set(currentEntries().map(entry => entry.id));
    const list = entries => entries.length ? entries.map(entry => {
      const otherLanguage = entry.language !== StudyLanguages.language;
      return `<div class="notebook-entry"><button class="notebook-jump" data-notebook-jump="${escapeHTML(entry.id)}" ${!active.has(entry.id) && !otherLanguage ? 'disabled' : ''}><small>${labels[entry.type]} · ${{ en: 'English', fr: 'Français', mg: 'Malagasy' }[entry.language]}${!active.has(entry.id) && !otherLanguage ? ' · text updated' : ''}</small><span>${escapeHTML(entry.quote.slice(0, 180))}${entry.quote.length > 180 ? '…' : ''}</span></button><button class="text-button" data-notebook-remove="${escapeHTML(entry.id)}" aria-label="Remove ${labels[entry.type].toLowerCase()}">Remove</button></div>`;
    }).join('') : '<p class="notebook-empty">No entries yet.</p>';
    document.getElementById('studyMarks').innerHTML = list(data.entries.filter(entry => entry.type !== 'bookmark'));
    document.getElementById('studyBookmarks').innerHTML = list(data.entries.filter(entry => entry.type === 'bookmark'));
  }
  function redraw() {
    if (!StudyLanguages.displayed || studyID !== state.currentPost?.id) return;
    const scroll = els.scroll.scrollTop;
    renderArticleText(StudyLanguages.displayed);
    applyMarks(); renderLists(); els.scroll.scrollTop = scroll;
    selection = null; updateTools();
  }
  function visiblePassage() {
    const top = els.scroll.getBoundingClientRect().top + 110;
    const paragraphs = [...body().children];
    const paragraph = paragraphs.find(element => element.getBoundingClientRect().bottom > top) || paragraphs[paragraphs.length - 1];
    if (!paragraph) return null;
    const range = document.createRange(); range.selectNodeContents(body()); range.setEndBefore(paragraph);
    const start = range.toString().length;
    const quote = paragraph.textContent.slice(0, 180);
    return { start, end: start + quote.length, quote };
  }
  function add(type) {
    if (!StudyLanguages.displayed || studyID !== state.currentPost?.id) return;
    const anchor = selection || (type === 'bookmark' ? visiblePassage() : null);
    if (!anchor?.quote.trim()) return;
    if (data.entries.some(entry => entry.type === type && entry.language === StudyLanguages.language && entry.fingerprint === fingerprint && entry.start === anchor.start && entry.end === anchor.end)) {
      showToast('This passage is already marked.'); return;
    }
    data.entries.push({ ...anchor, id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`, type, language: StudyLanguages.language, fingerprint });
    const saved = persist(); redraw();
    if (saved) showToast(`${labels[type]} saved.`);
  }
  function toggle(open = document.getElementById('studyNotebook').hidden) {
    document.getElementById('studyNotebook').hidden = !open;
    document.getElementById('studyNotes').setAttribute('aria-expanded', String(open));
    if (open) document.getElementById('studyNote').focus({ preventScroll: true });
  }
  let pendingJump = null;
  function jump(id) {
    const entry = data.entries.find(item => item.id === id);
    if (!entry) return;
    if (entry.language !== StudyLanguages.language) { pendingJump = id; StudyLanguages.set(entry.language); return; }
    const element = [...body().querySelectorAll('[data-mark-ids]')].find(span => span.dataset.markIds.split(' ').includes(id));
    if (element) { toggle(false); element.scrollIntoView({ block: 'center' }); }
  }
  document.addEventListener('gospel:study-opening', event => {
    if (studyID !== event.detail.id) {
      studyID = event.detail.id;
      const stored = storedJSON(key(), {});
      data = { note: typeof stored.note === 'string' ? stored.note : '', entries: Array.isArray(stored.entries) ? stored.entries.filter(entry => labels[entry.type] && ['en', 'fr', 'mg'].includes(entry.language) && typeof entry.quote === 'string') : [] };
      document.getElementById('studyNote').value = data.note;
      document.getElementById('noteStatus').textContent = data.note ? 'Saved on this device.' : 'Notes save automatically.';
      pendingJump = null;
    }
    selection = null; fingerprint = ''; updateTools(); renderLists();
  });
  document.addEventListener('gospel:study-rendered', () => {
    fingerprint = sourceFingerprint(body().textContent);
    selection = null; applyMarks(); renderLists(); updateTools();
    if (pendingJump) { const id = pendingJump; pendingJump = null; jump(id); }
  });
  document.addEventListener('selectionchange', captureSelection);
  document.querySelectorAll('[data-annotation]').forEach(button => {
    button.addEventListener('mousedown', event => event.preventDefault());
    button.addEventListener('click', () => add(button.dataset.annotation));
  });
  document.getElementById('studyNotes').addEventListener('click', () => toggle());
  document.getElementById('closeNotebook').addEventListener('click', () => toggle(false));
  document.getElementById('studyNote').addEventListener('input', event => { data.note = event.target.value; persist(); });
  document.getElementById('studyNotebook').addEventListener('click', event => {
    const remove = event.target.closest('[data-notebook-remove]');
    if (remove) { data.entries = data.entries.filter(entry => entry.id !== remove.dataset.notebookRemove); persist(); redraw(); }
    const button = event.target.closest('[data-notebook-jump]');
    if (button) jump(button.dataset.notebookJump);
  });
  return { captureSelection, add, toggle, get entries() { return data.entries; } };
})();
