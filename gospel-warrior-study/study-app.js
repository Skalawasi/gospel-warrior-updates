function storedJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (_) { return fallback; }
}

const READING_SKINS = ['light', 'sepia', 'dark'];
const COLOUR_THEMES = [
  { id: 'forest', name: 'Forest & Gold', description: 'Quiet greens, antique gold', primary: '#20382e', secondary: '#536f5f', accent: '#d4bf87', lightAccent: '#896b35', sidebar: '#20382e', dark: { paper: '#1e2822', surface: '#263229', ink: '#e1e4d5', muted: '#a2ae99', line: '#3a4437', soft: '#303c31', reading: '#d2d8c6', sidebar: '#16291f' } },
  { id: 'terracotta', name: 'Terracotta', description: 'Warm charcoal, cream & coral', primary: '#844f43', secondary: '#885547', accent: '#cf8c7b', lightAccent: '#985b49', sidebar: '#2c241c', dark: { paper: '#171410', surface: '#221e16', ink: '#eee5d3', muted: '#b6aa92', line: '#3c3528', soft: '#2c271c', reading: '#dfd5c1', sidebar: '#241f17' } },
  { id: 'midnight', name: 'Midnight Blue', description: 'Deep navy, soft silver', primary: '#253e60', secondary: '#4a6686', accent: '#a1b9dc', lightAccent: '#4c688e', sidebar: '#1c2c44', dark: { paper: '#131b27', surface: '#1a2635', ink: '#e1e9f2', muted: '#a1b2c7', line: '#354458', soft: '#223144', reading: '#d2ddec', sidebar: '#111b2b' } },
  { id: 'plum', name: 'Royal Plum', description: 'Velvet plum, gentle lavender', primary: '#563758', secondary: '#79587f', accent: '#c9a4d6', lightAccent: '#795180', sidebar: '#352338', dark: { paper: '#211924', surface: '#2c2230', ink: '#ece1ed', muted: '#bda8c1', line: '#433548', soft: '#382b3c', reading: '#dfd0e2', sidebar: '#281a2a' } },
  { id: 'olive', name: 'Olive & Honey', description: 'Earthy olive, honeyed light', primary: '#4c5534', secondary: '#646d3e', accent: '#d0bd74', lightAccent: '#80642d', sidebar: '#30351f', dark: { paper: '#202017', surface: '#28281e', ink: '#ebe8cd', muted: '#b7b490', line: '#3e3e2a', soft: '#323222', reading: '#dfdcc4', sidebar: '#1d2116' } },
  { id: 'ocean', name: 'Ocean Teal', description: 'Calm teal, sea-glass accents', primary: '#174747', secondary: '#3e756d', accent: '#91c3b8', lightAccent: '#386f66', sidebar: '#183c3b', dark: { paper: '#132425', surface: '#1b3030', ink: '#e0ece8', muted: '#a0beb6', line: '#33524e', soft: '#243d38', reading: '#cde0db', sidebar: '#132a2a' } }
];
const savedSkin = localStorage.getItem('gw-reading-skin');
const restoredSkin = READING_SKINS.includes(savedSkin) ? savedSkin : localStorage.getItem('gw-reading-dark') === 'true' ? 'dark' : 'light';
const savedColour = localStorage.getItem('gw-colour-theme');
const restoredFilters = storedJSON('gw-library-filters', {});
const state = {
  data: null, posts: [], policy: {}, view: 'home', previousView: 'library',
  activeFilter: 'All', query: '', visible: 18, currentPost: null, yearFilter: null,
  saved: new Set(storedJSON('gw-saved', []).map(String)),
  fontSize: Math.max(16, Math.min(26, Number(localStorage.getItem('gw-font-size')) || 19)),
  skin: restoredSkin, darkMode: restoredSkin === 'dark',
  colourTheme: COLOUR_THEMES.some(theme => theme.id === savedColour) ? savedColour : 'forest',
  lastLightSkin: localStorage.getItem('gw-last-light-skin') === 'sepia' ? 'sepia' : 'light',
  sortOrder: localStorage.getItem('gw-sort-order') || 'newest',
  bibleShelf: restoredFilters.bibleShelf || 'all', bookFilter: restoredFilters.bookFilter || 'all',
  characterFilter: restoredFilters.characterFilter || 'all', topicFilters: restoredFilters.topicFilters || [],
  layout: localStorage.getItem('gw-library-layout') || 'list', indexKind: 'books', indexShelf: 'all',
  readingPositions: storedJSON('gw-reading-positions', {}),
  lastStudy: localStorage.getItem('gw-last-study'), libraryScroll: 0, lastProgressSave: 0,
  settingsTab: 'reading', settingsFocus: null, ready: false
};
const syncState = {
  status: null, apiAvailable: null, revision: null, pendingRevision: null,
  autoRefresh: true, polling: null, refreshing: null, settingsBusy: false,
  lastPoll: 0, pollTimer: null, clockTimer: null
};

