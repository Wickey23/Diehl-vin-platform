# Diehl VIN Platform

A Vercel-ready operations platform for VIN lookup, DTNA sales-order tracking, in-service date enrichment, imports/exports and change history.

## Architecture

- **Web:** Next.js + TypeScript on Vercel
- **Database:** Supabase/Postgres
- **DTNA:** separate secure Playwright worker for the persistent browser/MFA workflow
- **Dynamic fields:** stored in JSONB so newly added Dealer Reporting fields do not require an immediate migration

## Local setup

1. `npm install`
2. Copy `.env.example` to `.env.local`
3. Add Supabase variables
4. Run `supabase/schema.sql` in Supabase SQL Editor
5. `npm run dev`

## Vercel

`vercel.json` currently sets `git.deploymentEnabled` to `false`, so pushes do **not** automatically create Vercel deployments. Trigger deployments manually when ready.

## Security

Never commit DTNA credentials, browser profiles, OneDrive workbooks, exported VIN/customer data, Supabase service-role keys, or worker secrets.
