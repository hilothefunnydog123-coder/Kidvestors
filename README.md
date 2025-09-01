# Kidvestor (Free • 15s updates)

This is a ready-to-deploy **Vite + React** app that shows:
- Top 15 **Stocks** (Finnhub free API)
- Top 15 **Crypto** (CoinGecko free)
- Top 15 **Forex** (exchangerate.host free)
- Top 15 **Futures** (Binance Futures public)

It refreshes every **15 seconds** and includes a **lessons & unlocks** pane (saved in localStorage).

## Deploy on Netlify (no coding)
1. Create a new **GitHub** repo named `kidvestor` (public).
2. Upload all files from this folder into the repo (ensure `package.json` is at the repo ROOT).
3. Go to **Netlify → New site from Git → GitHub → select your repo**.
4. Set **Build command**: `npm run build`
5. Set **Publish directory**: `dist`
6. Set an **Environment variable**:
   - Key: `VITE_FINNHUB_KEY`
   - Value: **your Finnhub API key** (keep it secret)
7. Deploy. Done.

## Local run (optional)
```bash
npm install
npm run dev
```

## Notes
- Do **not** put your API key in the code. Use environment variables (Netlify → Site settings → Environment).
- This is for **education** only. No real money. COPPA-friendly idea: keep personal data off the platform.
- If CoinGecko rate-limits, wait a minute and refresh.
- You can change the Top 15 lists in `src/App.jsx`.
