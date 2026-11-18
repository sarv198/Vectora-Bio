# Deploying CellScope publicly

Three free services, one per piece:

| Piece | Service | Notes |
| --- | --- | --- |
| Website (Next.js, `frontend/`) | Vercel, Hobby plan | Builds from GitHub on every push. |
| API (FastAPI, `backend/` + `data/processed/`) | Render, free web service, running a Docker image from Docker Hub | The processed data (about 27 MB) is built into the image and never committed to GitHub. Sleeps after 15 minutes without visitors; the first request after that takes about a minute. |
| Database (Postgres) | Neon, free plan | Holds compound and gene metadata plus saved benchmark results (a few MB). Suspends when idle and wakes in under a second. |

Free-tier limits change; check each provider's pricing page before relying on them.

The API is not hosted on Vercel because its scientific Python stack (pandas, SciPy, scikit-learn), its data files and its 10 to 15 second analyses do not fit serverless functions well.

Public-deployment defaults are built into `deploy/api/Dockerfile`:

| Setting | Value | Effect |
| --- | --- | --- |
| `EVALUATION_RUNS_ENABLED` | `false` | Visitors cannot start benchmark runs (about 15 s of CPU each, written to the database). The Evaluation page shows the saved runs and hides the run controls. |
| `PERSIST_ANALYSIS_RUNS` | `false` | Visitors' queries are not logged to the database. |
| `DATA_RAW_DIR` | `/tmp/cellscope-raw` | Cell images are cached here on first view and fetched again after a restart. |

Override any of them under the Render service's **Environment**.

Never commit `.env`, a database URL, or `cellscope.dump`. `.gitignore` already excludes the dump and the staged build folder.

---

## 1. Database: Neon

1. Create an account at neon.tech and a new project (pick a US region). Note the database name it creates.
2. Open **Connect**, switch **Connection pooling off** (the host name then has no `-pooler`), and copy the connection string. It looks like `postgresql://USER:PASSWORD@ep-....neon.tech/DBNAME?sslmode=require`. Keep it private.
3. Start Docker Desktop and the local database, then copy it into Neon. Run from `vectora-bio/` in PowerShell. The dump is written inside the container and copied out, because redirecting binary output with `>` in Windows PowerShell corrupts it.

   ```powershell
   docker compose up -d db
   docker compose exec db pg_dump -U vectora -d vectora -Fc --no-owner --no-acl -f /tmp/cellscope.dump
   docker compose cp db:/tmp/cellscope.dump ./cellscope.dump
   docker run --rm -v "${PWD}:/w" postgres:16-alpine pg_restore --no-owner --no-acl -d "NEON_URL" /w/cellscope.dump
   ```

   Use your own `POSTGRES_USER` / `POSTGRES_DB` if you changed them in `.env`. Replace `NEON_URL` with the string from step 2, keeping the quotes.
4. Check the copy:

   ```powershell
   docker run --rm postgres:16-alpine psql "NEON_URL" -c "select count(*) from compounds"
   ```

   It should report 306 or more rows (one per compound record).
5. Delete `cellscope.dump` when you are done.

## 2. API: Render (via Docker Hub)

Render's free web services build from GitHub, but `data/processed/` is not on GitHub. So the API image is built on your computer, pushed to Docker Hub, and Render runs that image.

Measured at Render's free size (512 MB, 0.1 CPU): startup about 35 s, peak memory about 385 MB, the first run of each analysis 1 to 13 s (repeats are cached).

