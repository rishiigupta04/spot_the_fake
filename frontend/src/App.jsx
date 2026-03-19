import React, { useState, Suspense, useEffect } from 'react'
import {
  Container,
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  CircularProgress,
  CssBaseline,
} from '@mui/material'
import axios from 'axios'
import { motion } from 'framer-motion'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Features from './components/Features'
import HowItWorks from './components/HowItWorks'
import PhishingAnalysis from './components/Dashboard/PhishingAnalysis'
import SimilarityAnalysis from './components/Dashboard/SimilarityAnalysis'
import HistoryWatchlistPanel from './components/Dashboard/HistoryWatchlistPanel'
import { buildApiUrl, postSimilarityUpload } from './config/api'

// Lazy-load FinalVerdict to optimize initial load
const FinalVerdict = React.lazy(() => import('./components/Dashboard/FinalVerdict'))

// Animation variants
const fadeInUp = {
  hidden: { opacity: 0, y: 40 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.15, duration: 0.6, ease: 'easeOut' },
  }),
}

const getApiErrorMessage = (err) => {
  const payload = err?.response?.data
  if (payload?.error?.message) return payload.error.message
  if (typeof payload?.error === 'string') return payload.error
  if (typeof payload?.message === 'string') return payload.message
  if (typeof payload === 'string') return payload
  return err?.message || 'Request failed'
}

const HISTORY_KEY = 'stf_scan_history_v1'
const WATCHLIST_KEY = 'stf_watchlist_v1'

const parseStoredJson = (key, fallbackValue) => {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallbackValue
  } catch (_) {
    return fallbackValue
  }
}

