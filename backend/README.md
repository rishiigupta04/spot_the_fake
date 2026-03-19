Backend (Flask) for Spot-the-Fake

Files added/modified:
- app.py - Flask routes: /health, /model-info, /predict, /similarity, /similarity-upload
- models/loader.py - helper to load the existing pickled model (phishing_lgbm.pkl)
- requirements.txt - backend-specific pip dependencies

Quick start (Windows / macOS / Linux):
1. Create and activate a virtualenv (recommended):
   python -m venv .venv
   .\.venv\Scripts\activate    # Windows
   source .venv/bin/activate     # macOS / Linux

2. Install dependencies:
   pip install -r backend/requirements.txt

3. Run the Flask app:
   python backend/app.py

Endpoints:
- GET /health -> basic status and import diagnostics
- GET /model-info -> returns info about the pickled ML package (if available)
- POST /predict -> JSON {"url": "https://..."} returns ML+LLM prediction
- POST /predict-lite -> JSON {"url": "https://..."} returns fast ML-only URL risk (for real-time badge)
- POST /similarity -> JSON {"url": "https://..."} returns similarity result
- POST /similarity-upload -> multipart/form-data file upload (field name 'file') to run image similarity

Request/response notes:
- URL endpoints accept bare domains like `example.com`; backend normalizes to `https://example.com`.
- Success shape remains: `{"success": true, "result": ...}`.
- Error shape is standardized: `{"success": false, "error": {"code": "...", "message": "..."}}`.
- `/health` also reports `cloudinary.configured` and per-key presence flags.
- `/predict` now includes additive fields for richer scoring:
  - `result.risk_signals.domain` (WHOIS/RDAP age + registrar reputation)
  - `result.risk_signals.ssl` (certificate validity/expiry)
  - `result.risk_signals.redirect.depth`
  - `result.risk_signals.network` (IP/ASN reputation hints)
  - `result.risk_signals.sensitive_fields` (password/payment field detection)
  - `result.urgency` (low/medium/high/critical + reasons)

Notes / gotchas:
- The backend imports your existing app1.py and app2.py to reuse logic. If those files depend on packages not installed (selenium, groq, tesseract), /health will show import errors.
- Selenium requires Chrome and a compatible chromedriver or Selenium Manager.
- Set `GROQ_API_KEY` in your environment if you want LLM analysis.
- You can also create a project-root `.env` file (see `.env.example`) and the backend will load it automatically.
- Optional: set `GROQ_MODEL` to override the default model.
- Tesseract OCR must be installed on the system for OCR functionality.

Vercel notes:
- This backend is wired for Vercel via root `vercel.json`.
- In serverless mode, user screenshots are stored in writable temp storage (`/tmp/spot-the-fake-user`) and are not persistent across cold starts.
- If you need durable user image history, use object storage (S3/R2/etc.) and store returned URLs.

Cloudinary optional integration:
- Set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
- `/similarity` and `/similarity-upload` responses will include:
  - `result.reference_image_url`
  - `result.user_screenshot_url`
- Frontend prefers these hosted URLs and falls back to `/static/*` when absent.

If you see import errors when hitting /health, install missing dependencies shown in the import_error string.