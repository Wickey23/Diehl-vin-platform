# Diehl VIN Platform

Excel-first VIN / DTNA operations platform.

## Architecture

- **Vercel/Next.js**: operator UI only. It does not store customer VIN data.
- **Windows worker**: persistent local service that owns the queue, browser automation, Outlook/OneDrive integration and workbook writes.
- **VIN_Master_Data.xlsx**: authoritative business database.
- **worker_state.db**: local SQLite checkpoint/queue only; it is not the business database.
- **Cloudflare Tunnel**: gives the Vercel UI an HTTPS path to the Windows worker without opening an inbound firewall port.

## First-time Windows setup

1. Open `worker/worker.env.example`, copy it to `worker/worker.env`, and set a long random `WORKER_ACCESS_KEY`.
2. Confirm `MASTER_WORKBOOK` points to the permanent OneDrive workbook.
3. Set `VIN_LOOKUP_COMMAND`, `DTNA_SYNC_COMMAND`, and `OUTLOOK_SYNC_COMMAND` to the existing local scripts/executables when available.
4. Run `worker/SETUP_AND_RUN.bat` and leave it open.
5. Run `worker/START_PUBLIC_TUNNEL.bat` and copy the generated `https://...trycloudflare.com` URL.
6. Open the website, click **Connect worker**, paste that URL and the access key.

## Lookup hook contract

`VIN_LOOKUP_COMMAND` receives:

- `DIEHL_VINS`: newline-separated VINs
- `DIEHL_RESULT_FILE`: path where the command should write JSON
- `DIEHL_WORKER_SLOT`: isolated worker number (1-8)
- `DIEHL_BROWSER_PROFILE`: isolated browser-profile directory

The result file may be either a JSON object keyed by VIN or an array of result objects containing `vin`. The worker writes successful results to `VIN_Master_Data.xlsx` through a single serialized Excel writer and appends to `Lookup Log` when that sheet exists.

## Security

Do not commit `worker.env`, browser profiles, `worker_state.db`, or VIN/customer exports. The public tunnel rejects requests without the local `WORKER_ACCESS_KEY`.
