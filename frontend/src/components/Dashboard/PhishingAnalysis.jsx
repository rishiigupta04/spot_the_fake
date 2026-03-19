import React from 'react'
import { Paper, Typography, Box, Chip, CircularProgress, List, ListItem, ListItemText, Stack, Divider } from '@mui/material'
import BugReportIcon from '@mui/icons-material/BugReport'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'

export default function PhishingAnalysis({ result }) {
  if (!result) return null
  const legitScore = Math.max(0, Math.min(1, result.ml_confidence ?? 0))
  const phishingBadge = result.ml_prediction === 'phishing'
  const badgeColor = phishingBadge ? 'error' : 'success'
  const urgency = result?.urgency?.level || 'low'
  const riskSignals = result?.risk_signals || {}
  const domainAge = riskSignals?.domain?.age_days
  const registrarRep = riskSignals?.domain?.registrar_reputation
  const sslValid = riskSignals?.ssl?.valid
  const redirectDepth = riskSignals?.redirect?.depth
  const networkRep = riskSignals?.network?.asn_reputation || riskSignals?.network?.ip_reputation
  const sensitive = riskSignals?.sensitive_fields || {}

  const recommended = phishingBadge
    ? 'Treat as suspicious — avoid entering credentials and verify source.'
    : 'Likely legitimate — proceed with caution and verify identity if needed.'

  return (
    <Paper
      sx={{
        p: 2.25,
        background: theme => theme.palette.mode === 'dark'
          ? 'linear-gradient(180deg,#061426 0%,#071226 100%)'
          : theme.palette.background.paper,
        color: theme => theme.palette.text.primary,
        borderRadius: 2,
        boxShadow: theme => theme.palette.mode === 'dark'
          ? '0 6px 18px rgba(2,6,23,0.6)'
          : '0 4px 10px rgba(2,6,23,0.06)'
      }}
      elevation={0}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, letterSpacing: 0.2 }}>
            Phishing Detection
          </Typography>
          <Typography variant="caption" sx={{ opacity: 0.78 }}>
            Lightweight ML + LLM ensemble
          </Typography>
        </Box>
        <Chip
          icon={<BugReportIcon />}
          label={(result.ml_prediction || 'unknown').toUpperCase()}
          color={badgeColor}
          sx={{ fontWeight: 700, px: 1.5 }}
        />
      </Box>

      {/* Score + ML explanations */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', my: 2 }}>
        <Box sx={{ position: 'relative', width: 100, height: 100, display: 'grid', placeItems: 'center' }}>
          <CircularProgress
            variant="determinate"
            value={legitScore * 100}
            size={92}
            thickness={5}
            sx={{ '& .MuiCircularProgress-circle': { strokeLinecap: 'round' } }}
          />
          <Box sx={{ position: 'absolute', textAlign: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              {Math.round(legitScore * 100)}%
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', opacity: 0.75 }}>
              Legitimacy
            </Typography>
          </Box>
        </Box>

        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>
            Confidence & key indicators
          </Typography>
          <List dense>
            {(result.ml_explanations || []).slice(0, 5).map((t, i) => (
              <ListItem key={i} sx={{ py: 0 }}>
                <ListItemText primary={t} primaryTypographyProps={{ variant: 'body2' }} />
              </ListItem>
            ))}
            {(!(result.ml_explanations || []).length) && (
              <ListItem sx={{ py: 0 }}>
                <ListItemText
                  primary="No strong ML indicators available."
                  primaryTypographyProps={{ variant: 'body2', sx: { opacity: 0.78 } }}
                />
              </ListItem>
            )}
          </List>

          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Chip
              icon={<CheckCircleIcon />}
              label={`ML Confidence: ${Math.round((result.ml_confidence ?? 0) * 100)}%`}
              color="primary"
              size="small"
            />
            <Chip
              icon={<WarningAmberIcon />}
              label={`LLM: ${result.llm_risk_level ?? 'unknown'}`}
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.04)', color: '#e6eef8' }}
            />
          </Stack>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255,255,255,0.04)', my: 1 }} />

      <Box sx={{ mt: 1.5 }}>
        <Typography variant="caption" sx={{ opacity: 0.8, fontWeight: 700 }}>
          Risk Signals
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mt: 0.75 }}>
          <Chip size="small" label={`Urgency: ${String(urgency).toUpperCase()}`} color={urgency === 'critical' || urgency === 'high' ? 'error' : urgency === 'medium' ? 'warning' : 'success'} />
          <Chip size="small" label={`Domain age: ${typeof domainAge === 'number' ? `${domainAge}d` : 'unknown'}`} />
          <Chip size="small" label={`Registrar: ${registrarRep || 'unknown'}`} />
          <Chip size="small" label={`SSL: ${sslValid === true ? 'valid' : sslValid === false ? 'invalid' : 'unknown'}`} />
          <Chip size="small" label={`Redirects: ${typeof redirectDepth === 'number' ? redirectDepth : 'n/a'}`} />
          <Chip size="small" label={`Network: ${networkRep || 'unknown'}`} />
        </Stack>
        {(sensitive?.has_password_field || sensitive?.has_payment_indicator) && (
          <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
            Sensitive fields detected (password/payment). Treat this page with extra caution.
          </Typography>
        )}
      </Box>

      {/* AI Insight */}
      <Box sx={{ mt: 1 }}>
        <Typography variant="caption" sx={{ opacity: 0.8, fontWeight: 700 }}>
          AI Insight
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          {result.llm_prediction
            ? `${result.llm_prediction} (${result.llm_risk_level})`
            : 'No LLM judgement available.'}
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.8 }}>
          LLM status: {result.llm_status || 'unknown'}
        </Typography>
        {result.llm_error && (
          <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 0.25 }}>
            LLM fallback reason: {result.llm_error}
          </Typography>
        )}

        {/* LLM full explanation */}
        {(result.llm_reasons || []).length > 0 && (
          <Box sx={{ mt: 1.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              LLM Explanation
            </Typography>
            <List dense sx={{ mt: 0.5 }}>
              {result.llm_reasons.slice(0, 5).map((reason, i) => (
                <ListItem key={i} sx={{ py: 0 }}>
                  <ListItemText primary={reason} primaryTypographyProps={{ variant: 'body2' }} />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Evidence snippets */}
        {(result.evidence_snippets || []).length > 0 && (
          <Box sx={{ mt: 1.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Evidence Snippets
            </Typography>
            <List dense sx={{ mt: 0.5 }}>
              {result.evidence_snippets.slice(0, 3).map((s, i) => (
                <ListItem key={i} sx={{ py: 0 }}>
                  <ListItemText primary={s} primaryTypographyProps={{ variant: 'body2' }} />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Recommendation */}
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Recommended action
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.85 }}>
            {recommended}
          </Typography>
        </Box>
      </Box>
    </Paper>
  )
}