const CORE_TOPICS = ['Jesus & Gospels', 'Genesis & Patriarchs', 'Kings & Prophets', 'Torah & Covenant', 'Acts & Early Church', 'Prayer & Spiritual Life', 'Faith, Grace & Salvation', 'Marriage & Relationships', 'Sexuality & Purity', 'Revelation & Eternity', 'Wisdom, Psalms & Worship', 'Spiritual Warfare', 'Church & Ministry', 'Family & Parenting', 'Healing & Encouragement', 'Money & Stewardship'];
const OLD_TESTAMENT_BOOKS = ['Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel', '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra', 'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi'];
const NEW_TESTAMENT_BOOKS = ['Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans', '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians', 'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon', 'Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John', 'Jude', 'Revelation'];
const CHARACTER_PRIORITY = ['Jesus', 'Moses', 'Abraham', 'David', 'Solomon', 'Peter', 'Paul', 'John', 'Mary'];
const VIEW_NAMES = { home: 'Study desk', library: 'Study library', saved: 'Saved studies', scripture: 'Bible reader', bible: 'Bible index', topics: 'Study topics', timeline: 'Timeline', updates: 'Library updates', translations: 'Study translations' };
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const els = { homeView: $('#homeView'), articleView: $('#articleView'), studyGrid: $('#studyGrid'), relatedGrid: $('#relatedGrid'), search: $('#searchInput'), resultCount: $('#resultCount'), loadMore: $('#loadMore'), emptyState: $('#emptyState'), clearFilters: $('#clearFilters'), savedCount: $('#savedCount'), readingProgress: $('#readingProgress'), toast: $('#toast'), scroll: $('#main') };
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escapeHTML = (value = '') => String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
const normalizeTitle = title => title || '';
const topicsFor = post => [...new Set((post.topics?.length ? post.topics : post.subject ? [post.subject] : []).filter(Boolean))];
const categoryFor = post => topicsFor(post)[0] || 'Bible study';
const topicFor = categoryFor;
function readMinutes(post) {
  if (typeof post === 'string') return Math.max(1, Math.round(post.trim().split(/\s+/).length / 235));
  if (!post.readingMinutes) post.readingMinutes = readMinutes(post.text);
  return post.readingMinutes;
}
function formatDate(timestamp) { return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(timestamp * 1000)); }
function formatCheck(value, options = {}) {
  const date = new Date(value);
  if (!value || !Number.isFinite(date.getTime())) return 'Not yet';
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', ...options }).format(date);
}
function excerptFor(post) {
  if (post.translationExcerpt) return post.translationExcerpt;
  const blocks = post.text.split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  const source = blocks.find(block => block !== post.title && block !== post.subtitle && block.length > 60) || post.text;
  return source.length > 185 ? `${source.slice(0, 182).trim()}…` : source;
}
function linkify(value) {
  return escapeHTML(value).replace(/(https?:\/\/[^\s<]+)/g, raw => {
    const punctuation = raw.match(/[.,;:!?)]$/)?.[0] || '';
    const url = punctuation ? raw.slice(0, -1) : raw;
    return `<a href="${url}" target="_blank" rel="noopener">${url}</a>${punctuation}`;
  }).replace(/\n/g, '<br>');
}
function allTopicNames() {
  const actual = new Set(state.posts.flatMap(topicsFor));
  return [...CORE_TOPICS, ...[...actual].filter(topic => !CORE_TOPICS.includes(topic)).sort((a, b) => a.localeCompare(b))];
}
function topicCounts() {
  const counts = new Map();
  state.posts.forEach(post => topicsFor(post).forEach(topic => counts.set(topic, (counts.get(topic) || 0) + 1)));
  return counts;
}
function orderedOptions(values, priority = []) {
  const unique = [...new Set(values)].filter(Boolean);
  return [...priority.filter(value => unique.includes(value)), ...unique.filter(value => !priority.includes(value)).sort((a, b) => a.localeCompare(b))];
}
function persistLibrarySettings() {
  localStorage.setItem('gw-sort-order', state.sortOrder);
  localStorage.setItem('gw-library-filters', JSON.stringify({ bibleShelf: state.bibleShelf, bookFilter: state.bookFilter, characterFilter: state.characterFilter, topicFilters: state.topicFilters }));
}
function matchesBibleShelf(post) {
  if (state.bibleShelf === 'all') return true;
  const books = post.bibleBooks || [];
  return state.bibleShelf === 'old'
    ? post.testament === 'Old Testament' || books.some(book => OLD_TESTAMENT_BOOKS.includes(book))
    : post.testament === 'New Testament' || books.some(book => NEW_TESTAMENT_BOOKS.includes(book));
}
function sortPosts(posts) {
  return [...posts].sort((left, right) => {
    if (state.sortOrder === 'oldest') return left.timestamp - right.timestamp || left.title.localeCompare(right.title);
    if (state.sortOrder === 'az') return left.title.localeCompare(right.title) || right.timestamp - left.timestamp;
    if (state.sortOrder === 'za') return right.title.localeCompare(left.title) || right.timestamp - left.timestamp;
    return right.timestamp - left.timestamp || left.title.localeCompare(right.title);
  });
}
function filteredPosts() {
  let posts = state.posts;
  if (state.activeFilter === 'Saved') posts = posts.filter(post => state.saved.has(post.id));
  else if (state.activeFilter !== 'All') posts = posts.filter(post => topicsFor(post).includes(state.activeFilter));
  if (state.yearFilter) posts = posts.filter(post => new Date(post.timestamp * 1000).getUTCFullYear() === state.yearFilter);
  if (state.bibleShelf !== 'all') posts = posts.filter(matchesBibleShelf);
  if (state.bookFilter !== 'all') posts = posts.filter(post => (post.bibleBooks || []).includes(state.bookFilter));
  if (state.characterFilter !== 'all') posts = posts.filter(post => (post.biblicalCharacters || []).includes(state.characterFilter));
  if (state.topicFilters.length) posts = posts.filter(post => state.topicFilters.some(topic => topicsFor(post).includes(topic)));
  if (state.query) {
    const terms = state.query.toLowerCase().split(/\s+/).filter(Boolean);
    posts = posts.filter(post => {
      const haystack = `${post.title} ${post.subtitle || ''} ${post.text} ${(post.topics || []).join(' ')} ${(post.bibleBooks || []).join(' ')} ${(post.biblicalCharacters || []).join(' ')} ${(post.bibleReferences || []).join(' ')}`.toLowerCase();
      const translated = StudyLanguages.metadata(post);
      const translatedHaystack = `${translated.title} ${translated.subtitle || ''} ${translated.translationExcerpt || ''}`.toLowerCase();
      return terms.every(term => haystack.includes(term) || translatedHaystack.includes(term));
    });
  }
  return sortPosts(posts);
}

function showView(view, { push = true, preserveFilters = false } = {}) {
  if (!VIEW_NAMES[view]) view = 'home';
  if (state.currentPost) saveReadingPosition();
  if (view === 'saved' && !preserveFilters) {
    resetFilterValues();
    state.activeFilter = 'Saved';
  } else if (view === 'library' && state.view === 'saved' && !preserveFilters) state.activeFilter = 'All';
  state.currentPost = null;
  StudyLanguages.cancel();
  state.view = view;
  els.homeView.hidden = false;
  els.articleView.hidden = true;
  document.body.classList.remove('article-open', 'sidebar-open');
  const page = view === 'saved' ? 'library' : view;
  $$('[data-page]').forEach(element => { element.hidden = element.dataset.page !== page; });
  $$('.sidebar-nav [data-view]').forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  $('#workspaceTitle').textContent = VIEW_NAMES[view];
  $('#libraryTitle').textContent = state.activeFilter === 'Saved' ? 'Saved studies' : 'Study library';
  $('#libraryDescription').textContent = state.activeFilter === 'Saved' ? 'The studies you want to return to, all in one place.' : 'Find your next question, passage, or moment of encouragement.';
  document.title = `${VIEW_NAMES[view]} — Gospel Warrior`;
  if (view === 'home') renderToday();
  if (page === 'library') { syncSettingsUI(); renderGrid(); }
  if (view === 'updates') pollUpdateStatus();
  if (push) history.pushState({}, '', `#view=${view}`);
  els.scroll.scrollTop = 0;
  els.readingProgress.style.width = '0';
  renderSyncUI();
  KJVBible.dismiss();
  if (view === 'scripture') KJVBible.open();
  else KJVBible.leave();
}
function resetFilterValues() {
  state.activeFilter = 'All'; state.yearFilter = null; state.bibleShelf = 'all';
  state.bookFilter = 'all'; state.characterFilter = 'all'; state.topicFilters = []; state.query = '';
  els.search.value = '';
}
function clearAll() {
  resetFilterValues();
  persistLibrarySettings();
  syncSettingsUI();
  renderGrid(true);
}
function resetSettings() { state.sortOrder = 'newest'; clearAll(); }
function setFilter(filter) {
  resetFilterValues();
  state.activeFilter = filter;
  if (filter !== 'All' && filter !== 'Saved') state.topicFilters = [filter];
  persistLibrarySettings();
  showView(filter === 'Saved' ? 'saved' : 'library', { preserveFilters: true });
  renderGrid(true);
}
function selectBibleBook(book) {
  resetFilterValues(); state.bookFilter = book; persistLibrarySettings();
  showView('library', { preserveFilters: true }); renderGrid(true);
}
function selectCharacter(character) {
  resetFilterValues(); state.characterFilter = character; persistLibrarySettings();
  showView('library', { preserveFilters: true }); renderGrid(true);
}
function selectArchiveYear(year) {
  resetFilterValues(); state.yearFilter = year; persistLibrarySettings();
  showView('library', { preserveFilters: true }); renderGrid(true);
}
function selectShelf(shelf) {
  resetFilterValues(); state.bibleShelf = shelf; persistLibrarySettings();
  showView('library', { preserveFilters: true }); renderGrid(true);
}
function searchStudies() {
  closeSettings();
  if (state.currentPost || !['library', 'saved'].includes(state.view)) showView('library', { preserveFilters: true });
  els.search.focus();
}

