import React, { useMemo, useState } from 'react'
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Chip,
  Stack,
  Divider,
} from '@mui/material'

const getHostname = (value) => {
  try {
    return new URL(value).hostname.toLowerCase()
  } catch (_) {
    return (value || '').toLowerCase()
  }
}

export default function HistoryWatchlistPanel({ history, setHistory, watchlist, setWatchlist }) {
  const [query, setQuery] = useState('')
  const [watchInput, setWatchInput] = useState('')
  const [clearAlertsBefore, setClearAlertsBefore] = useState(null)

  const getSeverity = (entry, impersonationLikely) => {
    const urgency = String(entry?.urgency || '').toLowerCase()
    const verdict = String(entry?.verdict || '').toLowerCase()
    if (impersonationLikely || urgency === 'critical') return 'critical'
    if (urgency === 'high' || verdict === 'phishing') return 'high'
    if (urgency === 'medium') return 'medium'
    return 'low'
  }

  const filteredHistory = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return history

    return history.filter((item) => {
      const blob = [
        item.url,
        item.verdict,
        item.urgency,
        item.brand,
        item.llmRisk,
      ].join(' ').toLowerCase()
      return blob.includes(q)
    })
  }, [history, query])

  const alerts = useMemo(() => {
    if (!watchlist.length || !history.length) return []

    const items = []
    const seen = new Set()
    for (const entry of history) {
      const host = getHostname(entry.url)
      const brand = (entry.brand || '').toLowerCase()
      const sim = Number(entry.similarityScore || 0)
      const verdict = String(entry.verdict || '').toLowerCase()
      const urgency = String(entry.urgency || '').toLowerCase()

      for (const watched of watchlist) {
        const needle = watched.toLowerCase()
        const mentionsWatchedBrand = brand.includes(needle) || host.includes(needle)
        const impersonationLikely = sim >= 0.65 && brand.includes(needle) && !host.includes(needle)
        const suspicious = verdict === 'phishing' || urgency === 'high' || urgency === 'critical'

        if (mentionsWatchedBrand && (impersonationLikely || suspicious)) {
          const dedupeKey = `${needle}|${entry.url}|${entry.verdict}|${entry.urgency}|${Math.round(sim * 100)}`
          if (seen.has(dedupeKey)) continue
          seen.add(dedupeKey)

          const severity = getSeverity(entry, impersonationLikely)
          items.push({
            id: `${entry.id}-${needle}`,
            watch: watched,
            url: entry.url,
            severity,
            reason: impersonationLikely
              ? `Potential impersonation (${Math.round(sim * 100)}% similarity)`
              : `Flagged as ${entry.verdict || 'suspicious'} with ${entry.urgency || 'unknown'} urgency`,
            timestamp: entry.timestamp,
          })
        }
      }

      if (items.length >= 20) break
    }

    return items
  }, [history, watchlist])

  const visibleAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (!clearAlertsBefore) return true
      return new Date(a.timestamp).getTime() > clearAlertsBefore
    })
  }, [alerts, clearAlertsBefore])

  const addWatch = () => {
    const value = watchInput.trim().toLowerCase()
    if (!value) return
    if (watchlist.includes(value)) return
    setWatchlist((prev) => [value, ...prev].slice(0, 50))
    setWatchInput('')
  }

  const removeWatch = (target) => {
    setWatchlist((prev) => prev.filter((item) => item !== target))
  }

  const severityChipColor = (severity) => {
    if (severity === 'critical' || severity === 'high') return 'error'
    if (severity === 'medium') return 'warning'
    return 'success'
  }

  return (
    <Paper sx={{ p: 2, mt: 2 }} elevation={1}>
      <Typography variant="h6" gutterBottom>
        History + Watchlist Dashboard
      </Typography>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
        <TextField
          size="small"
          label="Track brand/domain"
          value={watchInput}
          onChange={(e) => setWatchInput(e.target.value)}
          sx={{ minWidth: 240 }}
        />
        <Button variant="contained" onClick={addWatch}>Add Watch</Button>
      </Box>

      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mb: 2 }}>
        {watchlist.map((item) => (
          <Chip key={item} label={item} onDelete={() => removeWatch(item)} sx={{ mt: 1 }} />
        ))}
        {!watchlist.length && <Typography variant="body2" sx={{ opacity: 0.75 }}>No watch items yet.</Typography>}
      </Stack>

      <Divider sx={{ mb: 2 }} />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, flex: 1 }}>Watch Alerts</Typography>
        <Button size="small" variant="outlined" onClick={() => setClearAlertsBefore(Date.now())}>
          Clear Alerts
        </Button>
      </Box>
      <Box sx={{ mt: 1, mb: 2 }}>
        {visibleAlerts.slice(0, 8).map((alert) => (
          <Paper key={alert.id} sx={{ p: 1.25, mb: 1, bgcolor: '#2d1a1a' }} elevation={0}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, flex: 1 }}>[{alert.watch}] {alert.reason}</Typography>
              <Chip size="small" label={alert.severity} color={severityChipColor(alert.severity)} />
            </Box>
            <Typography variant="caption" sx={{ opacity: 0.85 }}>{alert.url}</Typography>
          </Paper>
        ))}
        {!visibleAlerts.length && <Typography variant="body2" sx={{ opacity: 0.75 }}>No active alerts.</Typography>}
      </Box>

      <Divider sx={{ mb: 2 }} />

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, flex: 1 }}>Previous Scans</Typography>
        <Button size="small" color="error" variant="outlined" onClick={() => setHistory([])}>
          Clear History
        </Button>
        <TextField
          size="small"
          label="Search history"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          sx={{ minWidth: 240 }}
        />
      </Box>

      <Box sx={{ maxHeight: 320, overflowY: 'auto' }}>
        {filteredHistory.slice(0, 100).map((entry) => (
          <Paper key={entry.id} sx={{ p: 1.25, mb: 1, bgcolor: 'rgba(255,255,255,0.02)' }} elevation={0}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, flex: 1 }}>
              {entry.verdict || 'unknown'} | urgency: {entry.urgency || 'low'} | similarity: {entry.similarityScore != null ? `${Math.round(entry.similarityScore * 100)}%` : 'n/a'}
              </Typography>
              <Chip
                size="small"
                label={entry.urgency || 'low'}
                color={severityChipColor(entry.urgency || 'low')}
              />
            </Box>
            <Typography variant="caption" sx={{ display: 'block', opacity: 0.85 }}>{entry.url}</Typography>
            <Typography variant="caption" sx={{ opacity: 0.7 }}>{new Date(entry.timestamp).toLocaleString()}</Typography>
          </Paper>
        ))}
        {!filteredHistory.length && <Typography variant="body2" sx={{ opacity: 0.75 }}>No matching history yet.</Typography>}
      </Box>
    </Paper>
  )
}