import React from 'react';
import { Dialog, DialogTitle, DialogContent, IconButton, Typography, Divider, Box } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

export default function SimilarityExplainModal({ open, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
        Similarity Analysis Explained
        <IconButton onClick={onClose} size="small" sx={{ ml: 2 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          How is Similarity Calculated?
        </Typography>
        <Typography variant="body2" paragraph>
          The similarity score compares the submitted website screenshot against known brand reference images using multiple features:
        </Typography>
        <ul style={{ marginTop: 0 }}>
          <li>
            <b>Image Similarity:</b> Measures how visually similar the screenshots are using advanced image comparison algorithms.
          </li>
          <li>
            <b>Color Similarity:</b> Compares the dominant color schemes and palettes between the two images.
          </li>
          <li>
            <b>Text Similarity:</b> Analyzes the extracted text content and its similarity to the brand reference.
          </li>
          <li>
            <b>Structure Similarity:</b> Compares layout/edge structure to catch close visual clones.
          </li>
        </ul>
        <Typography variant="body2" paragraph>
          The engine dynamically rebalances weights when OCR text quality is weak, and adds a confidence indicator.
        </Typography>
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
          How Are Results Interpreted?
        </Typography>
        <Box sx={{ mb: 1 }}>
          <Typography variant="body2"><b>High similarity + domain mismatch</b>: strong impersonation signal (high risk).</Typography>
          <Typography variant="body2"><b>High similarity + aligned domain</b>: likely legitimate brand presence (still verify host exactly).</Typography>
          <Typography variant="body2"><b>Moderate similarity</b>: caution signal, combine with phishing and domain checks.</Typography>
          <Typography variant="body2"><b>Low similarity</b>: unlikely to be direct brand impersonation.</Typography>
        </Box>
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
          How Should I Interpret the Results?
        </Typography>
        <Typography variant="body2" paragraph>
          - Similarity alone is not a final verdict: domain-brand alignment is critical.<br />
          - Treat high similarity on unexpected domains as likely phishing impersonation.<br />
          - Use this with phishing model outputs and urgency indicators for best decisions.
        </Typography>
        <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
          FAQ & Tips
        </Typography>
        <Typography variant="body2">
          • If you are unsure, always verify the website URL and look for other signs of phishing.<br />
          • No automated system is perfect—use this tool as one part of your decision process.
        </Typography>
      </DialogContent>
    </Dialog>
  );
}