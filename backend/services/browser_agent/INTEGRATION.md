# Member 3 Browser Agent integration

The `browser_agent/` package is sourced from `rohi5431/civicflow-browser` and
is exposed through the existing CivicFlow session API in `app/main.py`.

The default remains `CIVICFLOW_BROWSER_RUNTIME=mock`, so the frontend and Core
API work without a local Chromium installation. To enable the real runtime:

```powershell
$env:CIVICFLOW_BROWSER_RUNTIME = "playwright"
python -m playwright install chromium
uvicorn app.main:app --port 8002
```

When enabled, session creation starts an isolated Chromium context, navigation
commands use Playwright, and `inspect` commands return a value-safe DOM snapshot
from Member 3's observer. Sensitive actions and final submission remain under
the existing human-control safety boundary.
