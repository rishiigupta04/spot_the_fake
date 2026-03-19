const DEFAULT_API_BASE = 'http://localhost:5000'
const DEFAULT_CACHE_TTL_MS = 5 * 60 * 1000
const scanCache = new Map()

const isHttpUrl = (value) => /^https?:\/\//i.test(value || '')

async function getSettings() {
  const settings = await chrome.storage.sync.get({
    apiBaseUrl: DEFAULT_API_BASE,
    cacheTtlMs: DEFAULT_CACHE_TTL_MS,
  })

  return {
    apiBaseUrl: String(settings.apiBaseUrl || DEFAULT_API_BASE).replace(/\/+$/, ''),
    cacheTtlMs: Number(settings.cacheTtlMs) > 0 ? Number(settings.cacheTtlMs) : DEFAULT_CACHE_TTL_MS,
  }
}

function toCacheKey(url) {
  try {
    const parsed = new URL(url)
    return parsed.hostname.toLowerCase()
  } catch (_) {
    return null
  }
}

async function fetchRisk(url) {
  const { apiBaseUrl } = await getSettings()
  const endpoint = `${apiBaseUrl}/predict-lite`

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = await response.json()
      message = payload?.error?.message || message
    } catch (_) {
      // Keep fallback status text if body is not JSON.
    }
    throw new Error(message)
  }

  const payload = await response.json()
  return payload?.result || payload
}

async function getRiskWithCache(url) {
  const key = toCacheKey(url)
  const { cacheTtlMs } = await getSettings()

  if (key && scanCache.has(key)) {
    const cached = scanCache.get(key)
    if (Date.now() - cached.timestamp < cacheTtlMs) {
      return cached.result
    }
    scanCache.delete(key)
  }

  const result = await fetchRisk(url)
  if (key) {
    scanCache.set(key, { result, timestamp: Date.now() })
  }
  return result
}

async function scanAndPublish(tabId, url) {
  if (!isHttpUrl(url)) return

  const basePayload = {
    url,
    status: 'ok',
    risk_level: 'unknown',
    verdict: 'unknown',
    phishing_probability: null,
  }

  try {
    const result = await getRiskWithCache(url)
    const payload = {
      ...basePayload,
      ...result,
    }

    await chrome.tabs.sendMessage(tabId, {
      type: 'SPOT_FAKE_BADGE_UPDATE',
      payload,
    })
  } catch (error) {
    await chrome.tabs.sendMessage(tabId, {
      type: 'SPOT_FAKE_BADGE_UPDATE',
      payload: {
        ...basePayload,
        status: 'error',
        error: error?.message || 'Scan failed',
      },
    })
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab?.url) {
    scanAndPublish(tabId, tab.url)
  }
})

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const tab = await chrome.tabs.get(tabId)
  if (tab?.url) {
    scanAndPublish(tabId, tab.url)
  }
})

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'SPOT_FAKE_SCAN_CURRENT') return

  const tabId = sender?.tab?.id
  const url = sender?.tab?.url
  if (!tabId || !url) {
    sendResponse({ ok: false })
    return
  }

  scanAndPublish(tabId, url)
  sendResponse({ ok: true })
})