function cardHTML(post) {
  post = StudyLanguages.metadata(post);
  const saved = state.saved.has(post.id);
  const reference = (post.bibleReferences || [])[0];
  const image = (state.policy.excludedImages || []).includes(post.imageLocal) ? 'assets/study-emblem.svg' : post.imageLocal || 'assets/study-emblem.svg';
   return `<article class="study-card" data-id="${escapeHTML(post.id)}" tabindex="0" aria-label="Read ${escapeHTML(post.title)}"><div class="study-card-image"><img src="${escapeHTML(image)}" alt="" loading="lazy"/></div><div class="study-card-body"><div class="card-meta"><span>${escapeHTML(topicFor(post))}</span><i></i><span>${readMinutes(post)} min read</span></div><h3 lang="${post.translationReady ? post.translationLanguage : 'en'}">${escapeHTML(normalizeTitle(post.title))}</h3><p class="study-card-excerpt">${escapeHTML(excerptFor(post))}</p>${post.translationLanguage !== 'en' ? `<div class="translation-card-status">${post.translationReady ? `${post.translationLanguage === 'fr' ? 'Français' : 'Malagasy'} · ready offline` : `${post.translationLanguage === 'fr' ? 'French' : 'Malagasy'} version pending · open to prioritize`}</div>` : ''}<div class="card-footer"><time>${formatDate(post.timestamp)}</time>${reference ? `<span class="scripture-tag">${escapeHTML(reference)}</span>` : ''}</div></div><button class="card-save ${saved ? 'saved' : ''}" data-save="${escapeHTML(post.id)}" aria-label="${saved ? 'Remove saved study' : 'Save study'}" title="${saved ? 'Remove saved study' : 'Save study'}">${icon('save')}</button></article>`;
}
function renderGrid(reset = false) {
  if (reset) state.visible = 18;
  const posts = filteredPosts();
  els.resultCount.textContent = `${posts.length.toLocaleString()} ${posts.length === 1 ? 'study' : 'studies'}${state.yearFilter ? ` · ${state.yearFilter}` : ''}${state.query ? ` matching “${state.query}”` : ''}`;
  els.emptyState.hidden = posts.length > 0;
  els.studyGrid.hidden = posts.length === 0;
  els.studyGrid.className = `study-grid layout-${state.layout}`;
  els.studyGrid.innerHTML = posts.slice(0, state.visible).map(cardHTML).join('');
  els.loadMore.parentElement.hidden = posts.length <= state.visible;
  els.clearFilters.hidden = !state.query && !state.yearFilter && state.bibleShelf === 'all' && state.bookFilter === 'all' && state.characterFilter === 'all' && !state.topicFilters.length;
}
function recentStudyHTML(post) {
  post = StudyLanguages.metadata(post);
  return `<button class="recent-study" data-study="${escapeHTML(post.id)}"><svg class="study-symbol" aria-hidden="true"><use href="#i-book"/></svg><span><strong>${escapeHTML(post.title)}</strong><small>${escapeHTML(topicFor(post))} · ${formatDate(post.timestamp)} · ${readMinutes(post)} min read</small></span>${icon('arrow')}</button>`;
}
function renderToday() {
  const latest = state.posts[0] ? StudyLanguages.metadata(state.posts[0]) : null;
  if (!latest) return;
  const hour = new Date().getHours();
  $('#todayGreeting').textContent = hour < 12 ? 'GOOD MORNING · MAKE ROOM FOR THE WORD' : hour < 18 ? 'A LITTLE STILLNESS IN YOUR AFTERNOON' : 'A QUIET MOMENT IN THE WORD';
  $('#todayDate').textContent = new Intl.DateTimeFormat('en', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date());
  $('#heroTitle').textContent = latest.title;
  $('#heroMeta').textContent = `${formatDate(latest.timestamp)} · ${readMinutes(latest)} min read`;
  $('#heroExcerpt').textContent = excerptFor(latest);
  $('#recentStudies').innerHTML = state.posts.slice(1, 6).map(recentStudyHTML).join('');
  const originalPrevious = state.posts.find(post => post.id === state.lastStudy);
  const previous = originalPrevious ? StudyLanguages.metadata(originalPrevious) : null;
  const position = previous ? state.readingPositions[previous.id] : null;
  $('#continueTitle').textContent = previous ? previous.title : 'A steady rhythm of study.';
  $('#continueDetail').textContent = previous ? `${Math.round((position?.progress || 0) * 100)}% read · ${readMinutes(previous)} min study` : 'Choose a study and make a little room for Scripture today.';
  $('#continueStudy').innerHTML = `${previous ? 'Continue reading' : 'Open the library'} ${icon('arrow')}`;
  $('#continueProgress').hidden = !previous;
  $('#continueProgress span').style.width = `${(position?.progress || 0) * 100}%`;
  $('#studyTotal').textContent = state.posts.length;
  $('#sidebarStudyTotal').textContent = state.posts.length.toLocaleString();
}
function renderFilterBar() {
  const counts = topicCounts();
  $('#filterBar').innerHTML = ['All', ...allTopicNames().filter(topic => counts.get(topic))].map(topic => `<button class="filter-pill ${state.activeFilter === topic ? 'active' : ''}" data-filter="${escapeHTML(topic)}">${escapeHTML(topic === 'All' ? 'All topics' : topic)}</button>`).join('');
}
function availableBooks() { return orderedOptions(state.posts.flatMap(post => post.bibleBooks || []), [...OLD_TESTAMENT_BOOKS, ...NEW_TESTAMENT_BOOKS]); }
function refreshBookFilter() {
  const shelf = state.bibleShelf === 'old' ? OLD_TESTAMENT_BOOKS : state.bibleShelf === 'new' ? NEW_TESTAMENT_BOOKS : [...OLD_TESTAMENT_BOOKS, ...NEW_TESTAMENT_BOOKS];
  const books = availableBooks().filter(book => shelf.includes(book));
  if (state.bookFilter !== 'all' && !books.includes(state.bookFilter)) state.bookFilter = 'all';
  $('#bookFilter').innerHTML = '<option value="all">All books</option>' + books.map(book => `<option value="${escapeHTML(book)}">${escapeHTML(book)}</option>`).join('');
}
function renderSettingsControls() {
  const characters = orderedOptions(state.posts.flatMap(post => post.biblicalCharacters || []), CHARACTER_PRIORITY);
  if (state.characterFilter !== 'all' && !characters.includes(state.characterFilter)) state.characterFilter = 'all';
  $('#characterFilter').innerHTML = '<option value="all">All characters</option>' + characters.map(name => `<option value="${escapeHTML(name)}">${escapeHTML(name)}</option>`).join('');
  const counts = topicCounts();
  $('#topicSettings').innerHTML = allTopicNames().map(topic => `<label class="topic-check"><input type="checkbox" value="${escapeHTML(topic)}" data-setting-topic/><span>${escapeHTML(topic)}</span><b>${counts.get(topic) || 0}</b></label>`).join('');
  syncSettingsUI();
}
function syncSettingsUI() {
  $('#sortOrder').value = state.sortOrder; $('#quickSort').value = state.sortOrder;
  $('#bibleShelf').value = state.bibleShelf;
  refreshBookFilter(); $('#bookFilter').value = state.bookFilter; $('#characterFilter').value = state.characterFilter;
  $$('[data-setting-topic]').forEach(input => { input.checked = state.topicFilters.includes(input.value); });
  $$('[data-shelf]').forEach(button => button.classList.toggle('active', button.dataset.shelf === state.bibleShelf));
  $$('.filter-pill').forEach(button => button.classList.toggle('active', button.dataset.filter === state.activeFilter));
  $$('[data-layout]').forEach(button => { button.classList.toggle('active', button.dataset.layout === state.layout); button.setAttribute('aria-pressed', String(button.dataset.layout === state.layout)); });
  const active = [state.bibleShelf !== 'all', state.bookFilter !== 'all', state.characterFilter !== 'all', state.topicFilters.length > 0].filter(Boolean).length;
  $('#settingsSummary').textContent = `${active ? `${active} filter${active === 1 ? '' : 's'} active` : 'All studies'} · ${{ newest: 'Newest first', oldest: 'Oldest first', az: 'A → Z', za: 'Z → A' }[state.sortOrder]}`;
}
function applyLibrarySettings() {
  state.sortOrder = $('#sortOrder').value; state.bibleShelf = $('#bibleShelf').value;
  state.bookFilter = $('#bookFilter').value; state.characterFilter = $('#characterFilter').value;
  state.topicFilters = $$('[data-setting-topic]:checked').map(input => input.value);
  state.activeFilter = 'All'; state.yearFilter = null;
  syncSettingsUI(); persistLibrarySettings(); renderGrid(true); updateArticleNavigation();
}
function countEntries(field) {
  const counts = new Map();
  state.posts.forEach(post => (post[field] || []).forEach(value => counts.set(value, (counts.get(value) || 0) + 1)));
  return counts;
}
function renderArchiveGuide() {
  const bookCounts = countEntries('bibleBooks');
  const books = availableBooks().filter(book => state.indexShelf === 'all' || (state.indexShelf === 'old' ? OLD_TESTAMENT_BOOKS : NEW_TESTAMENT_BOOKS).includes(book));
  $('#bibleBookTotal').textContent = `${bookCounts.size} books indexed`;
  $('#bookIndex').innerHTML = books.map(book => `<button class="index-card" data-archive-book="${escapeHTML(book)}">${icon('book')}<span><strong>${escapeHTML(book)}</strong><small>${(bookCounts.get(book) || 0).toLocaleString()} studies</small></span></button>`).join('');
  const characters = countEntries('biblicalCharacters');
  $('#characterIndex').innerHTML = orderedOptions([...characters.keys()], CHARACTER_PRIORITY).map(name => `<button class="index-card" data-archive-character="${escapeHTML(name)}">${icon('people')}<span><strong>${escapeHTML(name)}</strong><small>${characters.get(name).toLocaleString()} studies</small></span></button>`).join('');
  const counts = topicCounts();
  const topics = allTopicNames().filter(topic => counts.get(topic));
  $('#studySubjectTotal').textContent = `${topics.length} study topics`;
  $('#subjectIndex').innerHTML = topics.map((topic, index) => `<button class="topic-card" data-filter="${escapeHTML(topic)}">${icon(index % 3 === 0 ? 'book' : index % 3 === 1 ? 'leaf' : 'topics')}<span><strong>${escapeHTML(topic)}</strong><small>${counts.get(topic).toLocaleString()} studies to explore</small></span></button>`).join('');
  const years = new Map();
  state.posts.forEach(post => { const year = new Date(post.timestamp * 1000).getUTCFullYear(); if (!years.has(year)) years.set(year, []); years.get(year).push(post); });
  $('#timelineList').innerHTML = [...years.entries()].sort((a, b) => b[0] - a[0]).map(([year, posts]) => `<article class="timeline-year-card"><div class="timeline-year-meta"><strong>${year}</strong><small>${posts.length.toLocaleString()} studies</small><button class="text-button" data-archive-year="${year}">Explore this year ${icon('arrow')}</button></div><div class="timeline-year-studies">${posts.slice(0, 3).map(recentStudyHTML).join('')}</div></article>`).join('');
}

