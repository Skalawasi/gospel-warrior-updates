/* Android's offline companion reuses the reader without a desktop service. */
(() => {
  const COMPILED_UPDATE_BASE_URL = '__GOSPEL_WARRIOR_UPDATE_BASE_URL__';
  const normalizeBase = value => String(value || '')
    .replace(/\\/g, '')
    .trim()
    .replace(/\/+$/, '');
  let updateBase = normalizeBase(localStorage.getItem('gw-update-base-url') || COMPILED_UPDATE_BASE_URL);
  let remoteUpdatesEnabled = /^https?:\/\//i.test(updateBase);
  window.gospelAndroidRemoteUpdates = remoteUpdatesEnabled;
  document.documentElement.classList.toggle('gospel-remote-enabled', remoteUpdatesEnabled);

  const remoteURL = (path, query = '') => `${updateBase}${path}${query}`;
  const archiveCacheRequest = () => new Request(`${location.origin}/content.json.gz`);
  const cacheArchive = response => {
    if (!response?.ok || !window.caches) return response;
    return caches.open('gospel-warrior-android-archive').then(cache => {
      cache.put(archiveCacheRequest(), response.clone()).catch(() => {});
      return response;
    }).catch(() => response);
  };
  const cachedArchive = () => window.caches
    ? caches.open('gospel-warrior-android-archive').then(cache => cache.match(archiveCacheRequest()))
    : Promise.resolve(undefined);
  localStorage.setItem('gw-study-language', 'en');

  const fetchOriginal = window.fetch.bind(window);
  window.fetch = (input, options) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (remoteUpdatesEnabled && url.origin === location.origin && url.pathname === '/content.json.gz') {
      return fetchOriginal(remoteURL(url.pathname, url.search), options)
        .then(cacheArchive)
        .catch(async error => (await cachedArchive()) || Promise.reject(error));
    }
    if (remoteUpdatesEnabled && url.origin === location.origin && url.pathname.startsWith('/api/')) {
      // A static GitHub raw-content repository cannot run the desktop Python
      // API. Its generated status document is the read-only equivalent of
      // GET /api/update/status. Check and settings controls are handled by
      // study-app.js so they do not issue unsupported POST requests.
      if (url.pathname === '/api/update/status') {
        const separator = updateBase.includes('?') ? '&' : '?';
        return fetchOriginal(remoteURL('/update-status.json', `${separator}v=${Date.now()}`), options);
      }
      return fetchOriginal(remoteURL(url.pathname, url.search), options);
    }
    if (!remoteUpdatesEnabled && url.origin === location.origin && url.pathname.startsWith('/api/')) {
      if (url.pathname === '/api/update/status') {
        return Promise.resolve(new Response(JSON.stringify({
          apiAvailable: false, state: 'offline', schedulerEnabled: false,
          automaticChecksEnabled: false, autoRefresh: false, recentAdded: []
        }), { headers: { 'Content-Type': 'application/json' } }));
      }
      return Promise.resolve(new Response('{}', { status: 503,
        headers: { 'Content-Type': 'application/json' } }));
    }
    return fetchOriginal(input, options);
  };

  if (window.GospelAndroid) {
    const clipboard = { writeText: async text => GospelAndroid.copyText(String(text)) };
    try { Object.defineProperty(navigator, 'clipboard', { value: clipboard }); } catch (_) { /* Web copy fallback remains available. */ }
  }

  window.gospelAndroidBack = () => {
    if (!document.getElementById('settingsPanel')?.hidden) { closeSettings(); return true; }
    if (document.body.classList.contains('sidebar-open')) {
      document.body.classList.remove('sidebar-open'); return true;
    }
    if (!document.getElementById('studyNotebook')?.hidden) {
      document.getElementById('closeNotebook').click(); return true;
    }
    if (!document.getElementById('bibleWordTooltip')?.hidden) { KJVBible.dismiss(); return true; }
    return false;
  };

  document.addEventListener('DOMContentLoaded', () => {
    const sourceSection = document.createElement('section');
    sourceSection.className = 'android-update-source preferences-card';
    sourceSection.innerHTML = `<div class="section-title"><h2>Android update source</h2><span class="subtle-label">PUBLIC HTTPS URL</span></div><p>Enter the public URL where the Gospel Warrior update server is running. The app keeps the latest downloaded archive available offline.</p><form><label for="androidUpdateBaseUrl">Update server URL</label><div class="android-update-source-row"><input id="androidUpdateBaseUrl" type="url" inputmode="url" autocomplete="url" placeholder="https://studies.example.com" value="${escapeHTML(updateBase)}"/><button class="button button-primary" type="submit">Save URL</button></div><small id="androidUpdateSourceStatus">${remoteUpdatesEnabled ? 'Connected update source configured.' : 'No remote update source configured.'}</small></form>`;
    document.getElementById('updateSettings').prepend(sourceSection);
    sourceSection.querySelector('form').addEventListener('submit', event => {
      event.preventDefault();
      const value = normalizeBase(sourceSection.querySelector('#androidUpdateBaseUrl').value);
      if (value && !/^https?:\/\//i.test(value)) {
        sourceSection.querySelector('#androidUpdateSourceStatus').textContent = 'Use a URL beginning with https://.';
        return;
      }
      if (value) localStorage.setItem('gw-update-base-url', value);
      else localStorage.removeItem('gw-update-base-url');
      location.reload();
    });

    const status = remoteUpdatesEnabled
      ? 'This Android app checks the Gospel Warrior update server while it is open. New studies are downloaded and merged into your local library without removing saved studies, notes, bookmarks, or reading progress.'
      : 'The complete English study archive and both Bible versions are available offline. Library additions arrive with a newer Android APK. Build with a public update-server URL to enable automatic fetching.';
    if (!remoteUpdatesEnabled) {
      const observer = new MutationObserver(() => {
        document.getElementById('updateStatusMessage').textContent = status;
        document.getElementById('updateStatusTitle').textContent = 'Your offline Android library';
        document.getElementById('lastCheckDetail').textContent = 'Bundled with this app';
        document.getElementById('nextCheckTime').textContent = 'Build with an update-server URL to enable updates';
      });
      observer.observe(document.getElementById('updateStatusLabel'), { childList: true });
    }
    if (remoteUpdatesEnabled) {
      sourceSection.querySelector('#androidUpdateSourceStatus').textContent = `Connected to ${updateBase}.`;
    }
    document.querySelector('#updates .view-heading p').textContent = remoteUpdatesEnabled
      ? 'New Bible studies are collected quietly while Gospel Warrior is open.'
      : 'Your complete reading library, included in the Android app.';
    document.querySelector('#updates .quiet-note').textContent = status;
    document.querySelector('#updateSettings .settings-description').textContent = status;
    if (!remoteUpdatesEnabled) {
      document.querySelector('#updates .update-stats > div:first-child').hidden = true;
      document.querySelector('#updates .preferences-card').hidden = true;
      document.querySelectorAll('#updateSettings .toggle-row, .settings-update-symbol').forEach(element => { element.hidden = true; });
    }
    document.querySelector('.settings-footer kbd').textContent = 'Back to close';
    document.getElementById('bibleReaderHint').textContent = 'Tap a word for its Hebrew or Greek dictionary meaning.';
    document.querySelectorAll('[data-study-language]:not([data-study-language="en"])').forEach(button => { button.hidden = true; });
    if (!remoteUpdatesEnabled) {
      document.getElementById('recentImports').parentElement.querySelector('.section-title').hidden = true;
      document.getElementById('recentImports').hidden = true;
    }
  });

  document.addEventListener('error', event => {
    const image = event.target;
    if (!remoteUpdatesEnabled || image?.tagName !== 'IMG' || image.dataset.remoteTried) return;
    const source = new URL(image.src, location.href);
    if (source.origin !== location.origin || !source.pathname.startsWith('/assets/')) return;
    image.dataset.remoteTried = 'true';
    image.src = remoteURL(source.pathname, source.search);
  }, true);
})();
