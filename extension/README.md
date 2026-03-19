# Spot the Fake Browser Extension (Live Badge)

This extension adds a lightweight phishing risk badge on every page using the backend endpoint:
- `POST /predict-lite`

## Load in Chrome/Edge

1. Open extensions page (`chrome://extensions` or `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `extension/` folder.

## Configure

1. Open extension details.
2. Open **Extension options**.
3. Set backend URL (default: `http://localhost:5000`).
4. Set cache TTL (default: `300000` ms = 5 minutes).

## How it works

- Background worker listens to tab updates.
- Calls `POST /predict-lite` for current URL.
- Caches risk by hostname for TTL.
- Content script shows a fixed badge with:
  - risk level (`low`, `medium`, `high`, `unknown`)
  - phishing probability