function toggleSave(id) {
  if (state.saved.has(id)) { state.saved.delete(id); showToast('Removed from saved studies'); }
  else { state.saved.add(id); showToast('Saved for another quiet moment.'); }
  localStorage.setItem('gw-saved', JSON.stringify([...state.saved]));
  updateSavedCount(); renderGrid(); updateArticleSaveButtons();
}
function updateSavedCount() { els.savedCount.textContent = state.saved.size; }
function updateArticleSaveButtons() {
  if (!state.currentPost) return;
  const saved = state.saved.has(state.currentPost.id);
  $('#articleSave').classList.toggle('saved', saved);
  $('#articleSave span').textContent = saved ? 'Saved' : 'Save study';
  $('#endSave').textContent = saved ? 'Remove from saved' : 'Save this study';
}
function mixColour(left, right, amount) {
  const parts = colour => [1, 3, 5].map(index => parseInt(colour.slice(index, index + 2), 16));
  const first = parts(left), second = parts(right);
  return '#' + first.map((value, index) => Math.round(value * (1 - amount) + second[index] * amount).toString(16).padStart(2, '0')).join('');
}
function appearanceColours(theme, skin) {
  const dark = skin === 'dark';
  const base = dark ? theme.dark : skin === 'sepia'
    ? { paper: '#ece0c6', surface: '#f7eedb', ink: '#423623', muted: '#756344', line: '#d6c6a8', soft: '#e9dcbe', reading: '#4c3d29' }
    : { paper: '#f5f3ed', surface: '#fffefa', ink: '#29332d', muted: '#686f62', line: '#e0e1d5', soft: '#eceee6', reading: '#414b3e' };
  const accent = dark ? theme.accent : theme.lightAccent;
  const sidebar = dark ? theme.dark.sidebar : theme.sidebar;
  return {
    '--forest': dark ? base.ink : theme.primary, '--forest-deep': sidebar,
    '--sage': dark ? mixColour(base.ink, theme.accent, .48) : theme.secondary,
    '--gold': accent, '--gold-light': mixColour(base.surface, theme.accent, .42),
    '--paper': base.paper, '--surface': base.surface, '--ink': base.ink, '--muted': base.muted,
    '--line': base.line, '--soft': base.soft, '--reading-ink': base.reading,
    '--sidebar-bg': sidebar, '--sidebar-ink': '#f0e8d8', '--sidebar-muted': mixColour(sidebar, '#f0e8d8', .68),
    '--sidebar-active': mixColour(sidebar, theme.accent, .18), '--sidebar-accent': theme.accent,
    '--button-bg': dark ? theme.accent : theme.primary,
    '--button-ink': dark ? theme.dark.paper : '#fffefa',
    '--button-hover': dark ? mixColour(theme.accent, '#ffffff', .12) : mixColour(theme.primary, '#000000', .15),
    '--accent-soft': mixColour(base.surface, theme.accent, dark ? .12 : .18),
    '--accent-line': mixColour(base.line, theme.accent, .22),
    '--scripture-bg': mixColour(base.surface, theme.accent, dark ? .08 : .12),
    '--saved-fill': mixColour(base.surface, theme.accent, .25),
    '--selection-ink': dark ? base.paper : theme.primary,
    '--selection-bg': mixColour(base.surface, theme.accent, dark ? .65 : .42),
    '--dark-skin-paper': theme.dark.paper, '--dark-skin-ink': theme.dark.ink
  };
}
function renderAppearanceControls() {
  const grid = $('#colourThemes');
  if (!grid.children.length) grid.innerHTML = COLOUR_THEMES.map(theme => `<button class="colour-theme-choice" data-colour-theme="${theme.id}" aria-pressed="false"><span class="theme-swatch" aria-hidden="true"><i></i><span><b></b><em></em><em></em></span></span><span class="theme-choice-name">${theme.name}</span><small>${theme.description}</small><span class="theme-choice-check">${icon('check')}</span></button>`).join('');
  const chosen = COLOUR_THEMES.find(theme => theme.id === state.colourTheme);
  $$('[data-colour-theme]').forEach(button => {
    const theme = COLOUR_THEMES.find(item => item.id === button.dataset.colourTheme);
    const colours = appearanceColours(theme, state.skin);
    const active = theme.id === state.colourTheme;
    button.setAttribute('aria-pressed', String(active));
    button.style.setProperty('--sample-sidebar', colours['--sidebar-bg']);
    button.style.setProperty('--sample-paper', colours['--paper']);
    button.style.setProperty('--sample-surface', colours['--surface']);
    button.style.setProperty('--sample-accent', colours['--button-bg']);
    button.style.setProperty('--sample-line', colours['--line']);
  });
  $$('[data-skin]').forEach(button => { button.classList.toggle('active', button.dataset.skin === state.skin); button.setAttribute('aria-pressed', String(button.dataset.skin === state.skin)); });
  $('#appearanceSummary').textContent = `${state.skin[0].toUpperCase() + state.skin.slice(1)} · ${chosen.name}`;
}
function applyReadingMode() {
  state.darkMode = state.skin === 'dark';
  const theme = COLOUR_THEMES.find(item => item.id === state.colourTheme);
  for (const [name, value] of Object.entries(appearanceColours(theme, state.skin))) document.body.style.setProperty(name, value);
  document.body.dataset.skin = state.skin; document.body.dataset.colourTheme = state.colourTheme;
  document.body.style.colorScheme = state.darkMode ? 'dark' : 'light';
  document.body.classList.toggle('reader-dark', state.darkMode);
  document.body.classList.toggle('reader-sepia', state.skin === 'sepia');
  $('#readerTheme').setAttribute('aria-pressed', String(state.darkMode));
  $('#readerTheme').title = state.darkMode ? 'Return to light or sepia skin' : 'Use dark skin';
  $('#readerTheme').setAttribute('aria-label', $('#readerTheme').title);
  $('meta[name="theme-color"]').content = document.body.style.getPropertyValue('--sidebar-bg');
  window.webkit?.messageHandlers?.gospelAppearance?.postMessage({ skin: state.skin, background: document.body.style.getPropertyValue('--paper') });
  renderAppearanceControls();
  $('#readingSize').value = state.fontSize;
  $('#readingSizeLabel').textContent = `${state.fontSize} px`;
  $('#readingPreview').style.fontSize = `${state.fontSize}px`;
  $('#articleBody').style.fontSize = `${state.fontSize}px`;
}
function setFontSize(size) { state.fontSize = Math.max(16, Math.min(26, Number(size))); localStorage.setItem('gw-font-size', state.fontSize); applyReadingMode(); }
function setReadingSkin(skin) {
  if (!READING_SKINS.includes(skin)) return;
  state.skin = skin;
  if (skin !== 'dark') { state.lastLightSkin = skin; localStorage.setItem('gw-last-light-skin', skin); }
  localStorage.setItem('gw-reading-skin', skin);
  localStorage.setItem('gw-reading-dark', String(skin === 'dark'));
  applyReadingMode();
}
function setColourTheme(colour) {
  if (!COLOUR_THEMES.some(theme => theme.id === colour)) return;
  state.colourTheme = colour; localStorage.setItem('gw-colour-theme', colour); applyReadingMode();
}
function toggleTheme() { setReadingSkin(state.skin === 'dark' ? state.lastLightSkin : 'dark'); }
function renderArticleText(post) {
  const blocks = post.text.split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  if (blocks[0] === post.title) blocks.shift();
  if (blocks[0] === post.subtitle) blocks.shift();
  const toc = [];
  $('#articleBody').innerHTML = blocks.map(block => {
    const letters = block.replace(/[^A-Za-z]/g, '');
    if (letters.length > 8 && letters === letters.toUpperCase() && block.length <= 125 && block.split(/\s+/).length >= 3) {
      const id = `section-${toc.length + 1}`; toc.push({ id, label: block });
      return `<h2 class="study-subhead" id="${id}">${linkify(block)}</h2>`;
    }
    if (/[\u0590-\u05ff]/.test(block) && block.length < 300) return `<p class="study-paragraph hebrew-line">${linkify(block)}</p>`;
    const quote = /^[“"]/u.test(block) && block.length > 45 && block.length < 480;
    if (quote) return `<blockquote class="${/(says|wrote|verse|scripture|lord|god|jesus|christ|father|spirit)/i.test(block) ? 'study-scripture' : 'study-quote'}">${linkify(block)}</blockquote>`;
    const strong = /^(but|and this|the question|there is|this is|remember|come back|look again)/i.test(block) && block.length < 100;
    return `<p class="study-paragraph${strong ? ' strong-line' : ''}">${linkify(block)}</p>`;
  }).join('');
  $('#articleToc').hidden = !toc.length;
  $('#tocLinks').innerHTML = toc.slice(0, 12).map(item => `<a href="#${item.id}" data-toc="${item.id}">${escapeHTML(item.label)}</a>`).join('');
}
function renderRelated(post) {
  const overlap = (left = [], right = []) => left.filter(value => right.includes(value)).length;
  const related = state.posts.filter(item => item.id !== post.id).map(item => ({ item, score: overlap(item.topics, post.topics) * 5 + overlap(item.bibleBooks, post.bibleBooks) * 4 + overlap(item.biblicalCharacters, post.biblicalCharacters) * 2 })).sort((a, b) => b.score - a.score || b.item.timestamp - a.item.timestamp).slice(0, 3).map(entry => entry.item);
  els.relatedGrid.innerHTML = related.map(cardHTML).join('');
}
function updateArticleNavigation() {
  if (!state.currentPost) return;
  const sequence = filteredPosts();
  const index = sequence.findIndex(post => post.id === state.currentPost.id);
  $('#articlePrev').disabled = index <= 0;
  $('#articleNext').disabled = index < 0 || index >= sequence.length - 1;
}
function openStudy(id, updateHash = true, resume = false) {
  const post = state.posts.find(item => item.id === String(id));
  if (!post) return;
  KJVBible.leave();
  if (state.currentPost) saveReadingPosition(); else { state.previousView = state.view; state.libraryScroll = els.scroll.scrollTop; }
  state.currentPost = post; state.lastStudy = post.id;
  localStorage.setItem('gw-last-study', post.id);
  els.homeView.hidden = true; els.articleView.hidden = false;
  document.body.classList.add('article-open'); document.body.classList.remove('sidebar-open');
  $('#workspaceTitle').textContent = 'Reading room';
  $('#articleCategory').textContent = topicFor(post);
  $('#articleDate').textContent = formatDate(post.timestamp); $('#articleDate').dateTime = post.date;
  $('#articleReadTime').textContent = `${readMinutes(post)} min read`;
  $('#articleTitle').textContent = post.title; $('#articleSubtitle').textContent = post.subtitle || excerptFor(post);
   $('#articleTaxonomy').innerHTML = [...(post.bibleReferences || []).slice(0, 4).map(value => `<button class="taxonomy-chip scripture-chip" data-bible-reference="${escapeHTML(value)}">${escapeHTML(value)}</button>`), ...(post.bibleBooks || []).slice(0, 3).map(value => `<span class="taxonomy-chip">${escapeHTML(value)}</span>`)].join('');
   $('#readerReferences').innerHTML = (post.bibleReferences || []).slice(0, 14).map(value => `<button data-bible-reference="${escapeHTML(value)}">${escapeHTML(value)}</button>`).join('') || '<span>Read alongside your Bible.</span>';
   StudyLanguages.open(post); renderRelated(post); updateArticleSaveButtons(); updateArticleNavigation(); applyReadingMode();
  document.title = `${post.title} — Gospel Warrior`;
  if (updateHash) history.pushState({ study: post.id }, '', `#study=${encodeURIComponent(post.id)}`);
  els.scroll.scrollTop = 0;
  if (resume && state.readingPositions[post.id]?.progress) requestAnimationFrame(() => {
    const body = $('#articleBody');
    const start = els.scroll.scrollTop + body.getBoundingClientRect().top - els.scroll.getBoundingClientRect().top;
    els.scroll.scrollTop = start + state.readingPositions[post.id].progress * Math.max(0, body.scrollHeight - els.scroll.clientHeight);
    onScroll();
  });
  onScroll();
}
function moveStudy(direction) {
  if (!state.currentPost) return;
  const sequence = filteredPosts();
  const next = sequence[sequence.findIndex(post => post.id === state.currentPost.id) + direction];
  if (next) openStudy(next.id);
}
function closeStudy(push = true) {
  if (!state.currentPost) return;
  saveReadingPosition();
  const scroll = state.libraryScroll;
  showView(state.previousView || 'library', { push, preserveFilters: true });
  els.scroll.scrollTop = scroll;
}
function readingFraction() {
  if (!state.currentPost) return 0;
  const body = $('#articleBody');
  const start = els.scroll.scrollTop + body.getBoundingClientRect().top - els.scroll.getBoundingClientRect().top;
  return Math.max(0, Math.min(1, (els.scroll.scrollTop - start) / Math.max(1, body.offsetHeight - els.scroll.clientHeight)));
}
function saveReadingPosition() {
  if (!state.currentPost) return;
  state.readingPositions[state.currentPost.id] = { progress: Number(readingFraction().toFixed(4)), updated: Date.now() };
  const entries = Object.entries(state.readingPositions).sort((a, b) => b[1].updated - a[1].updated).slice(0, 100);
  state.readingPositions = Object.fromEntries(entries);
  localStorage.setItem('gw-reading-positions', JSON.stringify(state.readingPositions));
}
function onScroll() {
  if (!state.currentPost) return;
  const percent = Math.round(readingFraction() * 100);
  els.readingProgress.style.width = `${percent}%`;
  $('#statusbarDetail').textContent = `${percent}% read · ${readMinutes(state.currentPost)} min study`;
  if (Date.now() - state.lastProgressSave > 2000) { saveReadingPosition(); state.lastProgressSave = Date.now(); }
}

function openSettings(tab = 'reading') {
  if (typeof tab !== 'string') tab = 'reading';
  state.settingsFocus = document.activeElement;
  $('#settingsOverlay').hidden = false; $('#settingsPanel').hidden = false;
  $('#settingsButton').setAttribute('aria-expanded', 'true');
  selectSettingsTab(tab);
  $('#settingsPanel').focus();
}
function selectSettingsTab(tab) {
  state.settingsTab = tab;
  $$('[data-settings-tab]').forEach(button => { button.setAttribute('aria-selected', String(button.dataset.settingsTab === tab)); button.tabIndex = button.dataset.settingsTab === tab ? 0 : -1; });
  $$('[data-settings-page]').forEach(page => { page.hidden = page.dataset.settingsPage !== tab; });
}
function closeSettings() {
  if ($('#settingsPanel').hidden) return;
  $('#settingsOverlay').hidden = true; $('#settingsPanel').hidden = true;
  $('#settingsButton').setAttribute('aria-expanded', 'false');
  if (state.settingsFocus?.isConnected) state.settingsFocus.focus();
}
function showToast(message) {
  $('#toast p').textContent = message;
  els.toast.classList.add('show'); clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.remove('show'), 4000);
}

