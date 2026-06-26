# API Reference

FoodAssistant exposes a REST API used by the UI, Home Assistant, and any external integrations.

Interactive docs (Swagger UI) are available at `/docs` when the app is running.

## UI Routes

| Endpoint | Description |
|---|---|
| `GET /setup` | Web setup wizard |
| `GET /ui/` | Inventory dashboard |
| `GET /ui/expiring` | Expiring items view |
| `GET /ui/add` | Add food (barcode, photo, manual) |
| `GET /ui/pending` | Pending scans queue |
| `GET /ui/defaults` | Expiry defaults editor |
| `GET /ui/cook` | Recipe suggestions ranked by inventory |
| `GET /ui/recipes` | Browse and import recipes |
| `GET /ui/current-recipe` | Active recipe view with timers |
| `GET /ui/mealplan` | Week meal plan (requires Mealie) |
| `GET /ui/shopping` | Shopping list (requires Mealie) |
| `GET /ui/about` | About and credits |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Connectivity and service status |
| `GET /expiring/summary` | Urgency counts for Home Assistant sensors |
| `GET /inventory/dashboard` | Full stock grouped by storage location |
| `GET /admin/version` | Running version string |
| `GET /admin/check-update` | Compare running version against latest GitHub tag |
| `GET /admin/backup` | Download app data as a zip archive |
| `POST /admin/restore` | Restore app data from an uploaded backup zip |
| `POST /admin/backup/remote` | Push backup to configured rclone remote |
| `POST /admin/backup/test-remote` | Test that rclone can reach the configured remote |

## Current Recipe and Timers

The active recipe and timers live in server memory so every surface (web UI,
Stream Deck, satellites) shares one state.

| Endpoint | Description |
|---|---|
| `GET /current-recipe` | Return the active recipe (or null) |
| `POST /current-recipe` | Replace the active recipe |
| `DELETE /current-recipe` | Clear the active recipe |
| `POST /current-recipe/scale` | Set the servings-scale multiplier |
| `GET /current-recipe/timer-suggestions` | Timer suggestions parsed from the recipe's step durations |
| `POST /current-recipe/timers/start` | Start a real timer from a suggestion |
| `POST /current-recipe/from-mealie` | Load a Mealie recipe (by slug) as the active recipe |
| `GET /timers` | List every timer with fresh remaining/state |
| `POST /timers` | Create and start a timer for `seconds` |
| `GET /timers/{id}` | Return one timer's current state |
| `DELETE /timers/{id}` | Cancel and remove a timer |

## Recipe Import (requires Mealie)

| Endpoint | Description |
|---|---|
| `POST /mealie/recipes/import-url` | Import a recipe from a webpage (Mealie scraper, then LLM fallback) |
| `POST /mealie/recipes/import-file` | Import from a generic JSON / schema.org JSON-LD / Mealie export file |
| `POST /mealie/recipes/import-external` | Save an external-source recipe into Mealie |
| `POST /mealie/recipes/extract-photo` | Vision-LLM extraction from a photographed recipe |
| `POST /mealie/recipes/generate` | Ask the LLM to write a full recipe for a dish name |

## Appliance (Pi-only)

These call the host bridge on a Pi appliance and return a clear error elsewhere.

| Endpoint | Description |
|---|---|
| `POST /setup/restore` | Full Grocy + Mealie + app snapshot restore via the host bridge |

`POST /setup/restore` is distinct from `POST /admin/restore`: the former restores
the whole stack (Grocy, Mealie, app data) from a snapshot already on the device
(an absolute `.tar.gz` path or `rclone:<remote-path>`), while `/admin/restore`
rewrites only this app's data directory from an uploaded zip. The host bridge
itself exposes a `POST /restore` it proxies to, but this file documents the app API.

## Query Parameters

`GET /ui/expiring?days=N`: show items expiring within N days (default 7).

`GET /admin/backup?include_secrets=true`: include API keys and passwords in the backup zip (omit for a safe-to-store redacted copy).

`GET /inventory/dashboard` returns JSON matching the Grocy stock structure, grouped by storage category. This is the endpoint the Home Assistant Lovelace dashboard polls.

`GET /expiring/summary` returns urgency bucket counts:

```json
{
  "expired": 2,
  "today": 0,
  "3d": 3,
  "ok": 14
}
```

See the live `/docs` page for full request/response schemas.
