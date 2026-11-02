-- One-time setup for a local PostgreSQL server. Run as a superuser, e.g.:
--   psql -U postgres -h localhost -f scripts/setup_postgres.sql
-- Replace the password and put the same one in vectora-bio/.env (DATABASE_URL).

CREATE ROLE vectora WITH LOGIN PASSWORD 'change-me';
CREATE DATABASE vectora OWNER vectora;

-- Tables are created by the application, not here:
--   cd backend && python -m app.db.init_db