export default function App() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [simResult, setSimResult] = useState(null)
  const [simLoading, setSimLoading] = useState(false)
  const [simError, setSimError] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [history, setHistory] = useState(() => parseStoredJson(HISTORY_KEY, []))
  const [watchlist, setWatchlist] = useState(() => parseStoredJson(WATCHLIST_KEY, []))
  const showPhishingCard = loading || !!result || !!error
  const showSimilarityCard = simLoading || !!simResult || !!simError

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history))
  }, [history])

  useEffect(() => {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist))
  }, [watchlist])

  const appendHistoryEntry = ({ inputUrl, phishingResult, phishingError, similarityResult, similarityError }) => {
    const similarityPayload = similarityResult?.result ?? similarityResult
    const phishingPayload = phishingResult?.result ?? phishingResult
    const score = similarityPayload?.score

    const entry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      url: inputUrl,
      verdict: phishingPayload?.final_verdict || (phishingError ? 'error' : null),
      urgency: phishingPayload?.urgency?.level || null,
      llmRisk: phishingPayload?.llm_risk_level || null,
      brand: similarityPayload?.brand || phishingPayload?.watch_profile?.brand_hint || null,
      similarityScore: typeof score === 'number' ? score : null,
      phishingError: phishingError || null,
      similarityError: similarityError || null,
    }

    setHistory((prev) => [entry, ...prev].slice(0, 250))
  }

  const handleSubmit = async (e) => {
    e && e.preventDefault()
    const trimmedUrl = (url || '').trim()

    if (!trimmedUrl) {
      setError('Please enter a URL to analyze.')
      return
    }

    setLoading(true)
    setSimLoading(true)
    setError(null)
    setSimError(null)
    setResult(null)
    setSimResult(null)
    let predictResultData = null
    let predictResultError = null
    let similarityResultData = null
    let similarityResultError = null
    let settledCalls = 0

    const finalizeHistory = () => {
      settledCalls += 1
      if (settledCalls < 2) return
      appendHistoryEntry({
        inputUrl: trimmedUrl,
        phishingResult: predictResultData,
        phishingError: predictResultError,
        similarityResult: similarityResultData,
        similarityError: similarityResultError,
      })
    }

    axios
      .post(buildApiUrl('/predict'), { url: trimmedUrl })
      .then((resp) => {
        const r = resp.data?.result ?? resp.data
        predictResultData = r
        setResult(r)
      })
      .catch((err) => {
        predictResultError = getApiErrorMessage(err)
        setError(predictResultError)
      })
      .finally(() => {
        setLoading(false)
        finalizeHistory()
      })

    axios
      .post(buildApiUrl('/similarity'), { url: trimmedUrl })
      .then((sresp) => {
        const s = sresp.data?.result ?? sresp.data
        similarityResultData = s
        setSimResult(s)
      })
      .catch((errSim) => {
        similarityResultError = getApiErrorMessage(errSim)
        setSimError(similarityResultError)
      })
      .finally(() => {
        setSimLoading(false)
        finalizeHistory()
      })
  }

  const handleUploadSubmit = async (e) => {
    e && e.preventDefault()

    if (!uploadFile) {
      setSimError('Please choose an image file first.')
      return
    }

    setLoading(false)
    setError(null)
    setResult(null)
    setSimLoading(true)
    setSimError(null)
    setSimResult(null)

    try {
      const uploadResp = await postSimilarityUpload(axios, uploadFile)
      const s = uploadResp.data?.result ?? uploadResp.data
      setSimResult(s)
      appendHistoryEntry({
        inputUrl: `file://${uploadFile.name}`,
        phishingResult: null,
        phishingError: null,
        similarityResult: s,
        similarityError: null,
      })
    } catch (errUpload) {
      const uploadErr = getApiErrorMessage(errUpload)
      setSimError(uploadErr)
      appendHistoryEntry({
        inputUrl: `file://${uploadFile.name}`,
        phishingResult: null,
        phishingError: null,
        similarityResult: null,
        similarityError: uploadErr,
      })
    } finally {
      setSimLoading(false)
    }
  }

  return (
    <>
      <CssBaseline />
      <Navbar />

      {/* Hero with fade-in */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={fadeInUp}
      >
        <Hero
          onCta={() =>
            document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })
          }
        />
      </motion.div>

      <Container maxWidth="lg" sx={{ mt: 6 }}>
        {/* Features with scroll animation */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={fadeInUp}
        >
          <Features />
        </motion.div>

        {/* How It Works Section */}
        <motion.div
          id="how-it-works"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={fadeInUp}
          sx={{ mt: 6 }}
        >
          <HowItWorks />
        </motion.div>

        {/* Demo Section */}
         <Box id="demo" sx={{ mt: 6, borderRadius: 3 }}>
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
            variants={fadeInUp}
          >
           <Paper
             sx={{
               p: 4,
             background: '#0f1724',
               color: (theme) => theme.palette.text.primary,
             }}
             elevation={3}
           >
             <Typography variant="h6" gutterBottom>
               Live Demo — Analyze a Website
             </Typography>

             {/* Input Form */}
             <Box
               component="form"
               onSubmit={handleSubmit}
               sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 2 }}
             >
               <TextField
                 fullWidth
                 label="Enter URL or text"
                 value={url}
                 onChange={(e) => setUrl(e.target.value)}
                 sx={{
                   background: (theme) =>
                     theme.palette.mode === 'dark'
                       ? 'rgba(255,255,255,0.03)'
                       : '#fff',
                   input: { color: 'inherit' },
                 }}
               />
               <Button variant="contained" type="submit" disabled={loading || simLoading}>
                 Analyze
               </Button>
             </Box>

             <Box
               component="form"
               onSubmit={handleUploadSubmit}
               sx={{ display: 'flex', gap: 2, alignItems: 'center', mt: 2, flexWrap: 'wrap' }}
             >
               <Button variant="outlined" component="label" disabled={loading || simLoading}>
                 {uploadFile ? `Selected: ${uploadFile.name}` : 'Choose Screenshot'}
                 <input
                   type="file"
                   accept="image/*"
                   hidden
                   onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                 />
               </Button>
               <Button variant="contained" type="submit" disabled={loading || simLoading || !uploadFile}>
                 Analyze Uploaded Image
               </Button>
             </Box>

             {/* Results & Feedback */}
             <Box sx={{ mt: 3 }}>
               {/* Loading states */}
               {(loading || simLoading) && (
                 <motion.div
                   initial={{ opacity: 0 }}
                   animate={{ opacity: 1 }}
                   transition={{ duration: 0.4 }}
                 >
                   <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                     <CircularProgress size={20} />
                     <Typography>
                       {loading ? 'Analyzing...' : 'Checking similarity...'}
                     </Typography>
                   </Box>
                 </motion.div>
               )}

               {/* Results Section */}
               {(result || simResult || loading || simLoading || error || simError) && (
                 <motion.div
                   initial="hidden"
                   animate="visible"
                   variants={fadeInUp}
                 >
                    <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {showPhishingCard && (
                        <Paper
                          sx={{
                            p: 2,
                            background: (theme) => theme.palette.background.paper,
                            color: (theme) => theme.palette.text.primary,
                          }}
                          elevation={1}
                        >
                          <Typography variant="subtitle1" gutterBottom>
                            Phishing Detection
                          </Typography>
                          {loading && !result && <Typography variant="body2">Analyzing phishing signals...</Typography>}
                          {!loading && error && <Typography color="error">Error: {error}</Typography>}
                          {result && <PhishingAnalysis result={result} />}
                        </Paper>
                      )}

                      {showSimilarityCard && (
                        <Paper
                          sx={{
                            p: 2,
                            background: (theme) => theme.palette.background.paper,
                            color: (theme) => theme.palette.text.primary,
                          }}
                          elevation={1}
                        >
                          <Typography variant="subtitle1" gutterBottom>
                            Website Similarity
                          </Typography>
                          <SimilarityAnalysis
                            simResult={simResult}
                            simLoading={simLoading}
                            simError={simError}
                          />
                        </Paper>
                      )}

                      {result && (
                        <Paper
                          sx={{
                            p: 2,
                            background: (theme) => theme.palette.background.paper,
                            color: (theme) => theme.palette.text.primary,
                          }}
                          elevation={1}
                        >
                          <Typography variant="subtitle1" gutterBottom>
                            Final Combined Analysis
                          </Typography>
                          {simLoading && !simResult && !simError && (
                            <Typography variant="body2" sx={{ mb: 1, opacity: 0.8 }}>
                              Awaiting similarity analysis... final verdict will auto-update when ready.
                            </Typography>
                          )}
                          <Suspense
                            fallback={
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  p: 2,
                                }}
                              >
                                <CircularProgress size={24} />
                              </Box>
                            }
                          >
                            <FinalVerdict
                              result={result}
                              similarityResult={simResult}
                            />
                          </Suspense>
                        </Paper>
                      )}
                    </Box>
                  </motion.div>
               )}

               <HistoryWatchlistPanel
                 history={history}
                 setHistory={setHistory}
                 watchlist={watchlist}
                 setWatchlist={setWatchlist}
               />
             </Box>
           </Paper>
          </motion.div>
         </Box>
      </Container>
    </>
  )
}