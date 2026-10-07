/* Study versions are separate from the immutable English archive. */
const StudyLanguages = (() => {
  const names = { en: 'English', fr: 'Français', mg: 'Malagasy' };
  const labels = {
    en: { loading: 'Preparing this study…', status: 'Original English study', retry: 'Retry translation', failed: 'Translation interrupted. Completed sections are saved. Retry to resume or check Translation progress.', select: 'Select all text', copy: 'Copy study' },
    fr: { loading: 'Traduction de l’étude en cours…', status: 'Traduction automatique · enregistrée pour la lecture hors ligne', retry: 'Réessayer', failed: 'Traduction interrompue. La progression est conservée. Réessayez ou consultez la progression des traductions.', select: 'Tout sélectionner', copy: 'Copier l’étude' },
    mg: { loading: 'Adika ny fianarana…', status: 'Dika mandeha ho azy · voatahiry ho vakina tsy misy Internet', retry: 'Andramo indray', failed: 'Tapaka ny fandikana. Voatahiry ny fandrosoana. Andramo indray na jereo ny fandrosoan’ny fandikana.', select: 'Safidio ny lahatsoratra rehetra', copy: 'Adikao ny fianarana' }
  };
  let language = ['en', 'fr', 'mg'].includes(localStorage.getItem('gw-study-language')) ? localStorage.getItem('gw-study-language') : 'en';
  let generation = 0;
  let displayed = null;
  const catalogs = { fr: new Map(), mg: new Map() };
  const catalogRevisions = {};
  let libraryStatus = null, libraryPolling = null, libraryTimer = null;
  let dbPromise;
  function database() {
    if (!dbPromise) dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open('gw-study-versions', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('versions', { keyPath: 'key' });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return dbPromise;
  }
  async function cache(action, value) {
    try {
      const db = await database();
      return await new Promise((resolve, reject) => {
        const transaction = db.transaction('versions', action === 'get' ? 'readonly' : 'readwrite');
        const request = transaction.objectStore('versions')[action](value);
        transaction.oncomplete = () => resolve(request.result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      });
    } catch (_) { return null; } // The server also persists complete translations.
  }
  function syncControls() {
    document.querySelectorAll('[data-study-language]').forEach(button => {
      const active = button.dataset.studyLanguage === language;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    for (const [id, label] of [['studySelectAll', 'select'], ['studyCopy', 'copy']]) {
      const button = document.getElementById(id);
      if (button) { button.textContent = labels[language][label]; button.disabled = !displayed; }
    }
    document.getElementById('translationRetry').textContent = labels[language].retry;
    renderLibraryStatus();
  }
  function metadata(post) {
    const version = catalogs[language]?.get(post.id);
    return version ? { ...post, title: version.title, subtitle: version.subtitle, translationExcerpt: version.excerpt, translationLanguage: language, translationReady: true } : { ...post, translationLanguage: language, translationReady: language === 'en' };
  }
  function refreshMetadataViews() {
    if (!state.ready) return;
    renderGrid(); renderToday(); renderArchiveGuide();
    if (state.currentPost) renderRelated(state.currentPost);
  }
  async function loadCatalog(code, revision, force = false) {
    if (code === 'en' || (!force && catalogRevisions[code] === revision)) return;
    try {
      const result = await fetchJSON(`/api/studies/translations/catalog?language=${code}`);
      catalogs[code] = new Map(result.entries.map(entry => [String(entry.id), entry]));
      catalogRevisions[code] = revision;
      await cache('put', { key: `catalog:${code}`, entries: result.entries });
      if (language === code) refreshMetadataViews();
    } catch (_) { /* Keep locally available metadata if the service is offline. */ }
  }
  function renderLibraryStatus() {
    const label = document.getElementById('libraryLanguageStatus');
    if (!label) return;
    let total = libraryStatus?.total || 0;
    try { if (!total) total = state.posts.length; } catch (_) { /* Archive script has not initialized yet. */ }
    const ready = libraryStatus?.ready?.[language] ?? catalogs[language]?.size ?? 0;
    label.textContent = language === 'en' ? 'Original English library' : `${names[language]} · ${ready.toLocaleString()} / ${total ? total.toLocaleString() : '—'} ready${libraryStatus?.enabled ? ' · preparing all studies' : ''}`;
    for (const [code, prefix] of [['fr', 'french'], ['mg', 'malagasy']]) {
      const count = libraryStatus?.ready?.[code] ?? catalogs[code].size;
      document.getElementById(`${prefix}ReadyCount`).textContent = `${count.toLocaleString()} / ${total ? total.toLocaleString() : '—'}`;
      const progress = document.getElementById(`${prefix}ReadyProgress`);
      progress.max = total || 1; progress.value = count;
    }
    const mode = libraryStatus?.state;
    document.getElementById('translationLibraryState').textContent = ({ complete: 'Both language libraries are ready.', paused: 'Preparation is paused.', waiting: 'Waiting to resume preparation.', preparing: libraryStatus?.engine === 'local' ? 'Preparing all studies locally · no internet needed.' : 'Preparing all studies, one complete version at a time.', loading: 'Opening the translation queue…' })[mode] || 'Translation service is connecting…';
    const current = libraryStatus?.current;
    document.getElementById('translationCurrentStudy').textContent = current ? `${names[current.language]} · ${current.title}` : '';
    document.getElementById('translationChunkProgress').textContent = current?.totalChunks ? `${current.completedChunks || 0} / ${current.totalChunks} text sections prepared · saved progress resumes automatically` : '';
    document.getElementById('translationLibraryError').textContent = libraryStatus?.error ? `${libraryStatus.error}${libraryStatus.nextRetry ? ` Next retry: ${new Date(libraryStatus.nextRetry * 1000).toLocaleTimeString()}.` : ''}` : '';
    document.getElementById('translationLibraryToggle').textContent = libraryStatus?.enabled === false ? 'Resume preparation' : 'Pause preparation';
    document.getElementById('translationLibraryToggle').disabled = !libraryStatus;
  }
  async function pollLibrary() {
    if (libraryPolling) return libraryPolling;
    libraryPolling = (async () => {
      try {
        libraryStatus = await fetchJSON('/api/studies/translations/status');
        await loadCatalog(language, libraryStatus.catalogRevision);
      } catch (_) { /* Reading cached studies stays available. */ }
      renderLibraryStatus();
    })();
    try { return await libraryPolling; } finally { libraryPolling = null; }
  }
  async function startLibrary() {
    for (const code of ['fr', 'mg']) {
      const cached = await cache('get', `catalog:${code}`);
      if (cached?.entries) catalogs[code] = new Map(cached.entries.map(entry => [String(entry.id), entry]));
    }
    refreshMetadataViews();
    await pollLibrary();
    if (!libraryTimer) libraryTimer = setInterval(pollLibrary, 5000);
  }
  function render(post, code) {
    displayed = { ...post, language: code };
    document.getElementById('articleTitle').textContent = post.title;
    document.getElementById('articleSubtitle').textContent = post.subtitle || excerptFor(post);
    document.getElementById('articleReadTime').textContent = `${readMinutes(post.text)} min`;
    document.querySelector('.reading-paper').lang = code;
    document.getElementById('articleBody').hidden = false;
    document.getElementById('articleBody').setAttribute('aria-busy', 'false');
    renderArticleText(post);
    document.title = `${post.title} — Gospel Warrior`;
    document.dispatchEvent(new CustomEvent('gospel:study-rendered', { detail: displayed }));
    syncControls();
  }
  async function open(post, retry = false) {
    const ticket = ++generation, code = language;
    const current = () => ticket === generation && state.currentPost?.id === post.id;
    displayed = null;
    document.dispatchEvent(new CustomEvent('gospel:study-opening', { detail: post }));
    syncControls();
    const status = document.getElementById('translationStatus');
    const retryButton = document.getElementById('translationRetry');
    retryButton.hidden = true;
    if (code === 'en') { status.textContent = labels.en.status; render(post, 'en'); return; }
    status.textContent = labels[code].loading;
    document.getElementById('articleTitle').textContent = names[code];
    document.getElementById('articleSubtitle').textContent = '';
    document.getElementById('articleBody').hidden = true;
    document.getElementById('articleBody').setAttribute('aria-busy', 'true');
    document.getElementById('articleToc').hidden = true;
    const key = `${post.id}:${code}`;
    const source = JSON.stringify([post.title, post.subtitle || '', post.text]);
    const cached = await cache('get', key);
    if (!current()) return;
    if (cached?.source === source) {
      status.textContent = labels[code].status; render({ ...post, ...cached.study }, code); return;
    }
    try {
      const deadline = Date.now() + 480000;
      let retryRequest = retry;
      while (current() && Date.now() < deadline) {
        const result = await fetchJSON('/api/studies/translation', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: post.id, language: code, retry: retryRequest })
        }, 30000);
        retryRequest = false;
        if (!current()) return;
        if (result.state === 'ready' && result.study?.text) {
          await cache('put', { key, source, study: result.study });
          if (!current()) return;
          status.textContent = labels[code].status;
          render({ ...post, ...result.study }, code);
          await loadCatalog(code, null, true); pollLibrary(); return;
        }
        if (result.state === 'error') {
          if (!result.retryable) throw new Error(result.error);
          status.textContent = `${labels[code].loading} · ${code === 'fr' ? 'Nouvelle tentative automatique, progression conservée.' : 'Andramana indray ho azy, voatahiry ny fandrosoana.'}`;
          retryRequest = true;
          await new Promise(resolve => setTimeout(resolve, 15000));
          continue;
        }
        if (result.totalChunks) status.textContent = `${labels[code].loading} ${result.completedChunks || 0} / ${result.totalChunks}`;
        await new Promise(resolve => setTimeout(resolve, 1200));
      }
      if (current()) throw new Error('Translation timed out');
    } catch (_) {
      if (!current()) return;
      status.textContent = labels[code].failed;
      document.getElementById('articleBody').setAttribute('aria-busy', 'false');
      retryButton.hidden = false;
    }
  }
  function set(code) {
    if (!['en', 'fr', 'mg'].includes(code) || code === language) return;
    language = code; localStorage.setItem('gw-study-language', code); syncControls();
    if (state.currentPost) { saveReadingPosition(); open(state.currentPost); }
    refreshMetadataViews();
    loadCatalog(code, libraryStatus?.catalogRevision, true);
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-study-language]');
    if (button) set(button.dataset.studyLanguage);
    const browse = event.target.closest('[data-open-language]');
    if (browse) { set(browse.dataset.openLanguage); showView('library'); }
    if (event.target.closest('#translationRetry') && state.currentPost) open(state.currentPost, true);
  });
  document.getElementById('translationLibraryToggle').addEventListener('click', async () => {
    try {
      libraryStatus = await fetchJSON('/api/studies/translations/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !libraryStatus.enabled }) });
      renderLibraryStatus();
    } catch (_) { showToast('Could not change translation preparation. Please retry.'); }
  });
  document.addEventListener('gospel:archive-refreshed', pollLibrary);
  window.addEventListener('beforeunload', () => clearInterval(libraryTimer));
  syncControls();
  return { open, set, syncControls, startLibrary, pollLibrary, metadata, cancel: () => { generation++; displayed = null; }, get displayed() { return displayed; }, get language() { return language; } };
})();
