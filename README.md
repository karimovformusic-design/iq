# MINDORA Telegram Bot

MINDORA is a Telegram bot for three age-banded, Uzbek-language self-assessments: reasoning practice, personality reflection, and everyday psychological wellbeing. It stores registrations, test attempts, private reports, payment receipts, moderation history, notification preferences, and broadcasts in PostgreSQL.

## What works

- `/start` registration that asks for first name, surname, and a validated age (7–70) before opening the main menu.
- 20 unique questions per attempt, answer validation, scoring, and a personalized report.
- After a test, users can choose to delete the result or pay to receive it. An IQ-style test produces a completion-certificate PDF after admin approval; personality and wellbeing tests provide written analysis.
- Manual report payments at **11,900 UZS** per report, receipt upload, and administrator approval or rejection.
- Admin access based only on numeric Telegram IDs in `ADMIN_IDS`.
- Live database-backed dashboard, paginated user directory, user search/details, payment review/history, test management/statistics, and bot settings.
- Confirm-before-send broadcasts with optional photo/caption, consent-aware targeting, persistent recipient status, retries for known temporary errors, and completion summaries.
- `/id` displays only the current Telegram user's numeric ID to help configure administrator access.
- `/healthz` checks both the process and its PostgreSQL connection.

## Assessment and payment limitations

These questionnaires are **not clinically validated**, and the reasoning result is not an official IQ score. The IQ-style completion certificate records the exercise score and an exercise-specific performance band; when enough data exists, it also shows an approximate percentile among MINDORA users in the same age band. This is not a general-population norm, an IQ qualification, or a claim of accuracy. Personality and wellbeing reports are non-diagnostic self-reflections; wellbeing questions refer to the previous two weeks. Updated question versions are stored separately so completed attempts retain their original wording. The assessments are not age-normed instruments.

The IQ-style PDF uses the first name and surname entered during bot registration and the age recorded for that test attempt. Every `/start` begins registration again; the prior profile remains stored until the user submits the new name, surname, and age. The main-menu **Joriy amalni bekor qilish** button (or `/cancel`) clears the saved name, surname, and age and starts registration again, while preserving test results, reports, and payment history. In an authorized admin workflow, `/cancel` only cancels that admin action.

The IQ completion PDF is bilingual and includes a certificate reference number and an exercise-specific performance band. A percentile is shown only when there are at least 10 distinct MINDORA users with completed IQ results in the same age band by the test date; it is an approximate comparison within MINDORA, not a general-population norm. The document is not an accredited IQ credential, clinical assessment, or measurement of a person’s overall potential.

Payments are manual. The bot records the receipt's Telegram file reference; an administrator must check the transfer in their banking app and approve or reject it. The bot does not contact a bank, verify a transfer automatically, or process refunds.

The payment defaults are set in `mindora/constants.py`:

- Recipient: Karimov Nosirjon
- Card: 5614684702056944
- Price per report: 11,900 UZS
- Administrator contact: @Karimov_112

The card number and receipt contents are not written to application logs. The number is shown only in the payment instructions and the administrator-only settings screen.

## Local setup

Requirements: Python 3.12+, a PostgreSQL database, and a Telegram bot token from BotFather.

1. Copy `.env.example` to `.env` and replace every placeholder. Do not commit `.env`.
2. Set `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, and `ADMIN_IDS`. `ADMIN_IDS` is a comma-separated list of numeric Telegram IDs; usernames are never accepted for authorization.
3. Install dependencies:

   ```sh
   python -m pip install -r requirements-dev.txt
   ```

4. Apply the database migration and seed the initial test bank:

   ```sh
   alembic upgrade head
   python -m mindora.seed
   ```

5. Run the bot:

   ```sh
   python -m mindora
   ```

6. Run automated tests:

   ```sh
   python -m pytest -q
   ```

For Replit, add `TELEGRAM_BOT_TOKEN` using **Tools → Secrets**. Keep the automatically provided development `DATABASE_URL`; do not replace it with a Railway URL. Set `ADMIN_IDS` as an environment variable after retrieving the ID with `/id` in the bot. The `MINDORA Telegram Bot` workflow is configured but not auto-started; start it only after configuring `ADMIN_IDS`. It runs `entrypoint.sh`, which applies migrations, seeds idempotently, and starts the bot. Do not run this workflow at the same time as the Railway service with the same token: Telegram long polling supports only one active poller.

## Get and configure an administrator Telegram ID

1. Start or open a private chat with the bot and send `/id`.
2. Copy the numeric ID shown in that chat.
3. In Replit, add a non-secret environment variable named `ADMIN_IDS`; in Railway, add a service variable with the same name.
4. Use only the numeric ID, for example `ADMIN_IDS=123456789`. For several administrators, separate IDs with commas, for example `ADMIN_IDS=123456789,987654321`.
5. Restart the bot after changing the variable. Until at least one ID is configured, no one can open the admin panel.

## GitHub setup

If this folder is not already connected to the intended repository:

```sh
git init
git add .
git commit -m "Build MINDORA Telegram bot"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

If it is already a Git repository, use its existing remote and push the new commit rather than creating a second repository. Confirm `.env` and all secrets are absent from the commit before pushing.

## Railway deployment

1. Create a Railway project and deploy the GitHub repository as a service. Railway detects the root `Dockerfile`.
2. Add a PostgreSQL service to the same Railway project.
3. In the bot service's variables, set:
   - `TELEGRAM_BOT_TOKEN` — the token from BotFather.
   - `DATABASE_URL` — Railway's reference to the PostgreSQL service URL.
   - `ADMIN_IDS` — comma-separated numeric Telegram administrator IDs.
   - `APP_ENV=production`.
4. Keep the bot service at **one replica** and stop the Replit bot workflow while Railway is running. It uses Telegram long polling; multiple pollers for the same token conflict. The broadcast worker is safe against concurrent database claims, but a single bot instance is the supported polling setup.
5. Set the service health-check path to `/healthz` if enabling Railway health checks. The container uses Railway's `PORT`.
6. Deploy. `entrypoint.sh` runs `alembic upgrade head`, seeds the test bank idempotently, and then starts Telegram polling. Persistent users, payments, and broadcast queues live in PostgreSQL, not the container filesystem.
7. Check the Railway service logs for startup success, then test `/start`, `/id`, a test attempt, a receipt upload, admin review, and a small confirmed broadcast before using it with real users.

Do not put the bot token, database URL, card number, receipts, or private reports in GitHub. Configure the token and database URL in Railway's variable manager.

## Data and migration notes

- Schema: `mindora/models.py`
- Alembic configuration and first migration: `alembic.ini`, `migrations/`
- Idempotent initial question bank: `mindora/seed_data.py`, `mindora/seed.py`
- Active test bank: 300 questions, with 20 distinct, age-neutral questions for each of three categories in each of five age bands (7–12, 13–17, 18–30, 31–50, 51–70). Old surplus rows are deactivated, not deleted.
- Broadcast delivery records move through `pending`, `sending`, `sent`, `failed`, `blocked`, and `skipped`. Consent and account status are rechecked immediately before delivery. On restart, a previously `sending` delivery is marked uncertain/failed instead of being replayed, because Telegram does not offer an idempotency key for send operations. This avoids duplicate re-sends at the cost of reporting an interrupted delivery as uncertain.
- Service announcements go only to active users who allow service messages. Promotional messages go only to users who explicitly opt in. A user who has blocked the bot is marked unreachable and excluded from future broadcasts.
- Admin user details show status, test history, and payment history, but never the user's answer-by-answer responses or report text.
