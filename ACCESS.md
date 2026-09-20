# Opening the app

The Python backend serves the built React UI **and** `/api/v1` on one origin:
**http://127.0.0.1:8000**. Port 5173 is only needed when developing the frontend.

`start-local.cmd` starts a hidden supervisor and opens the browser. It does not rebuild
the frontend. After code changes run `npm.cmd run build` inside `frontend`.
First-time installation uses `setup-local.cmd` (Python, Node and internet required).

Automatic startup is per Windows user, at **logon**, not before login:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-autostart.ps1
```

The app continues while that user stays logged in, including when the screen is locked.
The supervisor restarts the server if it exits. Logs: `backend/storage/web-server.log`.
Remove future autostart with the same script plus `-Remove`. That does not stop current processes.
This launcher assumes local HTTP on port 8000 (the default). The PC must remain awake.

## Permanent public mobile URL — pending account/domain setup

No public tunnel is installed or published yet. `127.0.0.1` on a phone refers to the
phone itself, not this PC. For a permanent HTTPS hostname using Cloudflare Tunnel:

1. Create a Cloudflare account and add a domain you own with active Cloudflare DNS.
2. Create a named tunnel in Cloudflare Zero Trust; install its Windows connector
   using the account-provided command on this PC. Keep its token private.
3. Route a hostname such as `creator.yourdomain.com` to `http://127.0.0.1:8000`.
4. Before enabling public traffic, use a private strong application login, disable
   open registration (`ALLOW_REGISTRATION=false`), set separate persistent random
   `JWT_SECRET` and `JWT_REFRESH_SECRET`, `COOKIE_SECURE=true`, and add the exact
   `https://creator.yourdomain.com` origin to `ALLOWED_ORIGINS` in `backend/.env`.
   Restart the backend and verify login, refresh and protected downloads over HTTPS.
5. Install the named tunnel as a Windows service for reconnect/startup; verify the
   actual URL on mobile data. No router port forwarding is needed.

The domain/subdomain and account authorization are required to complete this step.
Do not treat a local build or a healthy local server as evidence of public deployment.

If you do not own a domain, an ngrok account can provide an assigned static development
domain. Account authorization/authtoken and the assigned hostname are still needed.
Apply the same authentication, secure-cookie and allowed-origin settings above for that
HTTPS hostname. The free service may display a browser interstitial and has usage limits.
This alternative has not been installed or activated either.

## Current feature boundaries

Task Scheduler supports persisted daily, weekly, monthly and every-N-days generation
in Asia/Kolkata time. It runs while the backend is up, skips missed prior days, and
waits when another video is rendering. Monthly day 29–31 clamps to month end.
Scheduled jobs render straight through to MP4; failures appear on the task/video card.
Pause/delete affects future starts, not an already-running video. Social destination
checkboxes save preferences only; API account connections are still required to publish.
Share opens official platform websites; it does not automatically upload, publish,
or launch a native mobile share sheet. Website login is separate from API authorization.