1. **Docker Hub.** Create a free account at hub.docker.com. Under **Account settings → Personal access tokens**, create a token with **Read & Write** access and keep it open for the next step.
2. **Build and push the image.** Start Docker Desktop, then from `vectora-bio/` in PowerShell (replace `DOCKERHUB_USER` with your Docker Hub username):

   ```powershell
   python scripts/stage_api.py
   docker build --platform linux/amd64 -t DOCKERHUB_USER/cellscope-api:latest deploy/api/build
   docker login -u DOCKERHUB_USER
   docker push DOCKERHUB_USER/cellscope-api:latest
   ```

   `docker login` asks for a password: paste the access token. The staging script copies only the app code, `requirements.txt` and `data/processed/`, and refuses to continue if it finds a `.env` file. The image is about 1.1 GB (about 350 MB compressed), so the first push takes a few minutes.

   The repository is public unless you make it private on hub.docker.com (if your plan allows private repositories). It holds the API code and processed JUMP pilot profiles, no secrets. If you make it private, create a second token with **Read-only** access for Render.
3. **Create the web service.** On render.com, sign up, then **+ New → Web Service → Existing Image**:
   - Image URL: `docker.io/DOCKERHUB_USER/cellscope-api:latest`. For a private repository, open **Credential → Add credential**: Registry Docker Hub, your username, and the read-only token.
   - Name `cellscope-api`, a US region, instance type **Free**.
   - **Environment Variables**:
     - `DATABASE_URL`: the Neon string with its prefix changed from `postgresql://` to `postgresql+psycopg://`. Keep `?sslmode=require` and any other query parameters.
     - `CORS_ORIGINS`: `http://localhost:3000` for now; step 3.5 sets the real value.
   - **Advanced → Health Check Path**: `/api/health`.
   - Click **Deploy**.
4. When the log shows `Uvicorn running`, open `https://cellscope-api.onrender.com/api/health` (Render shows the exact address at the top of the service page; it may have a suffix). Expect `"status": "ok"`, the database `ok` with 306 compounds, all three datasets available, and `"evaluation_runs": false`. If the database shows `unavailable`, check `DATABASE_URL` and its `postgresql+psycopg://` prefix.

The free service sleeps after 15 minutes without requests; the next visitor waits about a minute while it starts.

To deploy backend changes later, rerun the three commands of step 2.2 (stage, build, push), then on Render click **Manual Deploy → Deploy latest reference**. Render does not redeploy on its own when you push an image.

## 3. Website: Vercel

1. Commit and push the repository to GitHub. The data folders are gitignored and stay local.
2. On vercel.com, **Add New → Project**, import `Vectora-Bio`, and set **Root Directory** to `vectora-bio/frontend`. Vercel detects Next.js; keep the default build settings.
3. Under **Environment Variables**, add `NEXT_PUBLIC_API_BASE_URL` = your Render address, for example `https://cellscope-api.onrender.com` (no trailing slash).
4. Click **Deploy**. The variable is built into the site, so redeploy after changing it.
5. Copy the production address (for example `https://cellscope.vercel.app`). On Render, open the service's **Environment**, set `CORS_ORIGINS` to it and save (Render restarts the service). Separate several origins with commas, for example a custom domain as well. Preview deployments use other addresses and are blocked unless you add them.
6. Open the site. The sidebar footer should read `Connected · 817 profiles`, and the manual tests in `docs/manual_tests.md` should pass, except for running new benchmarks.

Every push to the default branch now redeploys the website. The API only changes when you push a new image and redeploy it (end of step 2).

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Site shows "Cannot reach the API" | The Render service is asleep or still starting (open `/api/health` and wait about a minute), or `NEXT_PUBLIC_API_BASE_URL` is wrong. |
| Browser console shows a CORS error | `CORS_ORIGINS` on Render does not exactly match the site's address (scheme included, no trailing slash). |
| Health shows the database `unavailable` | `DATABASE_URL` missing, wrong prefix, or the Neon project was deleted. |
| Render log shows "Out of memory" or restarts | The free instance has 512 MB; the API peaks near 385 MB. Check that `EVALUATION_RUNS_ENABLED` is still `false`. |
| Render cannot pull the image | The image URL or tag is wrong, or the repository is private and the service has no registry credential. |
| Images say "Could not reach the Cell Painting Gallery" | Temporary S3 issue; images are fetched from the public gallery on first view. |
