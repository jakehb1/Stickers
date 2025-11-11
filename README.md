# Sticker Shop Platform

This repository contains a FastAPI backend, a Telegram WebApp mini app and a lightweight admin dashboard for selling digital sticker packs with Stripe payments.

## Features

- **FastAPI backend** with SQLite (configurable) storage for stickers and purchases.
- **Admin authentication** via bearer token with hashed password stored in environment variables.
- **Sticker management** endpoints for creating, updating, deleting and toggling sticker visibility.
- **Stripe checkout integration** including webhook handler to mark purchases as fulfilled.
- **TON blockchain payments** with on-chain invoice tracking backed by configurable wallet and confirmation thresholds.
- **Telegram mini app** frontend (`apps/mini-app`) that lists stickers and launches the Stripe checkout session.
- **Admin dashboard** frontend (`apps/admin-dashboard`) to login, upload, edit, activate/deactivate, and delete stickers through the browser.

## Getting started

### 1. Configure environment

Copy the example environment file and update the values:

```bash
cp backend/.env.example backend/.env
```

Set the following values:

- `SECRET_KEY`: random string for JWT signing.
- `ADMIN_PASSWORD_HASH`: bcrypt hash of the admin password. Generate using Python:
  ```python
  from passlib.context import CryptContext
  print(CryptContext(schemes=["bcrypt"]).hash("your-password"))
  ```
- `STRIPE_SECRET_KEY`: Stripe secret key (`sk_live_...` or `sk_test_...`).
- `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL`: URLs to send customers after checkout.
- `STRIPE_WEBHOOK_SECRET`: Secret from your Stripe webhook endpoint (for `checkout.session.completed`).
- `TON_PAYMENT_WALLET`: Wallet address that will receive TON payments.
- `TON_API_BASE_URL`: Base URL for the TON blockchain API (defaults to `https://tonapi.io/v2`).
- `TON_API_KEY`: Optional API key for authenticated TON API access.
- `TON_INVOICE_TTL_SECONDS`: How long invoices remain payable before expiring (default 900 seconds).
- `TON_MIN_CONFIRMATIONS`: Minimum number of confirmations required before treating a TON transaction as settled.

### 2. Install backend dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the backend

```bash
uvicorn app.main:app --reload
```

The backend serves static files from `backend/static` at `http://localhost:8000/static`.

### 4. Serve the frontends

The frontends are static and can be hosted by any static server. During development you can use `python -m http.server`:

```bash
# Mini app
cd apps/mini-app
python -m http.server 5173
# Admin dashboard
cd ../admin-dashboard
python -m http.server 4173
```

Configure the global `API_BASE_URL` in each HTML file (or inject it at runtime) so the frontends can reach your backend (defaults to `http://localhost:8000`).

### 5. Telegram configuration

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and enable WebApp support.
2. Host the mini app frontend and configure the WebApp URL in BotFather to point to the hosted `index.html`.
3. In your backend, expose an endpoint for Stripe webhooks and configure the webhook URL inside the Stripe dashboard.

### Stripe webhook testing

To test webhooks locally, use the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/payments/webhook
```

### TON invoice flow

1. Set `currency` to `ton` and store the sticker price as **nanotons** (1 TON = 1_000_000_000 nanotons) when creating or editing stickers in the admin dashboard.
2. When a buyer chooses the TON option, the mini app should call `POST /payments/ton/invoice` with the `sticker_id` and Telegram user ID to obtain the payable address, amount, and unique comment memo.
3. Display the returned wallet address, amount, and comment to the buyer. They must include the provided comment in the transfer so the backend can match the payment.
4. After the buyer broadcasts the transaction, submit the transaction hash to `POST /payments/ton/confirm`. The backend will query the configured TON API, verify the destination address, comment, amount, and confirmation count, then mark the purchase as fulfilled.
5. Poll `GET /payments/ton/invoice/{invoice_id}` if you need to reflect invoice status changes in the UI (pending, confirmed, expired).

### Admin dashboard usage

1. Navigate to the hosted admin dashboard.
2. Login using the password that matches `ADMIN_PASSWORD_HASH`.
3. Upload new stickers using the form. Uploaded images are stored under `backend/static/stickers` and automatically linked in the mini app.
4. Click **Edit** next to a sticker to load its data into the form, update any fields (and optionally upload a replacement image), then submit to save.
5. Use **Activate/Deactivate** to control visibility in the mini app or **Delete** to remove a sticker entirely.

## Container deployment

The repository includes Docker images and a `docker-compose.yml` file so you can run the entire stack on any host that supports Docker.

1. Create and populate `backend/.env` using the values described above.
2. Build and start the containers:

   ```bash
   docker compose up -d --build
   ```

   The backend is available at `http://localhost:8000` and the frontends at `http://localhost:8080`. The Telegram mini app is served from the root path, while the admin dashboard is exposed at `/admin/`.

3. Tail the logs to verify startup and Stripe webhook handling:

   ```bash
   docker compose logs -f backend
   ```

4. When you are ready to stop the stack run `docker compose down`. Add the `--volumes` flag if you want to remove the SQLite database and uploaded sticker images that are stored in the named volumes.

### Customising frontend URLs

The frontend container rewrites a small `config.js` file at boot to point to the backend API. By default both mini app and admin dashboard talk to the internal `http://backend:8000` service defined in the compose file.

- Set `API_BASE_URL` to update both experiences at once.
- Or set `MINI_APP_API_BASE_URL` / `ADMIN_API_BASE_URL` separately if they should call different backends.

For production deployments place the containers behind a TLS-terminating proxy (for example, Nginx, Caddy, or a cloud load balancer). Point Telegram’s WebApp configuration to `https://your-domain/` (mini app) and access the admin dashboard at `https://your-domain/admin/`.

### Stripe webhooks in production

Expose `https://your-domain/payments/webhook` to Stripe so completed checkout sessions mark purchases as fulfilled. When running behind a reverse proxy be sure to forward the raw request body and `Stripe-Signature` header to the backend container.

## Deploying the static frontends to Vercel

Each frontend lives under the `apps/` directory and ships with its own `vercel.json` so you can deploy the mini app and admin dashboard as independent projects or branch previews.

### Mini app deployment

1. Create or switch to a branch dedicated to the Telegram experience (for example `mini-app`).
2. In Vercel, import the repository and set the **Root Directory** to `apps/mini-app`.
3. Choose the **Other** framework preset so no build command is executed.
4. Update `apps/mini-app/config.js` on that branch so `window.API_BASE_URL` targets your production backend (or inject the value at runtime by serving a custom `config.js`).
5. Deploy the branch. Vercel will use `apps/mini-app/vercel.json` to publish the static assets and configure a catch-all route so reloads stay on the landing page.

### Admin dashboard deployment

Repeat the steps above on a separate branch (for example `admin-dashboard`) and set the **Root Directory** to `apps/admin-dashboard`. Adjust its `config.js` if the admin tools should target a different backend environment. The included `vercel.json` again serves the dashboard as a static site with a single-page-app style catch-all route.

Ensure CORS is configured on the API if it lives on a different domain so both Vercel deployments can communicate successfully.

## Project structure

```
backend/
  app/
    main.py
    config.py
    database.py
    models.py
    schemas.py
    auth.py
    routes/
      admin.py
      stickers.py
      payments.py
  requirements.txt
  static/
    stickers/
apps/
  mini-app/
    index.html
    main.js
    styles.css
    vercel.json
  admin-dashboard/
    index.html
    main.js
    styles.css
    vercel.json
frontend/
  Dockerfile
  entrypoint.sh
  nginx.conf
README.md
```
