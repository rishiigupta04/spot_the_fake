const BADGE_ID = 'spot-the-fake-badge'

function ensureBadge() {
  let badge = document.getElementById(BADGE_ID)
  if (badge) return badge

  badge = document.createElement('div')
  badge.id = BADGE_ID
  badge.style.position = 'fixed'
  badge.style.top = '12px'
  badge.style.right = '12px'
  badge.style.zIndex = '2147483647'
  badge.style.padding = '8px 10px'
  badge.style.borderRadius = '10px'
  badge.style.fontFamily = 'Segoe UI, Arial, sans-serif'
  badge.style.fontSize = '12px'
  badge.style.lineHeight = '1.3'
  badge.style.maxWidth = '240px'
  badge.style.background = '#1f2937'
  badge.style.color = '#f9fafb'
  badge.style.boxShadow = '0 8px 22px rgba(0, 0, 0, 0.25)'
  badge.style.border = '1px solid rgba(255, 255, 255, 0.12)'
  badge.textContent = 'Spot the Fake: scanning...'

  document.documentElement.appendChild(badge)
  return badge
}

function getStyleForRisk(payload) {
  const risk = String(payload?.risk_level || '').toLowerCase()
  if (payload?.status === 'error') {
    return { bg: '#7f1d1d', border: '#ef4444', label: 'Error' }
  }
  if (risk === 'high') {
    return { bg: '#7f1d1d', border: '#ef4444', label: 'High risk' }
  }
  if (risk === 'medium') {
    return { bg: '#78350f', border: '#f59e0b', label: 'Medium risk' }
  }
  if (risk === 'low') {
    return { bg: '#14532d', border: '#22c55e', label: 'Low risk' }
  }
  return { bg: '#1f2937', border: '#9ca3af', label: 'Unknown' }
}

function renderBadge(payload) {
  const badge = ensureBadge()
  const style = getStyleForRisk(payload)

  badge.style.background = style.bg
  badge.style.borderColor = style.border

  const probability =
    typeof payload?.phishing_probability === 'number'
      ? `${Math.round(payload.phishing_probability * 100)}%`
      : 'n/a'

  const statusLine = payload?.status === 'error'
    ? `Spot the Fake: ${payload?.error || 'Scan failed'}`
    : `Spot the Fake: ${style.label}`

  const detailLine = payload?.status === 'error'
    ? ''
    : `Phishing probability: ${probability}`

  badge.innerHTML = `${statusLine}${detailLine ? `<br>${detailLine}` : ''}`
}

function requestScan() {
  chrome.runtime.sendMessage({ type: 'SPOT_FAKE_SCAN_CURRENT' })
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'SPOT_FAKE_BADGE_UPDATE') {
    renderBadge(message.payload)
  }
})

let lastHref = location.href
setInterval(() => {
  if (location.href !== lastHref) {
    lastHref = location.href
    renderBadge({ status: 'ok', risk_level: 'unknown' })
    requestScan()
  }
}, 1000)

renderBadge({ status: 'ok', risk_level: 'unknown' })
requestScan()