async function fetchJSON(url, options = {}, timeout = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { cache: 'no-store', ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return await response.json();
  } finally { clearTimeout(timer); }
}
async function loadArchiveData() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(`content.json.gz?v=${Date.now()}`, { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error(`Content request failed: ${response.status}`);
    let data;
    if (response.headers.get('x-gospel-warrior-plain-json') === 'true' || (response.headers.get('content-encoding') || '').toLowerCase().includes('gzip')) data = await response.json();
    else {
      if (typeof DecompressionStream === 'undefined') throw new Error('The local archive service must provide HTTP gzip decoding.');
      data = await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).json();
    }
    return { data, revision: response.headers.get('x-archive-revision') };
  } finally { clearTimeout(timer); }
}
function hydrateArchive(data) {
  if (!Array.isArray(data.posts)) throw new Error('The archive is not a study collection.');
  const ids = new Set((state.policy.excludedPostIds || []).map(String));
  const titles = new Set((state.policy.excludedTitles || []).map(title => title.trim().toLowerCase()));
  const posts = data.posts.filter(post => !ids.has(String(post.id)) && !titles.has(post.title.trim().toLowerCase())).map(post => ({ ...post, id: String(post.id) })).sort((a, b) => b.timestamp - a.timestamp);
  if (!posts.length) throw new Error('The study library is empty.');
  state.data = data; state.posts = posts;
  const present = new Set(posts.map(post => post.id));
  state.saved = new Set([...state.saved].filter(id => present.has(id)));
  localStorage.setItem('gw-saved', JSON.stringify([...state.saved]));
}
function renderArchiveViews() { renderToday(); renderFilterBar(); renderSettingsControls(); renderArchiveGuide(); renderGrid(); updateSavedCount(); applyReadingMode(); }

