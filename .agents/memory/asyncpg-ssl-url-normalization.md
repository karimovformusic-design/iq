---
name: asyncpg TLS URL normalization
description: Replit PostgreSQL connection URL compatibility with SQLAlchemy's asyncpg driver.
---

When normalizing a PostgreSQL URL for SQLAlchemy's asyncpg driver, translate the `sslmode` query parameter to `ssl` and preserve other query parameters.

**Why:** The Replit development database URL included `sslmode`, which asyncpg rejected as an unexpected connection argument during Alembic migration.

**How to apply:** Keep URL normalization centralized in settings and cover `sslmode` conversion with a test. Do not print database URLs while debugging connection setup.
