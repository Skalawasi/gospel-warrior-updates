/* Offline KJV reader. Every lookup follows this verse's OSIS Strong's links. */
const KJVBible = (() => {
  let index = null, lexicon = null, loading = null, book = null, generation = 0;
  let version = localStorage.getItem('gw-bible-version') === 'mg' ? 'mg' : 'kjv';
  const manifests = {};
  const books = new Map();
  const saved = storedJSON('gw-kjv-location', {});
  let location = { book: Number.isInteger(saved.book) ? Math.max(0, Math.min(65, saved.book)) : 0, chapter: Number(saved.chapter) || 1, verse: Number(saved.verse) || 1 };
  let activeWord = null, pinned = false, hideTimer;
  const tooltip = document.getElementById('bibleWordTooltip');
  const aliases = ['Gen', 'Exod Ex', 'Lev', 'Num', 'Deut Dt', 'Josh', 'Judg', 'Ruth', '1Sam 1Sm', '2Sam 2Sm', '1Kgs 1Ki', '2Kgs 2Ki', '1Chr', '2Chr', 'Ezra', 'Neh', 'Esth', 'Job', 'Ps Psalm Psa', 'Prov Pr', 'Eccl', 'Song SongofSongs SongofSolomon Cant', 'Isa', 'Jer', 'Lam', 'Ezek', 'Dan', 'Hos', 'Joel', 'Amos', 'Obad', 'Jonah', 'Mic', 'Nah', 'Hab', 'Zeph', 'Hag', 'Zech', 'Mal', 'Matt Mt', 'Mark Mk', 'Luke Lk', 'John Jn', 'Acts', 'Rom', '1Cor', '2Cor', 'Gal', 'Eph', 'Phil', 'Col', '1Thess 1Th', '2Thess 2Th', '1Tim 1Ti', '2Tim 2Ti', 'Titus', 'Phlm Philemon', 'Heb', 'Jas Jam', '1Pet 1Pt', '2Pet 2Pt', '1John 1Jn', '2John 2Jn', '3John 3Jn', 'Jude', 'Rev'];
  const normalize = text => text.toLowerCase().replace(/[\s.]/g, '');
  async function compressedJSON(file) {
    const response = await fetch(`assets/bible/${file}`);
    if (!response.ok) throw new Error('Bible data unavailable');
    if (response.headers.get('x-gospel-warrior-plain-json') === 'true' || (response.headers.get('content-encoding') || '').includes('gzip')) return response.json();
    if (typeof DecompressionStream === 'undefined') throw new Error('Use the full app service for this Bible.');
    return new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).json();
  }
  async function ensureData() {
    if (manifests.kjv && manifests.mg && lexicon) return;
    if (!loading) loading = Promise.all([fetchJSON('assets/bible/index.json'), fetchJSON('assets/bible/mg/index.json'), compressedJSON('lexicon.json.gz')]).then(([manifest, malagasy, dictionary]) => {
      if (manifest.books.length !== 66 || malagasy.books.length !== 66) throw new Error('Incomplete Bible');
      manifests.kjv = manifest; manifests.mg = malagasy; lexicon = dictionary;
    }).finally(() => { loading = null; });
    return loading;
  }
  function status(message, failed = false) {
    document.getElementById('bibleStatus').textContent = message;
    document.getElementById('bibleRetry').hidden = !failed;
  }
  function controls(busy) {
    for (const id of ['kjvBook', 'kjvChapter', 'kjvVerse', 'kjvPrevious', 'kjvNext']) document.getElementById(id).disabled = busy;
    if (!busy && index) {
      document.getElementById('kjvPrevious').disabled = location.book === 0 && location.chapter === 1;
      document.getElementById('kjvNext').disabled = location.book === 65 && location.chapter === index.books[65].chapters;
    }
    document.getElementById('bibleVerses').setAttribute('aria-busy', String(busy));
  }
  function dismiss() {
    clearTimeout(hideTimer);
    if (activeWord) activeWord.removeAttribute('aria-describedby');
    activeWord = null; pinned = false; tooltip.hidden = true;
  }
  function render() {
    dismiss();
    const metadata = index.books[location.book];
    const malagasy = version === 'mg';
    document.querySelectorAll('[data-bible-version]').forEach(button => { const active = button.dataset.bibleVersion === version; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
    document.getElementById('bibleReaderTitle').textContent = malagasy ? 'Baiboly Malagasy (1865)' : 'King James Bible';
    document.getElementById('bibleReaderHint').textContent = malagasy ? 'Vakio ny Baiboly amin’ny teny Malagasy. Afaka mifamadika amin’ny KJV amin’ity toko ity ianao.' : 'Hover over a word for its Hebrew or Greek dictionary meaning. Click or focus a word to explore it.';
    document.querySelector('.bible-paper').lang = malagasy ? 'mg' : 'en';
    document.querySelector('.bible-reader-layout').classList.toggle('malagasy-bible', malagasy);
    document.getElementById('bibleWordPanel').hidden = malagasy;
    document.getElementById('malagasyWordStudy').hidden = !malagasy;
    document.getElementById('bibleVersionNote').textContent = malagasy ? 'Baiboly Malagasy (1865) · Public-domain published translation. Hebrew/Greek word meanings are available in the KJV version. Verse numbers follow this edition; empty source numbering slots are labelled.' : 'Meanings come from the verse’s Strong’s numbers. A phrase may link to more than one original word. Italics indicate words added by the KJV translators.';
    document.getElementById('kjvBook').innerHTML = index.books.map((item, i) => `<option value="${i}">${escapeHTML(item.name)}</option>`).join('');
    document.getElementById('kjvBook').value = location.book;
    document.getElementById('kjvChapter').innerHTML = Array.from({ length: metadata.chapters }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join('');
    document.getElementById('kjvChapter').value = location.chapter;
    const verses = book.chapters[location.chapter - 1];
    document.getElementById('kjvVerse').innerHTML = verses.map(verse => `<option value="${verse.number}">${verse.number}</option>`).join('');
    document.getElementById('kjvVerse').value = location.verse;
    document.getElementById('bibleChapterTitle').textContent = `${book.name} ${location.chapter}`;
    document.getElementById('bibleVerses').innerHTML = verses.map(verse => `<p class="bible-verse${verse.number === location.verse ? ' current-verse' : ''}" id="kjv-verse-${verse.number}"><sup>${verse.number}</sup> ${malagasy ? (verse.textUnavailable ? '<span class="source-verse-placeholder">[Tsy misy lahatsoratra amin’ity laharana ity ao amin’ny dikan-teny 1865.]</span>' : escapeHTML(verse.text)) : verse.tokens.map(([text, codes, added]) => {
      if (!text.trim()) return escapeHTML(text);
      return `<span class="bible-word${added ? ' translator-added' : ''}${codes.length ? ' indexed-word' : ''}" data-strongs="${escapeHTML(codes.join(' '))}" data-added="${added}" tabindex="${codes.length || added ? '0' : '-1'}" ${codes.length ? 'aria-label="' + escapeHTML(text.trim()) + ': original-language dictionary"' : ''}>${escapeHTML(text)}</span>`;
    }).join('')}</p>`).join('');
    document.getElementById('bibleWordDetails').innerHTML = '<p>Hover, click, or keyboard-focus a word in the passage to see its original-language entry.</p>';
    status(`${metadata.name} ${location.chapter} · ${verses.length} ${malagasy ? 'andininy · Baiboly Malagasy (1865) · azo vakina tsy misy Internet' : 'verses · Hebrew/Greek dictionary available offline'}`);
    controls(false);
    localStorage.setItem('gw-kjv-location', JSON.stringify(location));
    localStorage.setItem('gw-bible-version', version);
    document.title = `${metadata.name} ${location.chapter} — ${malagasy ? 'Malagasy 1865' : 'KJV'} — Gospel Warrior`;
    if (location.verse > 1) requestAnimationFrame(() => document.getElementById(`kjv-verse-${location.verse}`)?.scrollIntoView({ block: 'center' }));
  }
  async function go(bookIndex, chapter = 1, verse = 1, push = true, code = version) {
    const ticket = ++generation;
    version = code === 'mg' ? 'mg' : 'kjv';
    controls(true); status('Opening the local Bible and dictionaries…');
    try {
      await ensureData();
      if (ticket !== generation) return;
      index = manifests[version];
      const metadata = index.books[bookIndex];
      if (!Number.isInteger(bookIndex) || !metadata || !Number.isInteger(chapter) || chapter < 1 || chapter > metadata.chapters ||
          !Number.isInteger(verse) || verse < 1 || verse > metadata.verses[chapter - 1]) throw new Error('That passage does not exist. Check the book, chapter, and verse.');
      const cacheKey = `${version}:${bookIndex}`;
      let loaded = books.get(cacheKey);
      if (!loaded) {
        loaded = await compressedJSON(metadata.file);
        books.set(cacheKey, loaded);
        if (books.size > 4) books.delete(books.keys().next().value);
      }
      if (ticket !== generation) return;
      location = { book: bookIndex, chapter, verse }; book = loaded;
      render();
      if (push && state.view === 'scripture') history.pushState({}, '', `#bible=${version}:${bookIndex + 1}.${chapter}.${verse}`);
    } catch (error) {
      if (ticket !== generation) return;
      controls(false); status(error.message || 'Could not load the Bible. Retry the local app service.', true);
    }
  }
  async function open() {
    await go(location.book, location.chapter, location.verse, false);
  }
  async function setVersion(code) {
    if (!['kjv', 'mg'].includes(code) || code === version) return;
    version = code;
    const ticket = ++generation;
    controls(true);
    try {
      await ensureData();
      if (ticket !== generation) return;
      const metadata = manifests[code].books[location.book];
      const chapter = Math.min(location.chapter, metadata.chapters);
      const verse = Math.min(location.verse, metadata.verses[chapter - 1]);
      await go(location.book, chapter, verse, true, code);
    } catch (error) { if (ticket === generation) { controls(false); status(error.message, true); } }
  }
  async function reference(text) {
    try {
      await ensureData();
      index = manifests[version];
      const match = text.trim().match(/^(.+?)\s*(\d+)(?::(\d+)(?:[-–]\d+)?)?$/);
      if (!match) throw new Error('Use a reference such as John 3:16 or Psalm 23.');
      const name = normalize(match[1]);
      const bookIndex = index.books.findIndex((item, i) => [item.name, manifests.kjv.books[i].name, manifests.mg.books[i].name].some(label => normalize(label) === name) || aliases[i].split(' ').some(alias => normalize(alias) === name));
      const chapter = Number(match[2]), verse = Number(match[3] || 1);
      if (bookIndex < 0 || chapter < 1 || chapter > index.books[bookIndex].chapters || verse > index.books[bookIndex].verses[chapter - 1]) throw new Error('That passage does not exist. Check the book, chapter, and verse.');
      if (state.view !== 'scripture' || state.currentPost) showView('scripture', { push: false });
      await go(bookIndex, chapter, verse);
    } catch (error) { showToast(error.message); status(error.message); }
  }
  function dictionaryHTML(word) {
    const codes = word.dataset.strongs.split(' ').filter(Boolean);
    const heading = `<h3>${escapeHTML(word.textContent.trim())}</h3>`;
    if (!codes.length) return heading + `<p>${word.dataset.added === 'true' ? 'Added by the KJV translators to complete the English sense; no separate Hebrew or Greek word is linked.' : 'No separate Strong’s entry is linked to this word in the source text.'}</p>`;
    return heading + codes.map(code => {
      const entry = lexicon[code];
      const language = code[0] === 'H' ? 'Hebrew / Aramaic' : 'Greek';
      if (!entry) return `<section><small>${escapeHTML(code)} · ${language}</small><p>Dictionary entry unavailable.</p></section>`;
      return `<section><small>${escapeHTML(code)} · ${language}</small><div class="original-word" lang="${code[0] === 'H' ? 'he' : 'el'}" dir="auto">${escapeHTML(entry.lemma)}</div><p class="transliteration">${escapeHTML(entry.transliteration)}${entry.pronunciation ? ' · ' + escapeHTML(entry.pronunciation) : ''}</p><p>${escapeHTML(entry.meaning)}</p>${entry.kjv ? `<p class="dictionary-renderings"><strong>KJV renderings:</strong> ${escapeHTML(entry.kjv)}</p>` : ''}${entry.derivation ? `<p class="dictionary-derivation">${escapeHTML(entry.derivation)}</p>` : ''}</section>`;
    }).join('');
  }
  function positionTooltip(word) {
    const rect = word.getBoundingClientRect();
    const width = Math.min(380, innerWidth - 24);
    tooltip.style.width = `${width}px`;
    tooltip.style.left = `${Math.max(12, Math.min(innerWidth - width - 12, rect.left))}px`;
    tooltip.style.top = '12px';
    const height = tooltip.getBoundingClientRect().height;
    const top = rect.bottom + height + 12 <= innerHeight ? rect.bottom + 8 : Math.max(12, rect.top - height - 8);
    tooltip.style.top = `${top}px`;
  }
  function showWord(word, pin = false) {
    if (!lexicon || version !== 'kjv' || state.view !== 'scripture' || !word) return;
    if (pinned && !pin) return;
    dismiss(); activeWord = word; pinned = pin;
    const html = dictionaryHTML(word);
    tooltip.innerHTML = html; tooltip.hidden = false;
    document.getElementById('bibleWordDetails').innerHTML = html;
    word.setAttribute('aria-describedby', 'bibleWordTooltip');
    positionTooltip(word);
  }
  function hideSoon() { clearTimeout(hideTimer); if (!pinned) hideTimer = setTimeout(dismiss, 180); }
  const verses = document.getElementById('bibleVerses');
  verses.addEventListener('mouseover', event => {
    const word = event.target.closest('.bible-word');
    if (word && !word.contains(event.relatedTarget)) showWord(word);
  });
  verses.addEventListener('mouseout', event => { if (!event.target.closest('.bible-word')?.contains(event.relatedTarget)) hideSoon(); });
  verses.addEventListener('focusin', event => showWord(event.target.closest('.bible-word')));
  verses.addEventListener('focusout', hideSoon);
  verses.addEventListener('click', event => showWord(event.target.closest('.bible-word'), true));
  verses.addEventListener('keydown', event => {
    if (['Enter', ' '].includes(event.key) && event.target.closest('.bible-word')) { event.preventDefault(); showWord(event.target.closest('.bible-word'), true); }
  });
  tooltip.addEventListener('mouseenter', () => clearTimeout(hideTimer));
  tooltip.addEventListener('mouseleave', hideSoon);
  document.getElementById('bibleWordClear').addEventListener('click', () => { dismiss(); document.getElementById('bibleWordDetails').innerHTML = '<p>Select a word to begin a word study.</p>'; });
  document.getElementById('kjvBook').addEventListener('change', event => go(Number(event.target.value)));
  document.getElementById('kjvChapter').addEventListener('change', event => go(location.book, Number(event.target.value)));
  document.getElementById('kjvVerse').addEventListener('change', event => go(location.book, location.chapter, Number(event.target.value)));
  function move(direction) {
    let nextBook = location.book, nextChapter = location.chapter + direction;
    if (nextChapter < 1) { nextBook--; nextChapter = index.books[nextBook]?.chapters; }
    else if (nextChapter > index.books[nextBook].chapters) { nextBook++; nextChapter = 1; }
    if (nextBook >= 0 && nextBook < 66) go(nextBook, nextChapter);
  }
  document.getElementById('kjvPrevious').addEventListener('click', () => move(-1));
  document.getElementById('kjvNext').addEventListener('click', () => move(1));
  document.getElementById('bibleRetry').addEventListener('click', open);
  document.getElementById('malagasyWordStudy').addEventListener('click', () => setVersion('kjv'));
  document.getElementById('bibleReferenceForm').addEventListener('submit', event => { event.preventDefault(); reference(document.getElementById('bibleReference').value); });
  document.addEventListener('click', event => {
    const versionButton = event.target.closest('[data-bible-version]');
    if (versionButton) setVersion(versionButton.dataset.bibleVersion);
    const link = event.target.closest('[data-bible-reference]');
    if (link) reference(link.dataset.bibleReference);
    if (pinned && !event.target.closest('.bible-word, #bibleWordTooltip')) dismiss();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && activeWord) { event.preventDefault(); dismiss(); }
  });
  els.scroll.addEventListener('scroll', () => { if (activeWord) dismiss(); }, { passive: true });
  window.addEventListener('resize', dismiss);
  return { open, go, reference, dismiss, setVersion, leave: () => { generation++; dismiss(); }, get version() { return version; }, get location() { return { ...location }; } };
})();
