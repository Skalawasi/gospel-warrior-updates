(async () => {
  const checks = [];
  const assert = (condition, label) => { if (!condition) throw new Error(label); checks.push(label); };
  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  const luminance = colour => {
    const channels = colour.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => { value /= 255; return value <= .04045 ? value / 12.92 : Math.pow((value + .055) / 1.055, 2.4); });
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  const contrast = (left, right) => { const a = luminance(left), b = luminance(right); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); };
  const eventually = async (condition, label) => {
    const deadline = Date.now() + 60000;
    while (Date.now() < deadline) {
      await pollUpdateStatus({ force: true });
      if (condition()) { checks.push(label); return; }
      await wait(200);
    }
    throw new Error(`${label} (loaded ${state.posts.length}; service total ${syncState.status?.currentTotal}; state ${syncState.status?.state}; running ${syncState.status?.updateInProgress}; error ${syncState.status?.error || 'none'})`);
  };
  try {
    const phase = window.gospelTestPhase;
    assert(state.ready && state.posts.length > (phase >= 3 ? 19 : 3800), 'Study archive loaded in native WebKit');
    assert(typeof DecompressionStream === 'undefined', 'Older-Safari compression compatibility');
    assert(document.querySelector('#studyTotal').textContent === String(state.posts.length), 'Complete local library count');
    assert(!state.posts.some(post => String(post.id) === '28949692034615161' || /52nd birthday/i.test(post.title)), 'Personal birthday post remains excluded');
    assert(!state.posts.some(post => /\b(?:subscrib(?:e|ing|ers?)|Gospel Warrior Library|50%\s+(?:discount|off)|share it to your Facebook profile|follow brother john(?:['’]s)? (?:for|(?:official )?page))\b|@followers|facebook\.com\/profile\.php/i.test(`${post.title}\n${post.subtitle}\n${post.text}`)), 'Study text and previews contain no subscription, library, discount, or social-media promotions');
    assert(!document.querySelector('img[src="assets/profile.jpg"]'), 'Personal portraits remain absent');
    assert(document.querySelector('.sidebar-nav') && getComputedStyle(document.body).overflow === 'hidden', 'App sidebar and independently scrolling workspace');
    assert(syncState.apiAvailable === true && syncState.status.intervalMinutes === 15, '15-minute update service connected');
    if (phase === 1) {
      clearAll(); showView('library');
      const search = document.querySelector('#searchInput');
      search.value = 'Moses'; search.dispatchEvent(new Event('input', { bubbles: true }));
      assert(filteredPosts().length > 0 && filteredPosts().length < state.posts.length, 'Full archive search works');
      clearAll(); openSettings('library');
      assert(!document.querySelector('#settingsPanel').hidden && !document.querySelector('#librarySettings').hidden, 'Dedicated library settings');
      const change = (id, value) => { const element = document.getElementById(id); element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })); };
      change('sortOrder', 'az');
      let posts = filteredPosts();
      assert(posts.every((post, i) => !i || posts[i - 1].title.localeCompare(post.title) <= 0), 'A–Z sorting');
      change('bibleShelf', 'old'); change('bookFilter', 'Genesis'); posts = filteredPosts();
      assert(posts.length > 1 && posts.every(post => post.bibleBooks.includes('Genesis')), 'Bible book and testament filters');
      resetSettings(); change('characterFilter', 'Moses');
      assert(filteredPosts().length > 0 && filteredPosts().every(post => post.biblicalCharacters.includes('Moses')), 'Biblical character filter');
      resetSettings();
      [...document.querySelectorAll('[data-setting-topic]')].slice(0, 2).forEach(topic => { topic.checked = true; topic.dispatchEvent(new Event('change', { bubbles: true })); });
      assert(state.topicFilters.length === 2 && filteredPosts().length > 0, 'Multi-topic filtering');
      closeSettings(); posts = filteredPosts(); openStudy(posts[0].id); moveStudy(1);
      assert(state.currentPost.id === posts[1].id, 'Next study follows active filters');
      moveStudy(-1); assert(state.currentPost.id === posts[0].id, 'Previous study follows active filters');
      document.querySelector('#articleSave').click();
      assert(state.saved.has(posts[0].id), 'Save a study');
      localStorage.setItem('gw-self-test-id', posts[0].id);
      document.querySelector('#readerTheme').click(); document.querySelector('[data-font=up]').click();
      assert(state.darkMode && state.fontSize === 20, 'Dark appearance and reading size');
      closeStudy(); resetSettings(); change('sortOrder', 'az');
      openSettings('updates');
      assert(document.querySelector('#automaticChecks').checked && document.querySelector('#automaticRefresh').checked, 'Automatic checks and refresh enabled by default');
      document.querySelector('#automaticRefresh').click();
      await eventually(() => !syncState.settingsBusy && !syncState.autoRefresh, 'Automatic-refresh switch persists through the real API');
      assert(!document.querySelector('#updatesAutoRefresh').checked, 'Update controls stay synchronized');
      document.querySelector('#automaticRefresh').click();
      await eventually(() => !syncState.settingsBusy && syncState.autoRefresh, 'Automatic refresh can be restored');
      closeSettings(); showView('bible');
      document.querySelector('[data-archive-book="Genesis"]').click();
      assert(state.view === 'library' && state.bookFilter === 'Genesis', 'Bible index navigates into matching studies');
      clearAll(); showView('home');
    } else if (phase === 2) {
      const savedID = localStorage.getItem('gw-self-test-id');
      assert(state.saved.has(savedID), 'Bookmarks survive app quit and a different service port');
      assert(state.sortOrder === 'az', 'Sorting survives relaunch');
      assert(state.darkMode && state.fontSize === 20, 'Reading preferences survive relaunch');
      assert(state.lastStudy === savedID && state.readingPositions[savedID], 'Continue-reading history survives relaunch');
      showView('saved'); openStudy(savedID);
      assert(!els.articleView.hidden && document.querySelector('#articleBody').textContent.length > 100, 'Saved study opens in the reading room');
    } else if (phase === 3) {
      await saveUpdateSettings({ enabled: true, intervalMinutes: 15, autoRefresh: true });
      clearAll(); showView('library');
      state.query = 'Jesus'; els.search.value = state.query; renderGrid(true);
      const baseCount = state.posts.length;
      const savedBefore = JSON.stringify([...state.saved]);
      const appearanceBefore = `${state.skin}/${state.colourTheme}`;
      const post = filteredPosts()[0]; openStudy(post.id); els.scroll.scrollTop = 220;
      const body = document.querySelector('#articleBody');
      const firstText = body.querySelector('p').firstChild;
      const range = document.createRange(); range.setStart(firstText, 0); range.setEnd(firstText, Math.min(12, firstText.textContent.length));
      getSelection().removeAllRanges(); getSelection().addRange(range);
      const selectedText = getSelection().toString();
      await wait(300);
      const settledPosition = els.scroll.scrollTop;
      const result = await requestUpdateCheck();
      assert(result?.started, 'Manual check uses the real archive update API');
      await eventually(() => state.posts.length === baseCount + 1, 'A newly imported Bible study automatically appears without restarting');
      assert(state.currentPost.id === post.id && document.querySelector('#articleBody') === body, 'Background refresh leaves the open study and reader DOM intact');
      assert(els.scroll.scrollTop === settledPosition && getSelection().toString() === selectedText, `Reading position and text selection survive automatic refresh (expected ${settledPosition}/${JSON.stringify(selectedText)}, got ${els.scroll.scrollTop}/${JSON.stringify(getSelection().toString())})`);
      assert(state.query === 'Jesus' && state.sortOrder === 'az' && JSON.stringify([...state.saved]) === savedBefore, 'Search, sorting, and bookmarks survive refresh');
      assert(`${state.skin}/${state.colourTheme}` === appearanceBefore && document.body.dataset.skin === state.skin && document.body.dataset.colourTheme === state.colourTheme, 'Chosen skin and colour palette survive automatic refresh');
      assert(syncState.revision === syncState.status.contentRevision && !syncState.pendingRevision, 'Archive generation acknowledged after automatic refresh');
      await saveUpdateSettings({ autoRefresh: false });
      await requestUpdateCheck();
      await eventually(() => !!syncState.pendingRevision && !syncState.status.updateInProgress, 'Manual-refresh mode advertises a newly collected study');
      assert(state.posts.length === baseCount + 1 && !document.querySelector('#newContentBanner').hidden, 'Automatic-refresh switch genuinely postpones content replacement');
      document.querySelector('#applyArchiveUpdate').click();
      await eventually(() => state.posts.length === baseCount + 2, 'Refresh-now control loads queued studies in place');
      assert(state.currentPost.id === post.id && els.scroll.scrollTop === settledPosition, 'Manual refresh also preserves the reading room');
      await saveUpdateSettings({ autoRefresh: true });
      closeStudy(); showView('updates');
    } else if (phase === 4) {
      setReadingSkin('light'); showView('home'); openSettings('updates');
      assert(!document.querySelector('#updateSettings').hidden && document.querySelector('#automaticChecks').checked && document.querySelector('#automaticRefresh').checked, 'Updates settings remain enabled after relaunch');
    } else if (phase === 5) {
      showView('library'); clearAll(); openStudy(state.posts[0].id); els.scroll.scrollTop = 220;
      const reader = document.querySelector('#articleBody');
      const wording = reader.textContent;
      const scroll = els.scroll.scrollTop;
      openSettings('reading');
      assert(document.querySelectorAll('#colourThemes [data-colour-theme]').length === 6 && document.querySelectorAll('.skin-choices [data-skin]').length === 3, 'Six colour palettes and three reading skins are available');
      for (const skin of READING_SKINS) {
        document.querySelector(`.skin-choices [data-skin="${skin}"]`).click();
        for (const theme of COLOUR_THEMES) {
          document.querySelector(`#colourThemes [data-colour-theme="${theme.id}"]`).click();
          const paper = getComputedStyle(document.querySelector('.reading-paper'));
          const body = getComputedStyle(reader);
          const button = getComputedStyle(document.querySelector('#heroReadButton'));
          assert(state.skin === skin && state.colourTheme === theme.id && document.body.dataset.skin === skin && document.body.dataset.colourTheme === theme.id, `${theme.name} / ${skin}: live selection`);
          assert(contrast(body.color, paper.backgroundColor) >= 4.5 && contrast(button.color, button.backgroundColor) >= 4.5, `${theme.name} / ${skin}: readable study and button contrast`);
        }
      }
      assert(reader === document.querySelector('#articleBody') && reader.textContent === wording && els.scroll.scrollTop === scroll, 'Switching appearance leaves study text and reading position intact');
      document.querySelector('#warmEveningPreset').click();
      assert(state.skin === 'dark' && state.colourTheme === 'terracotta' && getComputedStyle(document.body).backgroundColor === 'rgb(23, 20, 16)', 'Warm evening preset matches the reference charcoal-and-terracotta palette');
      assert(localStorage.getItem('gw-reading-skin') === 'dark' && localStorage.getItem('gw-colour-theme') === 'terracotta', 'Skin and colour choices are saved');
      closeSettings(); els.scroll.scrollTop = 0;
    } else if (phase === 6) {
      assert(state.skin === 'dark' && state.colourTheme === 'terracotta', 'Terracotta and dark skin survive quitting and relaunching on another port');
      showView('library'); openStudy(state.posts[0].id);
      document.querySelector('.reader-skin-control [data-skin="sepia"]').click();
      assert(state.skin === 'sepia' && !state.darkMode && state.colourTheme === 'terracotta', 'Reading-room quick controls change skin independently of the palette');
      document.querySelector('#readerTheme').click();
      assert(state.skin === 'dark', 'Dark-mode shortcut works with custom colours');
      document.querySelector('#readerTheme').click();
      assert(state.skin === 'sepia', 'Dark-mode shortcut remembers the previous sepia skin');
      setReadingSkin('dark'); closeStudy(); showView('home'); openSettings('reading');
    } else if (phase === 8) {
      showView('library'); clearAll(); StudyLanguages.set('en'); openStudy(state.posts[0].id);
      const post = state.currentPost;
      assert(document.querySelector('#libraryLanguageSwitch').getClientRects().length > 0, 'All-study language switch is visible above the workspace');
      localStorage.setItem('gw-reader-test-id', post.id);
      const body = document.querySelector('#articleBody');
      const original = body.textContent;
      const select = (start, end) => {
        const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
        const range = document.createRange(); let node, offset = 0, started = false;
        while ((node = walker.nextNode())) {
          if (!started && start <= offset + node.length) { range.setStart(node, start - offset); started = true; }
          if (end <= offset + node.length) { range.setEnd(node, end - offset); break; }
          offset += node.length;
        }
        getSelection().removeAllRanges(); getSelection().addRange(range); StudyNotebook.captureSelection();
      };
      select(5, 40); document.querySelector('#studyHighlight').click();
      select(15, 50); document.querySelector('#studyUnderline').click();
      assert(body.querySelector('.study-highlight.study-underline') && body.textContent === original, 'Overlapping highlights and underlines preserve the native study text');
      getSelection().removeAllRanges(); StudyNotebook.captureSelection(); document.querySelector('#studyPassageBookmark').click();
      assert(StudyNotebook.entries.some(entry => entry.type === 'bookmark'), 'Passage bookmark saves a source-linked anchor');
      document.querySelector('#studyNotes').click();
      const note = document.querySelector('#studyNote'); note.value = 'Native study notebook — saved reflection.'; note.dispatchEvent(new Event('input', { bubbles: true }));
      assert(JSON.parse(localStorage.getItem(`gw-study-notebook:${post.id}`)).note === note.value, 'Notes autosave through the native preferences bridge');
      assert(StudyCopy.selectAll() && getSelection().toString().includes(post.title), 'Select-all targets the study in native WebKit');
      assert(StudyCopy.fullText().includes(post.title) && StudyCopy.fullText().length >= post.text.length * .9, 'Copy includes the complete study rather than its preview');
      await StudyCopy.copy();
      const realFetch = window.fetch;
      window.fetch = (url, options) => url === '/api/studies/translation' ? Promise.resolve(new Response(JSON.stringify({ state: 'ready', study: JSON.parse(options.body).language === 'fr'
        ? { title: 'La grâce de Dieu', subtitle: 'Étude biblique', text: 'La grâce de Dieu\n\nLa grâce apporte le salut.' }
        : { title: 'Ny fahasoavan’Andriamanitra', subtitle: 'Fianarana Baiboly', text: 'Ny fahasoavan’Andriamanitra\n\nMitondra famonjena ny fahasoavana.' } }), { headers: { 'Content-Type': 'application/json' } })) : realFetch(url, options);
      try {
        StudyLanguages.set('fr'); await eventually(() => StudyLanguages.displayed?.language === 'fr', 'French version renders in native WebKit');
        assert(body.textContent.includes('apporte le salut') && !body.querySelector('.study-highlight'), 'French study wording has independent text markings');
        StudyLanguages.set('mg'); await eventually(() => StudyLanguages.displayed?.language === 'mg', 'Malagasy version renders in native WebKit');
        assert(body.textContent.includes('Mitondra famonjena') && StudyCopy.fullText().includes('Mitondra famonjena'), 'Malagasy study selection and copy use the translated version');
        StudyLanguages.set('fr'); await eventually(() => StudyLanguages.displayed?.language === 'fr', 'Saved French version reloads from IndexedDB');
      } finally { window.fetch = realFetch; StudyLanguages.set('en'); }
      assert(body.textContent === original && body.querySelector('.study-highlight'), 'English wording and annotations return after language switching');
      showView('scripture'); await KJVBible.go(0, 1, 1, false, 'kjv');
      assert(document.querySelectorAll('.bible-verse').length === 31, 'Native Bible reader loads Genesis through HTTP gzip without DecompressionStream');
      const god = document.querySelector('#kjv-verse-1 [data-strongs="H430"]'); god.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      assert(!document.querySelector('#bibleWordTooltip').hidden && document.querySelector('#bibleWordTooltip').textContent.includes('אֱלֹהִים'), 'Hebrew lemma and dictionary meaning appear on hover');
      await KJVBible.go(42, 1, 1, false);
      const word = document.querySelector('#kjv-verse-1 [data-strongs~="G3056"]'); word.focus();
      assert(document.querySelector('#bibleWordDetails').textContent.includes('λόγος'), 'Keyboard-focused KJV word displays its verse-specific Greek lemma');
      await KJVBible.setVersion('mg');
      assert(document.querySelector('#bibleChapterTitle').textContent === 'Jaona 1' && document.querySelector('#bibleVerses').textContent.includes('Andriamanitra'), 'Published Malagasy Bible loads offline at the selected chapter');
      assert(!document.querySelector('#bibleVerses .bible-word') && document.querySelector('#bibleWordPanel').hidden, 'Malagasy version has no invented word mappings');
      closeSettings(); showView('translations');
      await StudyLanguages.pollLibrary();
      await eventually(() => document.querySelector('#frenchReadyCount').textContent.includes(String(state.posts.length)), 'Translation coverage reports the active library size');
      assert(document.querySelector('#translationLibraryToggle').textContent === 'Resume preparation', 'Full-library preparation can remain paused in an isolated verification profile');
      showView('home');
    } else if (phase === 9) {
      const id = localStorage.getItem('gw-reader-test-id');
      openStudy(id);
      assert(document.querySelector('#studyNote').value === 'Native study notebook — saved reflection.', 'Study notes survive native relaunch on a new service port');
      assert(document.querySelector('.study-highlight.study-underline') && StudyNotebook.entries.some(entry => entry.type === 'bookmark'), 'Highlights, underlines and passage bookmarks survive native relaunch');
      assert(StudyLanguages.language === 'en' && KJVBible.version === 'mg', 'Study and Bible language choices persist independently');
      showView('scripture'); await KJVBible.open();
      assert(document.querySelector('#bibleChapterTitle').textContent === 'Jaona 1', 'Malagasy Bible version and reading location survive native relaunch');
      await KJVBible.reference('Genesisy 1:1');
      assert(document.querySelector('#bibleChapterTitle').textContent === 'Genesisy 1', 'Native passage search accepts Malagasy book names');
      await KJVBible.setVersion('kjv');
      assert(document.querySelector('#bibleChapterTitle').textContent === 'Genesis 1', 'Version switch returns to matching KJV passage');
    } else if (phase === 7) {
      assert(state.skin === 'dark' && state.colourTheme === 'terracotta', 'Appearance preferences persist after content imports and another relaunch');
      showView('home'); openSettings('reading');
      assert(document.querySelector('#colourThemes [data-colour-theme="terracotta"]').getAttribute('aria-pressed') === 'true' && document.querySelector('.skin-choices [data-skin="dark"]').getAttribute('aria-pressed') === 'true', 'Settings correctly identify the selected palette and skin');
      assert(syncState.status.autoRefresh && syncState.status.intervalMinutes === 15, 'Appearance choices retain 15-minute updates and automatic refresh');
    }
    assert(document.documentElement.scrollWidth <= innerWidth + 1 && els.scroll.scrollWidth <= els.scroll.clientWidth + 1, 'Workspace stays within the app window');
    assert([...document.querySelectorAll('img')].filter(image => image.loading !== 'lazy').every(image => !image.complete || image.naturalWidth > 0), 'Local interface artwork loads');
    window.gospelTestReport = { ok: true, phase, studies: state.posts.length, checks };
  } catch (error) { window.gospelTestReport = { ok: false, error: error.message, checks }; }
})();
void 0;
