# FoodAssistant interactive demo

`index.html` is a self-contained, no-backend interactive demo of FoodAssistant
(inventory, scanning, recipe suggestions, cameras, the unit converter, and the
Stream Deck). It runs entirely in the browser with sample data; open it locally
or host it as a static site.

## Live demo (Cloudflare Pages)

The demo is published to Cloudflare Pages and redeploys automatically whenever
anything under `docs/demo/` changes on `main`, via
[`.github/workflows/deploy-demo.yml`](../../.github/workflows/deploy-demo.yml).

Once set up, the live demo is at: **https://foodassistant-demo.pages.dev**

### One-time setup (pick one)

**Option A - GitHub Actions (already wired up):**
1. In Cloudflare, create an API token with the **Cloudflare Pages: Edit**
   permission, and note your **Account ID** (Cloudflare dashboard, right sidebar).
2. In this repo: **Settings > Secrets and variables > Actions > New repository
   secret**, add:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
3. Push any change under `docs/demo/` (or run the workflow manually from the
   Actions tab). The first run creates the `foodassistant-demo` Pages project and
   deploys it. Subsequent changes redeploy automatically.

**Option B - Cloudflare dashboard Git integration (no secrets, no workflow):**
1. Cloudflare dashboard > **Workers & Pages > Create > Pages > Connect to Git**.
2. Pick this repository.
3. Build settings: **Framework preset** = None, **Build command** = (blank),
   **Build output directory** = `docs/demo`.
4. Save and deploy. Cloudflare then rebuilds on every push to `main`.

Either path keeps the published demo in step with development. If you use Option
B, you can delete `.github/workflows/deploy-demo.yml` (it just no-ops without the
secrets).

## Updating the demo

The demo is a hand-built static mock, not the live app, so it does not track
features automatically. When a feature is worth showcasing, edit `index.html`;
the deploy then publishes it on the next push.
