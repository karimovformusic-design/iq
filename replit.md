# MINDORA Telegram Bot

MINDORA is an Uzbek-language Telegram bot for age-banded self-assessments, manual report payments, and secure administrator tools.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `sh entrypoint.sh` — apply migrations, seed the question bank, and start the Telegram bot
- `python -m pytest -q` — run MINDORA tests
- Required MINDORA env: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, and numeric Telegram IDs in `ADMIN_IDS`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)
- Bot: Python 3.12, aiogram, SQLAlchemy async, Alembic, PostgreSQL

## Where things live

- `mindora/handlers.py` — Telegram user and administrator flows
- `mindora/models.py` — PostgreSQL entities
- `mindora/services.py` — registration, tests, payments, dashboard, and broadcast logic
- `mindora/broadcast_worker.py` — persistent broadcast delivery
- `mindora/seed_data.py` and `mindora/seed.py` — test bank and idempotent seeding
- `migrations/` — Alembic schema migrations
- `README.md` — Replit, GitHub, and Railway setup instructions

## Architecture decisions

- Telegram admin authorization uses only numeric IDs in `ADMIN_IDS`; usernames are not accepted.
- Reports are private and released only after an administrator approves a manually checked receipt.
- Broadcast recipients are recorded in PostgreSQL; uncertain in-flight sends are not replayed after restart.
- Assessments are self-reflection tools, not validated clinical or official IQ instruments.

## Product

Users can take three age-banded tests and request a private report for 11,900 UZS. Administrators review receipts, manage users and tests, view live statistics, and send confirmed broadcasts to eligible users.

## User preferences
Payment defaults: recipient Karimov Nosirjon; card 5614684702056944; 11,900 UZS per report; administrator contact @Karimov_112.

Keep the payment defaults and assessment disclaimers consistent with `README.md`.

## Gotchas
- Configure `ADMIN_IDS` with positive numeric Telegram IDs; until then, nobody can open the admin panel.
- Railway polling deployment should use one replica. PostgreSQL must be configured before the container starts; startup runs Alembic and the idempotent seed.

- Do not run the Replit bot workflow and Railway service with the same Telegram token at the same time.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
