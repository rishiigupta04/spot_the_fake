const DEFAULTS = {
  apiBaseUrl: 'http://localhost:5000',
  cacheTtlMs: 5 * 60 * 1000,
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get(DEFAULTS)
  document.getElementById('apiBaseUrl').value = settings.apiBaseUrl || DEFAULTS.apiBaseUrl
  document.getElementById('cacheTtlMs').value = String(settings.cacheTtlMs || DEFAULTS.cacheTtlMs)
}

async function saveSettings() {
  const apiBaseUrl = (document.getElementById('apiBaseUrl').value || DEFAULTS.apiBaseUrl).trim().replace(/\/+$/, '')
  const cacheTtlMsRaw = Number(document.getElementById('cacheTtlMs').value)
  const cacheTtlMs = Number.isFinite(cacheTtlMsRaw) && cacheTtlMsRaw > 0 ? cacheTtlMsRaw : DEFAULTS.cacheTtlMs

  await chrome.storage.sync.set({ apiBaseUrl, cacheTtlMs })

  const status = document.getElementById('status')
  status.textContent = 'Settings saved.'
  window.setTimeout(() => {
    status.textContent = ''
  }, 1500)
}

document.getElementById('saveButton').addEventListener('click', saveSettings)
loadSettings()