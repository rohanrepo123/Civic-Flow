# Member 3 Browser Agent integration

The `browser_agent/` package is sourced from `rohi5431/civicflow-browser` and
is exposed through the existing CivicFlow session API in `app/main.py`.

The local startup script uses live Chromium by default. Install its browser once
after installing Python dependencies:

```powershell
python -m playwright install chromium
scripts/run-local.cmd
```

Each CivicFlow browser session starts an isolated visible Chromium window on
the local desktop. The stream in the app shows its live page; use **Take manual
control** to interact with the Chromium window directly, then return control to
CivicFlow for inspection and safe field preparation. If Chromium cannot start,
session creation fails with an actionable error; it does not fabricate a live
session.

For UI-only development, mock behavior must be requested explicitly with
`scripts/run-local.cmd -MockBrowser`. It is labeled as simulated and does not
open or interact with a government portal. Sensitive authentication, OTP,
CAPTCHA, payment, consent, legal declarations, and final submission remain
under citizen control.