async function refreshArchive({ automatic = false } = {}) {
  if (syncState.refreshing) return syncState.refreshing;
  syncState.refreshing = (async () => {
    const existingIDs = new Set(state.posts.map(post => post.id));
    try {
      const { data, revision } = await loadArchiveData();
      // Capture immediately before applying data: the reader may have scrolled,
      // selected text, or opened another study while the archive was loading.
      const scroll = els.scroll.scrollTop;
      const readingID = state.currentPost?.id;
      const selection = getSelection();
      const selectedText = selection?.toString() || '';
      const ranges = [];
      if (readingID && selection?.rangeCount && $('#articleBody').contains(selection.anchorNode)) {
        for (let index = 0; index < selection.rangeCount; index++) ranges.push(selection.getRangeAt(index).cloneRange());
      }
      hydrateArchive(data);
      syncState.revision = revision || syncState.status?.contentRevision || null;
      syncState.pendingRevision = null;
      renderArchiveViews();
      // Never replace the reader's DOM during a background refresh. This keeps
      // text selection, reading position, and the open study uninterrupted.
      if (readingID) {
        state.currentPost = state.posts.find(post => post.id === readingID) || state.currentPost;
        updateArticleNavigation(); updateArticleSaveButtons();
      }
      if (ranges.length && getSelection().toString() !== selectedText) {
        getSelection().removeAllRanges(); ranges.forEach(range => getSelection().addRange(range));
      }
      els.scroll.scrollTop = scroll;
      const added = state.posts.filter(post => !existingIDs.has(post.id)).length;
      renderSyncUI();
      if (added) showToast(`${added} new Bible ${added === 1 ? 'study' : 'studies'} added to your library.`);
      else if (!automatic) showToast('Your study library is refreshed.');
      document.dispatchEvent(new CustomEvent('gospel:archive-refreshed', { detail: { added, revision: syncState.revision } }));
      return { added, revision: syncState.revision };
    } catch (error) {
      if (!automatic) showToast('Could not refresh right now. Your current studies are still available.');
      syncState.pendingRevision = syncState.status?.contentRevision || syncState.pendingRevision;
      renderSyncUI();
      throw error;
    }
  })();
  try { return await syncState.refreshing; } finally { syncState.refreshing = null; }
}
async function pollUpdateStatus({ force = false } = {}) {
  if (syncState.polling) return syncState.polling;
  if (!force && document.hidden && Date.now() - syncState.lastPoll < 30000) return syncState.status;
  syncState.polling = (async () => {
    syncState.lastPoll = Date.now();
    try {
      const status = await fetchJSON('/api/update/status');
      syncState.apiAvailable = !!status.apiAvailable;
      syncState.status = status;
      syncState.autoRefresh = status.autoRefresh !== false;
      if (state.ready && status.contentRevision && status.contentRevision !== syncState.revision) {
        if (!syncState.revision) {
          syncState.revision = status.contentRevision;
          // Android's packaged archive has no HTTP file metadata. When a
          // public source is configured, perform one comparison download so a
          // newly installed APK immediately converges on the hosted archive.
          if (window.gospelAndroidRemoteUpdates) {
            try { await refreshArchive({ automatic: true }); } catch (_) { /* Retry on the next poll. */ }
          }
        }
        else {
          syncState.pendingRevision = status.contentRevision;
          if (syncState.autoRefresh && !status.updateInProgress) {
            try { await refreshArchive({ automatic: true }); } catch (_) { /* Retry on the next poll. */ }
          }
        }
      }
    } catch (_) {
      syncState.apiAvailable = false;
    }
    renderSyncUI();
    return syncState.status;
  })();
  try { return await syncState.polling; } finally { syncState.polling = null; }
}
async function requestUpdateCheck() {
  if (syncState.status?.staticOnly) {
    showToast('The public update source checks automatically while the app is open.');
    return null;
  }
  if (syncState.apiAvailable === false) { showToast('The offline library is ready. Update checks need the app service.'); return null; }
  try {
    const result = await fetchJSON('/api/update/check', { method: 'POST' });
    if (result.started) showToast('Checking for new Bible studies in the background.');
    else showToast('A study update check is already in progress.');
    await pollUpdateStatus({ force: true });
    return result;
  } catch (_) { showToast('Could not start this check. The next automatic check will retry.'); return null; }
}
async function saveUpdateSettings(changes) {
  if (syncState.status?.staticOnly) {
    if (Object.prototype.hasOwnProperty.call(changes, 'autoRefresh')) {
      syncState.autoRefresh = !!changes.autoRefresh;
      renderSyncUI();
    }
    showToast('Automatic update scheduling is managed by the public source.');
    return null;
  }
  if (syncState.settingsBusy) return null;
  syncState.settingsBusy = true;
  const message = 'Saving update settings…';
  $('#updateSettingsStatus').textContent = message; $('#updatesSettingsStatus').textContent = message;
  renderSyncUI();
  try {
    const payload = await fetchJSON('/api/update/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ intervalMinutes: 15, ...changes }) });
    syncState.status = payload.status; syncState.apiAvailable = true;
    syncState.autoRefresh = payload.config.autoRefresh !== false;
    $('#updateSettingsStatus').textContent = 'Saved. Your library will follow these settings.';
    $('#updatesSettingsStatus').textContent = 'Update settings saved.';
    if (syncState.autoRefresh && syncState.pendingRevision) await refreshArchive({ automatic: true });
    return payload;
  } catch (_) {
    $('#updateSettingsStatus').textContent = 'Could not save. Please try again.';
    $('#updatesSettingsStatus').textContent = 'Could not save. Please try again.';
    return null;
  } finally { syncState.settingsBusy = false; renderSyncUI(); }
}
function syncMode() {
  if (syncState.apiAvailable === false) return 'offline';
  const status = syncState.status;
  if (!status) return 'offline';
  if (status.updateInProgress) return 'checking';
  if (status.state === 'error') return 'error';
  if (!status.schedulerEnabled) return 'paused';
  return 'current';
}
function renderSyncUI() {
  const status = syncState.status || {};
  const mode = syncMode();
  const busy = mode === 'checking';
  const readOnly = !!status.staticOnly;
  document.body.classList.toggle('is-checking', busy);
  for (const id of ['syncDot', 'sidebarUpdateDot', 'statusbarDot', 'settingsSyncDot']) $(`#${id}`).className = `status-dot ${mode}`;
  $('#syncOrbit').classList.toggle('checking', busy);
  const enabled = status.automaticChecksEnabled !== false;
  for (const id of ['automaticChecks', 'updatesEnabled']) { $(`#${id}`).checked = enabled; $(`#${id}`).disabled = readOnly || syncState.apiAvailable !== true || syncState.settingsBusy; }
  for (const id of ['automaticRefresh', 'updatesAutoRefresh']) { $(`#${id}`).checked = syncState.autoRefresh; $(`#${id}`).disabled = readOnly || syncState.apiAvailable !== true || syncState.settingsBusy; }
  $$('.check-now-button').forEach(button => { button.disabled = readOnly || syncState.apiAvailable === false || busy; });
  const label = readOnly ? 'Automatic updates are on' : busy ? 'Checking for new Bible studies' : mode === 'error' ? 'The next check will retry' : mode === 'offline' ? 'Offline reading is ready' : mode === 'paused' ? 'Automatic checks paused' : 'Automatic updates are on';
  $('#sidebarSyncTitle').textContent = readOnly ? 'Public updates are on' : busy ? 'Checking for new studies' : mode === 'current' ? 'Checks every 15 minutes' : mode === 'paused' ? 'Automatic checks paused' : 'Offline library ready';
  $('#settingsSyncTitle').textContent = label; $('#updateStatusLabel').textContent = label;
  $('#updateStatusTitle').textContent = busy ? 'Making room for new studies.' : mode === 'error' ? 'Your studies are still here.' : 'A little more of the Word.';
  $('#updateStatusMessage').textContent = busy ? (status.discovered ? `Reading ${status.processed || 0} of ${status.discovered} newly found studies. Your library remains available.` : 'Looking for newly published Bible studies. Keep reading while we check.') : mode === 'error' ? 'The online source could not be checked. Your offline library stays ready, and the next scheduled check will retry.' : mode === 'offline' ? 'All local studies are available. The update service will reconnect when available.' : mode === 'paused' ? 'You can check manually at any time, or turn automatic checks back on.' : `${state.posts.length.toLocaleString()} studies in your library. ${syncState.autoRefresh ? 'New content refreshes automatically.' : 'New content waits for you to refresh.'}`;
  $('#settingsSyncDetail').textContent = status.lastSuccess ? `Last successful check: ${formatCheck(status.lastSuccess)}` : 'The complete archive is available offline.';
  $('#lastCheckTime').textContent = status.lastCheck ? formatCheck(status.lastCheck, { month: undefined, day: undefined }) : 'Not yet';
  $('#lastCheckDetail').textContent = status.lastCheck ? (mode === 'error' ? 'Check incomplete · retry scheduled' : `${Number(status.addedLastRun || 0)} new studies found`) : 'A check runs when the app opens';
  $('#statusbarSync').textContent = busy ? 'Checking for new Bible studies…' : `${state.posts.length.toLocaleString()} studies · ${syncState.pendingRevision ? 'Update ready' : mode === 'current' && status.lastSuccess ? 'Library up to date' : 'Available offline'}`;
  $('#newContentBanner').hidden = !syncState.pendingRevision;
  $('#newContentMessage').textContent = syncState.autoRefresh ? 'Your library update is ready. Refresh will retry automatically.' : 'New Bible studies are ready for your library.';
  renderUpdateClock(); renderRecentImports();
}
function renderUpdateClock() {
  const status = syncState.status || {};
  const due = status.schedulerEnabled && status.nextCheck ? new Date(status.nextCheck).getTime() : null;
  let short = status.staticOnly ? 'Automatic' : 'Paused';
  if (due && Number.isFinite(due)) {
    const seconds = Math.max(0, Math.ceil((due - Date.now()) / 1000));
    short = seconds ? `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s` : 'Checking soon';
  } else if (syncState.apiAvailable !== true) short = 'Offline';
  $('#nextCheckCountdown').textContent = short;
  $('#nextCheckTime').textContent = due ? formatCheck(status.nextCheck) : status.staticOnly ? 'The public source checks automatically' : 'Manual checks remain available';
  $('#sidebarSyncDetail').textContent = due ? `Next check in ${short}` : status.staticOnly ? 'Public source checks automatically' : syncState.apiAvailable === true ? 'Refresh content automatically' : 'Reading is available offline';
  if (!state.currentPost) $('#statusbarDetail').textContent = `${syncState.autoRefresh ? 'Auto-refresh on' : 'Manual refresh'}${due ? ` · Next check ${short}` : ''}`;
}
function renderRecentImports() {
  const entries = syncState.status?.recentAdded || [];
  $('#recentImportCount').textContent = entries.length ? `${entries.length} RECENT ${entries.length === 1 ? 'STUDY' : 'STUDIES'}` : 'READY FOR WHAT COMES NEXT';
  $('#recentImports').innerHTML = entries.length ? entries.slice(0, 12).map(entry => {
    const post = state.posts.find(item => item.id === String(entry.id));
    return post ? recentStudyHTML(post) : `<button class="recent-study" disabled>${icon('book')}<span><strong>${escapeHTML(entry.title)}</strong><small>Refresh your content to read this study.</small></span></button>`;
  }).join('') : '<div class="recent-study"><svg class="study-symbol"><use href="#i-book"/></svg><span><strong>Your library is ready for new studies.</strong><small>Newly collected Bible studies will appear here automatically.</small></span></div>';
}
function startSyncMonitor() {
  pollUpdateStatus({ force: true });
  syncState.pollTimer = setInterval(() => pollUpdateStatus(), 10000);
  syncState.clockTimer = setInterval(() => { if (!document.hidden) renderUpdateClock(); }, 1000);
}

function routeFromHash() {
  const passage = location.hash.match(/^#bible=(?:(kjv|mg):)?(\d+)\.(\d+)\.(\d+)$/);
  if (passage) { showView('scripture', { push: false }); KJVBible.go(Number(passage[2]) - 1, Number(passage[3]), Number(passage[4]), false, passage[1] || KJVBible.version); return; }
  const study = location.hash.match(/^#study=(.+)$/);
  if (study) { openStudy(decodeURIComponent(study[1]), false); return; }
  if (/^#section-/.test(location.hash) && state.currentPost) return;
  const view = location.hash.match(/^#view=(.+)$/)?.[1];
  const legacy = { '#studies': 'library', '#index': 'bible', '#paths': 'topics', '#timeline': 'timeline', '#home': 'home' };
  showView(view || legacy[location.hash] || 'home', { push: false, preserveFilters: true });
}
function wireEvents() {
  // Delegated controls keep working when refreshed archive metadata is rendered.
  document.addEventListener('click', event => {
    const button = event.target.closest('button, a[data-toc]');
    if (!button || button.disabled) return;
    if (button.dataset.skin) { setReadingSkin(button.dataset.skin); return; }
    if (button.dataset.colourTheme) { setColourTheme(button.dataset.colourTheme); return; }
    if (button.dataset.view) { closeSettings(); showView(button.dataset.view); return; }
    if (button.dataset.save) { event.stopPropagation(); toggleSave(button.dataset.save); return; }
    if (button.dataset.study) { openStudy(button.dataset.study); return; }
    if (button.dataset.filter) { setFilter(button.dataset.filter); return; }
    if (button.dataset.archiveBook) { selectBibleBook(button.dataset.archiveBook); return; }
    if (button.dataset.archiveCharacter) { selectCharacter(button.dataset.archiveCharacter); return; }
    if (button.dataset.archiveYear) { selectArchiveYear(Number(button.dataset.archiveYear)); return; }
    if (button.dataset.quickShelf || button.dataset.shelf) { selectShelf(button.dataset.quickShelf || button.dataset.shelf); return; }
    if (button.dataset.layout) { state.layout = button.dataset.layout; localStorage.setItem('gw-library-layout', state.layout); syncSettingsUI(); renderGrid(); return; }
    if (button.dataset.indexKind) {
      state.indexKind = button.dataset.indexKind;
      $$('[data-index-kind]').forEach(item => item.classList.toggle('active', item === button));
      $('#bookIndex').hidden = state.indexKind !== 'books'; $('#characterIndex').hidden = state.indexKind !== 'people'; $('#indexShelfControls').hidden = state.indexKind !== 'books'; return;
    }
    if (button.dataset.indexShelf) { state.indexShelf = button.dataset.indexShelf; $$('[data-index-shelf]').forEach(item => item.classList.toggle('active', item === button)); renderArchiveGuide(); return; }
    if (button.dataset.settingsTab) { selectSettingsTab(button.dataset.settingsTab); return; }
    if (button.dataset.font) { setFontSize(state.fontSize + (button.dataset.font === 'up' ? 1 : -1)); return; }
    if (button.dataset.toc) { event.preventDefault(); document.getElementById(button.dataset.toc)?.scrollIntoView({ block: 'start' }); }
  });
  for (const container of [els.studyGrid, els.relatedGrid]) {
    const activate = event => {
      if (event.target.closest('[data-save]')) return;
      const card = event.target.closest('.study-card');
      if (!card || (event.type === 'keydown' && !['Enter', ' '].includes(event.key))) return;
      if (event.type === 'keydown') event.preventDefault();
      openStudy(card.dataset.id);
    };
    container.addEventListener('click', activate); container.addEventListener('keydown', activate);
  }
  $('#settingsButton').addEventListener('click', () => openSettings());
  $('#closeSettings').addEventListener('click', closeSettings);
  $('#settingsOverlay').addEventListener('click', event => { if (event.target === $('#settingsOverlay')) closeSettings(); });
  $('#libraryFilters').addEventListener('click', () => openSettings('library'));
  $('#showUpdates').addEventListener('click', () => { closeSettings(); showView('updates'); });
  $('#menuButton').addEventListener('click', () => {
    if (window.innerWidth <= 700) document.body.classList.toggle('sidebar-open');
    else { document.body.classList.toggle('sidebar-collapsed'); localStorage.setItem('gw-sidebar-collapsed', String(document.body.classList.contains('sidebar-collapsed'))); }
    $('#menuButton').setAttribute('aria-expanded', String(!document.body.classList.contains('sidebar-collapsed')));
  });
  ['sortOrder', 'bibleShelf', 'bookFilter', 'characterFilter'].forEach(id => $(`#${id}`).addEventListener('change', applyLibrarySettings));
  $('#topicSettings').addEventListener('change', applyLibrarySettings);
  $('#quickSort').addEventListener('change', event => { state.sortOrder = event.target.value; persistLibrarySettings(); syncSettingsUI(); renderGrid(true); updateArticleNavigation(); });
  $('#resetSettings').addEventListener('click', resetSettings);
  $('#clearFilters').addEventListener('click', clearAll); $('#emptyClear').addEventListener('click', clearAll);
  let searchTimer;
  els.search.addEventListener('input', event => {
    state.query = event.target.value.trim(); state.yearFilter = null;
    if (state.currentPost || !['library', 'saved'].includes(state.view)) showView('library', { preserveFilters: true });
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => renderGrid(true), 180);
  });
  els.loadMore.addEventListener('click', () => { state.visible += 18; renderGrid(); });
  $('#heroReadButton').addEventListener('click', () => { if (state.posts.length) openStudy(state.posts[0].id); });
  $('#continueStudy').addEventListener('click', () => { if (state.posts.some(post => post.id === state.lastStudy)) openStudy(state.lastStudy, true, true); else showView('library'); });
  $('#backButton').addEventListener('click', () => closeStudy());
  $('#articleSave').addEventListener('click', () => { if (state.currentPost) toggleSave(state.currentPost.id); });
  $('#endSave').addEventListener('click', () => { if (state.currentPost) toggleSave(state.currentPost.id); });
  $('#articlePrev').addEventListener('click', () => moveStudy(-1)); $('#articleNext').addEventListener('click', () => moveStudy(1));
  $('#readerTheme').addEventListener('click', toggleTheme);
  $('#warmEveningPreset').addEventListener('click', () => { setColourTheme('terracotta'); setReadingSkin('dark'); });
  $('#resetAppearance').addEventListener('click', () => { setColourTheme('forest'); setReadingSkin('light'); });
  $('#readingSize').addEventListener('input', event => setFontSize(event.target.value));
  for (const id of ['checkNow', 'toolbarCheckNow', 'settingsCheckNow']) $(`#${id}`).addEventListener('click', requestUpdateCheck);
  for (const id of ['automaticChecks', 'updatesEnabled']) $(`#${id}`).addEventListener('change', event => saveUpdateSettings({ enabled: event.target.checked }));
  for (const id of ['automaticRefresh', 'updatesAutoRefresh']) $(`#${id}`).addEventListener('change', event => saveUpdateSettings({ autoRefresh: event.target.checked }));
  for (const id of ['refreshArchive', 'applyArchiveUpdate']) $(`#${id}`).addEventListener('click', () => refreshArchive().catch(() => {}));
  els.scroll.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('popstate', routeFromHash);
  for (const event of ['focus', 'online', 'pageshow']) window.addEventListener(event, () => { if (state.ready) pollUpdateStatus({ force: true }); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && state.ready) pollUpdateStatus({ force: true }); });
  window.addEventListener('beforeunload', () => { saveReadingPosition(); clearInterval(syncState.pollTimer); clearInterval(syncState.clockTimer); });
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchStudies(); }
    if ((event.metaKey || event.ctrlKey) && event.key === ',') { event.preventDefault(); openSettings(); }
    if (event.key === 'Escape') { if (!$('#settingsPanel').hidden) closeSettings(); else if (document.body.classList.contains('sidebar-open')) document.body.classList.remove('sidebar-open'); else if (state.currentPost) closeStudy(); }
    if (!$('#settingsPanel').hidden && event.key === 'Tab') {
      const focusable = $$('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]', $('#settingsPanel')).filter(element => element.getClientRects().length);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === $('#settingsPanel'))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    const tab = event.target.closest('[data-settings-tab]');
    if (tab && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
      event.preventDefault(); const tabs = $$('[data-settings-tab]');
      const next = tabs[(tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : 2)) % tabs.length]; selectSettingsTab(next.dataset.settingsTab); next.focus();
    }
  });
}

async function init() {
  wireEvents();
  if (localStorage.getItem('gw-sidebar-collapsed') === 'true') document.body.classList.add('sidebar-collapsed');
  applyReadingMode();
  try {
    const [archive, policy] = await Promise.all([loadArchiveData(), fetchJSON('content-policy.json')]);
    state.policy = policy; hydrateArchive(archive.data); syncState.revision = archive.revision;
    renderArchiveViews(); state.ready = true; routeFromHash(); startSyncMonitor(); StudyLanguages.startLibrary();
  } catch (error) {
    console.error(error);
    $('#heroTitle').textContent = 'Your library could not open.';
    $('#heroExcerpt').textContent = 'Reopen the app to restart the local study service.';
    els.studyGrid.innerHTML = '<div class="empty-state"><h2>We could not open the study library.</h2><p>Reopen Gospel Warrior to restart its local archive service.</p></div>';
  }
}
init();
