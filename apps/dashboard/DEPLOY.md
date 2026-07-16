# Deploying StratAgent as a public service

Cloning the repo gives someone their **own private instance**: their engagements,
their lessons, their database. Nothing reaches you. That is the right default for
privacy — and it means the operator console, the feedback channel and the
learning loop have nothing to show, because there is no shared instance to
observe.

Deploy **one** instance and hand out a **URL** (not a repo) when you want:

* usage you can actually see (`/admin`),
* feedback that reaches you,
* a learning loop that compounds across everyone's cases rather than restarting
  from zero on every laptop.

The trade is real: **you** pay for the free tier, and users trust you with their
business problems. BYOK and the quotas below are what keep that sane.

---

## 1. Before you deploy — the settings that matter

| Variable | Public value | Why |
|---|---|---|
| `STRATAGENT_TRUST_PROXY` | **`1`** | Every PaaS puts a proxy in front. Without this, all visitors look like one IP and the first 15 runs lock out the world. **Never set it to 1 when directly exposed** — X-Forwarded-For is caller-supplied. |
| `STRATAGENT_IP_SALT` | a long random string | Pins the IP-quota hash across restarts. Unset ⇒ a fresh salt each boot ⇒ quotas reset on every deploy. |
| `STRATAGENT_ADMIN_TOKEN` | a long random string | Without it `/admin` 404s and you are blind. |
| `STRATAGENT_DAILY_QUOTA` | `3`–`5` | Per browser. Courtesy limit. |
| `STRATAGENT_DAILY_IP_QUOTA` | `10`–`15` | Per source. **This is the real abuse control.** |
| `STRATAGENT_MAX_CONCURRENT` | `4`–`8` | Bounds load on one SQLite writer + the shared provider quota. |
| `STRATAGENT_CORS_ORIGINS` | your frontend URL | Defaults to localhost; the browser blocks the API otherwise. |
| `NEXT_PUBLIC_API_URL` | your backend URL | **Baked in at build time**, not runtime — set it before building the frontend. |
| `STRATAGENT_DB` | a path on a **persistent volume** | Otherwise every deploy silently destroys all history. |

Generate the secrets:

```bash
python3 -c "import secrets; print('STRATAGENT_ADMIN_TOKEN=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('STRATAGENT_IP_SALT=' + secrets.token_urlsafe(32))"
```

## 2. What the free tier costs you

A run is ~13–16 provider calls. On the pooled free chain that is **€0** — you are
spending *quota*, not money. The ceiling is therefore requests/day, not budget:

```
5 Gemini projects  ≈ 5 × 1,500 req/day  ÷ ~15 calls  ≈ 500 engagements/day
```

`DAILY_IP_QUOTA=15` means one network can take ~15 of those. If you outgrow it,
add Gemini projects (free, linear) before you add billing.

## 2.5 Live instance

The operator's own deployment (Railway project `nurturing-cooperation`,
workspace `darpan00720's Projects`):

| Service | Railway service name | URL |
|---|---|---|
| Backend  | `Consulting-Agent`    | https://consulting-agent-production-7eb7.up.railway.app |
| Frontend | `adorable-stillness`  | https://stratagent.up.railway.app |

Both auto-deploy from `main` on push. Check status without the web UI:

```bash
railway link -p nurturing-cooperation -s Consulting-Agent   # or adorable-stillness
railway status           # deploy ID, online/offline, volume usage
railway logs             # tail the running container
railway deployment list  # build history (SUCCESS/FAILED/REMOVED)
```

`railway login` opens a one-time device-pairing URL if the CLI isn't
authenticated yet.

## 3. Two services, one repo

`docker-compose.yml` builds both; most PaaS deploy them as separate services.

**Backend** — build context is the **repo root** (it needs `plugins/` and
`knowledge-vault/`), dockerfile `apps/dashboard/backend/Dockerfile`, port 8000.
Mount a volume and point `STRATAGENT_DB` inside it.

**Frontend** — build context `apps/dashboard/frontend`, port 3000, build arg
`NEXT_PUBLIC_API_URL=<your backend URL>`.

Deploy the backend first (you need its URL), then the frontend, then set
`STRATAGENT_CORS_ORIGINS` to the frontend URL and redeploy the backend.

## 4. Verify before announcing it

```bash
curl -s https://<backend>/api/health          # {"ok":true,"free_tier":true,"mock":false}
curl -s https://<backend>/api/admin/overview  # 404 (no token) — correct
curl -s -H "X-Admin-Token: <token>" https://<backend>/api/admin/overview   # 200
```

Then, from a browser, run one real engagement end to end and confirm it appears
in `/admin`. **Check `mock` is `false`** — a mock deployment serves canned text
to everyone (the banner says so, but check anyway).

## 5. Operating it

* **Watch `/admin`.** Failed runs show the exact phase that broke.
* **Rate limits are not incidents.** Engagements pause and auto-resume; alert on
  pause *rate*, not pauses.
* **Back up the volume.** It is the only copy of every engagement, every comment,
  and every lesson the platform has learned.
* Telemetry: `docker exec <backend> /app/.venv/bin/python -m app.ops`

## 6. What you are taking on

Say it plainly, because users can't see it:

* Pasted case prompts land in **your** database. People paste confidential
  briefs. Back it up, and consider a retention policy.
* Pasted images are never persisted; BYOK keys are never stored. Those
  guarantees hold on a public deployment and are pinned by tests.
* There is no signup, so there is no way to notify a user later, and no way for
  them to delete their data. If either matters, that is a product decision to
  make *before* you have users — not after.
