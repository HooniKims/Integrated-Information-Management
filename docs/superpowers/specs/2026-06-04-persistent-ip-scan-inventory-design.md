# Persistent IP Scan Inventory Design

## Goal

Upgrade the IP scan screen from a temporary scan-result viewer into a persistent IP allocation ledger. The main question the screen must answer is: "Who is currently using which IP address?"

## Users And Workflow

The primary user is the school information department teacher. They need to open the app, immediately see the last known IP allocation status, scan the school range when needed, and update human-owned fields such as user, saved device name, and notes without losing them during later scans.

## Data Model

Create a JSON-backed scan inventory repository at `data/scan_inventory.json`.

Each IP row is keyed by normalized IPv4 address and stores:

- `ip`: normalized IPv4 address.
- `assigned_user`: manually entered user, owner, room, or person responsible for that IP.
- `custom_name`: manually saved device name. This should stay compatible with the existing scan device name behavior.
- `hostname`: latest hostname discovered by scan.
- `hostname_source`: latest source such as reverse DNS, NetBIOS, or nbtscan.
- `mac_address`: latest MAC address discovered by scan.
- `reachable`: latest ping reachability.
- `latency_ms`: latest response time.
- `status`: latest scan status, such as healthy, warning, offline, or conflict.
- `note`: latest scan note or manual note if no scan note is present.
- `manual_note`: manually entered note that scans must preserve.
- `reported_at`: timestamp from the latest scan result.
- `last_seen_at`: timestamp when the IP last responded.
- `first_seen_at`: timestamp when the IP first appeared in the saved ledger.
- `updated_at`: timestamp when the row was last changed.

Manual fields are `assigned_user`, `custom_name`, and `manual_note`. Automated scan updates must not overwrite those manual fields with blanks.

## Backend API

Add these routes:

- `GET /api/scan-inventory`: returns saved IP inventory rows and summary counts.
- `PATCH /api/scan-inventory/{ip}`: updates manual fields for one IP row.

Change scan completion behavior:

- When a scan job reaches `completed` or `cancelled`, merge every scan result into `scan_inventory.json`.
- Existing rows remain even if the latest scan does not include that IP.
- If a scanned IP is reachable, update `last_seen_at`.
- If a scanned IP is new, create a row using the scan result plus blank manual fields.
- If a scanned IP already exists, update scan-owned fields and preserve manual fields.

## Frontend Behavior

The IP scan screen should load saved inventory after login and whenever the user opens the IP scan tab. The table should show saved inventory even before a new scan starts.

The scan button should still run the same range scan. During scanning, live results can update the table. When the job finishes, the table should refresh from the saved inventory so the user sees the durable ledger state.

The table should be centered on allocation:

- IP
- Status
- User/Owner
- Device name
- Hostname source
- MAC
- Last seen
- Note

The detail panel should allow editing:

- User/Owner
- Saved device name
- Manual note

Existing filters remain useful, with one added filter:

- User missing: reachable or known IP rows where `assigned_user` is blank.

## Summary Cards

Keep current summary cards and calculate them from saved inventory on initial load:

- Total targets or saved IP rows.
- Reachable devices.
- Name unresolved.
- MAC confirmed.

The "total" label can remain scan-oriented while a scan is running, but at rest it should reflect saved rows.

## Error Handling

If `scan_inventory.json` is missing or malformed, the repository should recover to an empty inventory rather than breaking the app.

If manual update receives an invalid IP, return HTTP 400 with a clear JSON error.

If a scan job is missing in memory after a browser refresh, the saved inventory API still provides the last known state.

## Testing

Add repository tests for:

- New scan results create inventory rows.
- Later scan results update scan-owned fields and preserve manual fields.
- Reachable results update `last_seen_at`.
- Malformed JSON recovers to empty inventory.

Add server tests for:

- `GET /api/scan-inventory` returns saved rows and summary.
- `PATCH /api/scan-inventory/{ip}` updates manual fields.

Add frontend structural tests for:

- IP scan screen has a user/owner field.
- App loads `/api/scan-inventory`.
- App refreshes saved inventory after scan completion.

## Out Of Scope

This version does not discover physical switch ports. It tracks IP allocation only. It also does not implement historical diffs or a separate change log; the priority is a current static ledger that survives reconnects and server restarts.
