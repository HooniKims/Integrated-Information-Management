# Persistent IP Scan Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist IP scan results as an IP allocation ledger so the user can reopen the app and see who is using each IP address.

**Architecture:** Add a JSON-backed repository in `scanner.py`, expose it through `server.py`, merge completed scan results into the repository, and update the existing IP scan frontend to render saved inventory plus editable manual fields.

**Tech Stack:** Python `unittest`, stdlib HTTP server, JSON persistence, vanilla HTML/CSS/JavaScript.

---

## File Map

- Modify `scanner.py`: add `ScanInventoryRepository` and optional scan completion callback in `ScanManager`.
- Modify `server.py`: instantiate the repository, add `GET /api/scan-inventory`, add `PATCH /api/scan-inventory/{ip}`, and merge completed scans.
- Modify `web/index.html`: add user/owner and manual note fields to the IP scan detail panel and table headers.
- Modify `web/app.js`: load saved inventory on IP scan view, render user/owner columns, save manual allocation fields, refresh inventory after completed scans.
- Modify `web/styles.css`: add compact form styling if existing detail/editor classes are insufficient.
- Add/modify tests in `tests/test_scanner.py`, `tests/test_server_scan_inventory.py`, and `tests/test_device_inventory_form.py`.

---

### Task 1: Repository Persistence

**Files:**
- Modify: `scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write failing repository tests**

Add tests that create a temporary `ScanInventoryRepository`, merge scan results, preserve manual fields, update `last_seen_at`, and recover from malformed JSON.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_scanner`

Expected: FAIL because `ScanInventoryRepository` does not exist.

- [ ] **Step 3: Implement repository**

Add methods:

```python
class ScanInventoryRepository:
    def list_entries(self) -> list[dict[str, Any]]: ...
    def summarize_entries(self) -> dict[str, int]: ...
    def merge_scan_results(self, results: list[dict[str, Any]]) -> dict[str, Any]: ...
    def update_manual_fields(self, ip: str, payload: dict[str, Any]) -> dict[str, Any]: ...
```

Manual fields to preserve are `assigned_user`, `custom_name`, and `manual_note`.

- [ ] **Step 4: Run repository tests**

Run: `python -m unittest tests.test_scanner`

Expected: PASS.

---

### Task 2: Backend API And Scan Merge

**Files:**
- Modify: `server.py`
- Modify: `scanner.py`
- Test: `tests/test_server_scan_inventory.py`

- [ ] **Step 1: Write failing API tests**

Add API tests for:

- `GET /api/scan-inventory` returns `items` and `summary`.
- `PATCH /api/scan-inventory/10.73.78.51` updates `assigned_user`, `custom_name`, and `manual_note`.
- Completing a scan job calls the repository merge path.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m unittest tests.test_server_scan_inventory`

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Implement API routes**

Instantiate:

```python
SCAN_INVENTORY_REPOSITORY = ScanInventoryRepository(DATA_DIR / "scan_inventory.json")
SCAN_MANAGER = ScanManager(
    name_lookup=SCAN_NAME_REPOSITORY.get_name,
    completion_callback=SCAN_INVENTORY_REPOSITORY.merge_scan_results,
)
```

Add `GET /api/scan-inventory` and `PATCH /api/scan-inventory/{ip}`.

- [ ] **Step 4: Run API tests**

Run: `python -m unittest tests.test_server_scan_inventory`

Expected: PASS.

---

### Task 3: Frontend Inventory Loading And Rendering

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Test: `tests/test_device_inventory_form.py`

- [ ] **Step 1: Write failing frontend structural tests**

Assert that:

- The IP scan table contains `사용자/담당자`.
- `web/app.js` calls `/api/scan-inventory`.
- `web/app.js` contains a save function for scan inventory manual fields.

- [ ] **Step 2: Update HTML**

Add table/detail fields for `assigned_user` and `manual_note`.

- [ ] **Step 3: Update JS state and loading**

Add:

```javascript
scanInventoryLoaded: false,
```

Add `loadScanInventory()` that fetches `/api/scan-inventory`, updates summary, and calls `renderResults(items)`.

- [ ] **Step 4: Refresh after scan completion**

When `pollJob()` sees `completed` or `cancelled`, call `loadScanInventory({ force: true })`.

- [ ] **Step 5: Run frontend checks**

Run: `python -m unittest tests.test_device_inventory_form`

Run: `node --check .\web\app.js`

Expected: PASS.

---

### Task 4: Manual Field Editing

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Optionally modify: `web/styles.css`

- [ ] **Step 1: Add detail editor controls**

Add inputs in the selected IP detail panel:

- `scanAssignedUserInput`
- `detailCustomNameInput` already exists and should be reused
- `scanManualNoteInput`
- `saveScanInventoryButton`

- [ ] **Step 2: Save fields through API**

Add `saveScanInventoryEntry()` that PATCHes `/api/scan-inventory/{ip}` and updates `state.rawResults`.

- [ ] **Step 3: Keep existing name CSV behavior compatible**

When saving a custom name from the detail panel, continue updating `/api/scan-device-names` or have the backend inventory update also sync `ScanNameRepository`.

- [ ] **Step 4: Smoke-test the UI**

Start server and request `/`, `/app.js`, and `/api/scan-inventory`.

Expected: HTTP 200 for authenticated API tests or route coverage through unittest.

---

### Task 5: Verification And Shipping

**Files:**
- All modified files

- [ ] **Step 1: Run full tests**

Run: `python -m unittest discover -s tests -p "test_*.py"`

Expected: PASS.

- [ ] **Step 2: Run syntax checks**

Run: `python -m py_compile server.py site_accounts.py device_inventory.py scanner.py password_manager.py`

Run: `node --check .\web\app.js`

Expected: PASS.

- [ ] **Step 3: Commit and push**

Commit message:

```bash
git commit -m "feat: persist ip scan inventory"
git push origin main
```

---

## Self-Review

Spec coverage:

- Persistent scan inventory: Task 1 and Task 2.
- Saved screen after reconnect: Task 3.
- Manual user/IP ownership fields: Task 1, Task 2, and Task 4.
- Scan update preserving manual fields: Task 1 and Task 2.
- Tests and verification: Task 5.

No placeholders remain. Type names and route names are consistent across tasks.
