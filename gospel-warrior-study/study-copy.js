const StudyCopy = (() => {
  function selectAll() {
    if (!state.currentPost || !StudyLanguages.displayed) return false;
    const text = document.getElementById('studyText');
    text.focus({ preventScroll: true });
    const range = document.createRange(); range.selectNodeContents(text);
    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    return true;
  }
  function fullText() {
    const post = StudyLanguages.displayed;
    if (!post) return '';
    const blocks = post.text.split(/\n\s*\n/).map(block => block.trim()).filter(Boolean);
    if (blocks[0] === post.title) blocks.shift();
    if (post.subtitle && blocks[0] === post.subtitle) blocks.shift();
    return [post.title, post.subtitle, ...blocks].filter(Boolean).join('\n\n');
  }
  async function copy() {
    const text = fullText();
    if (!text) return;
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch (_) {
      // Big Sur WebKit and browsers without clipboard permission.
      const focus = document.activeElement, scroll = els.scroll.scrollTop;
      const selection = getSelection(), ranges = [];
      for (let i = 0; i < selection.rangeCount; i++) ranges.push(selection.getRangeAt(i).cloneRange());
      const field = document.createElement('textarea');
      field.value = text; field.className = 'clipboard-fallback'; field.setAttribute('aria-label', 'Study text to copy');
      document.body.append(field); field.select();
      try { copied = document.execCommand('copy'); } catch (_) { /* Offer manual copy below. */ }
      field.remove(); focus?.focus({ preventScroll: true });
      selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range));
      els.scroll.scrollTop = scroll;
    }
    const messages = { en: 'Study copied to clipboard.', fr: 'Étude copiée dans le presse-papiers.', mg: 'Vo adika ny fianarana.' };
    if (copied) showToast(messages[StudyLanguages.language]);
    else { selectAll(); showToast('Text selected. Press ⌘C or Ctrl+C to copy.'); }
  }
  document.getElementById('studySelectAll').addEventListener('click', selectAll);
  document.getElementById('studyCopy').addEventListener('click', copy);
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'a' && state.currentPost &&
        !event.target.closest('input, textarea, [contenteditable="true"]') && document.getElementById('settingsPanel').hidden) {
      if (selectAll()) event.preventDefault();
    }
  });
  return { selectAll, copy, fullText };
})();
