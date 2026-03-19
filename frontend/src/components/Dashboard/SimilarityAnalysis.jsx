import React, { useState } from 'react'
import {
  Paper, Typography, Box, LinearProgress, Grid, Chip, Stack,
  Dialog, DialogContent, IconButton, Divider
} from '@mui/material'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import CloseIcon from '@mui/icons-material/Close'
import { motion } from 'framer-motion'
import SimilarityExplainModal from './SimilarityExplainModal'
import { buildStaticAssetUrl } from '../../config/api'

export default function SimilarityAnalysis({ simResult, simLoading, simError }) {
  const [openImg, setOpenImg] = useState(false)
  const [imgSrc, setImgSrc] = useState('')
  const [imgCaption, setImgCaption] = useState('')
  const [explainOpen, setExplainOpen] = useState(false);

  const openImage = (src, caption) => {
    setImgSrc(src)
    setImgCaption(caption)
    setOpenImg(true)
  }

  const closeImage = () => setOpenImg(false)

  const result = simResult?.result ?? simResult
  const score = result?.score ?? null
  const details = result?.details ?? {}
  const assessment = result?.assessment || details?.assessment || null
  const confidence =
    typeof result?.confidence === 'number'
      ? result.confidence
      : typeof details?.confidence === 'number'
        ? details.confidence
        : null
  const ocr = details?.ocr ?? null

  const simErrorMessage =
    typeof simError === 'string'
      ? simError
      : simError?.error?.message || simError?.message || null

  // Ensure score is a number and round to 2 decimals to avoid floating point issues
  const numericScore = score !== null ? Number(Number(score).toFixed(2)) : null;

  // Unify thresholds for level and progress bar color
  const level = numericScore == null
    ? null
    : numericScore >= 0.9
      ? 'Legit'
      : numericScore >= 0.65
        ? 'High'
        : numericScore >= 0.30
          ? 'Moderate'
          : 'Low'

  const refFile = result?.reference_image?.split(/[/\\]/).pop()
  const userFile = result?.user_screenshot?.split(/[/\\]/).pop()

  const refSrc = result?.reference_image_url || buildStaticAssetUrl('brands', refFile)
  const userSrc = result?.user_screenshot_url || buildStaticAssetUrl('user', userFile)
  const breakdownKeys = ['image', 'color', 'text', 'structure']
  const riskLevel = (assessment?.risk_level || '').toLowerCase()
  const riskChipColor =
    riskLevel === 'critical' || riskLevel === 'high'
      ? 'error'
      : riskLevel === 'medium'
        ? 'warning'
        : 'success'

  return (
    <Paper
      sx={{
        p: 2.25,
        /* match other dashboard cards: use paper background so this card blends with the rest */
        background: theme => theme.palette.background.paper,
        borderRadius: 2,
        boxShadow: theme => theme.palette.mode === 'dark' ? '0 6px 18px rgba(2,6,23,0.55)' : '0 4px 10px rgba(2,6,23,0.06)',
        fontFamily: 'Inter, sans-serif'
      }}
      elevation={0}
      component={motion.div}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Website Similarity Analysis
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.65 }}>
            Comparing submitted screenshot against known brand assets
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {assessment?.risk_level && (
            <Chip
              label={`Risk: ${String(assessment.risk_level).toUpperCase()}`}
              size="small"
              color={riskChipColor}
            />
          )}
          <Chip
            icon={<CompareArrowsIcon />}
            label={level || 'No Data'}
            sx={{
              background: level === 'Legit'
                ? 'linear-gradient(90deg,#1976d2,#64b5f6)'
                : level === 'High'
                  ? 'linear-gradient(90deg,#ff4d4d,#d32f2f)'
                  : level === 'Moderate'
                    ? 'linear-gradient(90deg,#ffb74d,#f57c00)'
                    : 'linear-gradient(90deg,#4db6ac,#00796b)',
              color: '#fff',
              fontWeight: 600
            }}
          />
          <IconButton aria-label="Explain similarity analysis" onClick={() => setExplainOpen(true)} size="small" sx={{ ml: 1 }}>
            <span style={{ fontSize: "16px" }} role="img" aria-label="info">How❓</span>
          </IconButton>
        </Box>
      </Box>
      <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)', mb: 2 }} />

      {/* Content */}
      <Box sx={{ mt: 2 }}>
        {simLoading && <Typography>Checking similarity...</Typography>}
        {simErrorMessage && <Typography color="error">{simErrorMessage}</Typography>}

        {numericScore !== null && (
          <Box>
            {assessment?.headline && (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  {assessment.headline}
                </Typography>
                {assessment?.summary && (
                  <Typography variant="body2" sx={{ opacity: 0.86 }}>
                    {assessment.summary}
                  </Typography>
                )}
                <Typography variant="caption" sx={{ opacity: 0.75 }}>
                  Domain alignment: {
                    assessment?.domain_alignment === true
                      ? 'matched'
                      : assessment?.domain_alignment === false
                        ? 'mismatch'
                        : 'not available'
                  }
                  {confidence !== null && ` | Confidence: ${Math.round(confidence * 100)}%`}
                </Typography>
              </Box>
            )}

            {/* Overall score */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
                <Typography variant="h3" sx={{ fontWeight: 900, color: '#4db6ac' }}>
                  {Math.round(numericScore*100)}%
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.75 }}>
                  Overall similarity
                </Typography>
              </motion.div>

              <Box sx={{ flex: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={numericScore*100}
                  sx={{
                    height: 12,
                    borderRadius: 6,
                    background: 'rgba(255,255,255,0.05)',
                    '& .MuiLinearProgress-bar': {
                      background: numericScore >= 0.9
                        ? '#1976d2' // blue for legit
                        : numericScore >= 0.65
                          ? '#e57373' // red for high
                          : numericScore >= 0.35
                            ? '#ffb74d' // orange for moderate
                            : '#4db6ac' // green for low
                    }
                  }}
                />
                <Typography variant="body2" sx={{ mt:1, opacity: 0.85 }}>
                  {assessment?.summary || (
                    <>
                      {level === 'Legit' && '✅ Very high resemblance to known brand assets.'}
                      {level === 'High' && '⚠️ High resemblance — possible impersonation depending on domain context.'}
                      {level === 'Moderate' && '🔶 Moderate resemblance — investigate with additional checks.'}
                      {level === 'Low' && '✅ Low resemblance — unlikely to be direct brand impersonation.'}
                    </>
                  )}
                </Typography>
                {numericScore >= 0.65 && (
                  <Typography variant="caption" sx={{ display: 'block', mt: 0.75, opacity: 0.78 }}>
                    Final verdict checks domain-brand alignment before treating high similarity as legitimate.
                  </Typography>
                )}
              </Box>
            </Box>
            {/* Breakdown */}
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
              Similarity Breakdown
            </Typography>
            <Grid container spacing={2}>
              {breakdownKeys.map((k)=> (
                <Grid item xs={12} sm={6} md={3} key={k}>
                  <Paper
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      /* transparent so it visually matches the parent card */
                      bgcolor: 'transparent',
                      textAlign: 'center'
                    }}
                     elevation={0}
                     component={motion.div}
                     initial={{ opacity: 0, y: 10 }}
                     animate={{ opacity: 1, y: 0 }}
                     transition={{ delay: 0.2 }}
                   >
                     <Typography variant="body2" sx={{ textTransform: 'capitalize', fontWeight: 700 }}>
                       {k}
                     </Typography>
                     <Typography variant="h6" sx={{ mt: 0.5 }}>
                       {((details[k] ?? 0)*100).toFixed(1)}%
                     </Typography>
                     <LinearProgress
                       variant="determinate"
                       value={(details[k] ?? 0)*100}
                       sx={{
                         height: 8,
                         borderRadius: 6,
                         mt:1,
                         background: 'rgba(255,255,255,0.04)',
                         '& .MuiLinearProgress-bar': { background: '#1976d2' }
                       }}
                     />
                   </Paper>
                 </Grid>
               ))}
             </Grid>

             {ocr && (
               <Box sx={{ mt: 1.5 }}>
                 <Typography variant="caption" sx={{ opacity: 0.78 }}>
                   OCR status: {ocr.ocr_available ? 'available' : 'not available'} | ref text: {ocr.ref_text_len ?? 0} chars | submitted text: {ocr.target_text_len ?? 0} chars
                 </Typography>
               </Box>
             )}

             {Array.isArray(assessment?.reasons) && assessment.reasons.length > 0 && (
               <Box sx={{ mt: 1.5 }}>
                 <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>Why this result?</Typography>
                 <Typography variant="body2" sx={{ opacity: 0.85, whiteSpace: 'pre-line' }}>
                   {assessment.reasons.slice(0, 3).map((r) => `- ${r}`).join('\n')}
                 </Typography>
               </Box>
             )}

             {Array.isArray(assessment?.recommendations) && assessment.recommendations.length > 0 && (
               <Box sx={{ mt: 1.5 }}>
                 <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>Recommended actions</Typography>
                 <Typography variant="body2" sx={{ opacity: 0.85, whiteSpace: 'pre-line' }}>
                   {assessment.recommendations.slice(0, 3).map((r) => `- ${r}`).join('\n')}
                 </Typography>
               </Box>
             )}

             {/* Screenshots */}
             <Typography variant="subtitle2" sx={{ mt: 3, mb: 1, fontWeight: 600 }}>
               Screenshots Comparison
             </Typography>
             <Stack direction="row" spacing={3} sx={{ mt: 1, flexWrap: 'wrap' }}>
               {refSrc && (
                 <motion.div whileHover={{ scale: 1.03 }}>
                   <Box sx={{ textAlign: 'center' }}>
                     <img
                       src={refSrc}
                       alt="ref"
                       onClick={() => openImage(refSrc, 'Reference')}

                  style={{ width: 220, height: 140, objectFit: 'cover', borderRadius: 12, boxShadow: 'none', cursor: 'pointer' }}
                     />
                     <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.78 }}>
                       Reference Brand
                     </Typography>
                   </Box>
                 </motion.div>
               )}
               {userSrc && (
                 <motion.div whileHover={{ scale: 1.03 }}>
                   <Box sx={{ textAlign: 'center' }}>
                     <img
                       src={userSrc}
                       alt="user"
                       onClick={() => openImage(userSrc, 'User Screenshot')}
                       style={{ width: 220, height: 140, objectFit: 'cover', borderRadius: 12, boxShadow: 'none', cursor: 'pointer' }}
                     />
                     <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.78 }}>
                       Submitted Page
                     </Typography>
                   </Box>
                 </motion.div>
               )}
             </Stack>
          </Box>
        )}

        {!simLoading && score === null && !simErrorMessage && (
          <Typography variant="body2" sx={{ opacity: 0.8 }}>
            No similarity analysis available. Click Analyze to run checks.
          </Typography>
        )}
      </Box>

      {/* Lightbox */}
      <Dialog open={openImg} onClose={closeImage} maxWidth="lg" fullWidth>
        <DialogContent
          sx={{
            position: 'relative',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            p: 2,
            backdropFilter: 'blur(8px)',
            background: 'rgba(0,0,0,0.85)'
          }}
        >
          <IconButton onClick={closeImage} sx={{ position: 'absolute', right: 8, top: 8, color: '#fff' }}>
            <CloseIcon />
          </IconButton>
          {imgSrc && (
            <motion.img
              src={imgSrc}
              alt={imgCaption}
              style={{ maxWidth: '100%', maxHeight: '80vh', borderRadius: 10, boxShadow: '0 20px 60px rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Similarity Explain Modal */}
      <SimilarityExplainModal open={explainOpen} onClose={() => setExplainOpen(false)} />
    </Paper>
  )
}