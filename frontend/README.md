# PharmaCore Frontend

React + TypeScript + Vite frontend for Pharma_App.

The UI follows the supplied PharmaCore reference as its visual source of truth: near-black enterprise surfaces, thin green-gray structural rules, technical monospace operational data, restrained emerald/rose/violet status accents, a fixed left command rail, compact KPI cards and dense operational tables.

## Completed workspaces

- Operations — production dashboard, live batch monitoring, product creation and production-order creation
- Quality — QC queue, pass/fail actions and release actions
- Commercial — sales-order and fulfillment register
- Analytics — live batch-distribution and operational-signal views
- Admin — facilities and role/access overview

## Run

```bash
npm install
npm run dev
```

Set `VITE_API_URL` to the FastAPI base URL. Default: `http://localhost:8000/api/v1`.

The frontend stores the backend JWT locally and sends it as a bearer token to `/api/v1` endpoints.

## Build

```bash
npm run build
```

GitHub Actions also builds the production container after every frontend change so the shipping image is continuously verified.
