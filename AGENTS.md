# Repository Guidelines

## Project Structure & Module Organization
- `server.py` is the HTTP entrypoint for the intranet app. It wires the IP scanner, site account manager, and device inventory APIs.
- `scanner.py`, `site_accounts.py`, and `device_inventory.py` hold module-specific backend logic and JSON persistence rules.
- `web/` contains the single-page frontend: `index.html`, `app.js`, and `styles.css`.
- `tests/` contains `unittest` coverage for repository logic and HTTP APIs. Follow the existing `test_*.py` naming pattern.
- `data/` stores runtime JSON files such as `site_accounts.json` and `device_inventory.json`.
- `docs/` holds design notes, implementation plans, and research references.

## Build, Test, and Development Commands
- `python server.py` starts the local server on port `8765`.
- `run-ip-scan-webapp.bat` is the preferred Windows entrypoint for day-to-day local use.
- `python -m unittest discover -s tests -p "test_*.py"` runs the full backend/API test suite.
- `python -m py_compile server.py site_accounts.py device_inventory.py scanner.py` checks Python syntax without starting the app.
- `node --check .\web\app.js` validates frontend JavaScript syntax.

## Coding Style & Naming Conventions
- Use 4 spaces in Python and 2 spaces in HTML/CSS/JavaScript to match the current files.
- Prefer ASCII in code, but keep user-facing Korean copy in UTF-8 files.
- Use `snake_case` in Python, `camelCase` in JavaScript, and descriptive IDs such as `deviceInventoryTableBody`.
- Keep patches small and module-scoped; extend existing patterns before introducing new abstractions.

## Testing Guidelines
- Add or update `unittest` cases before changing backend behavior.
- Put API coverage in `tests/test_server_*.py` and repository coverage in `tests/test_*.py`.
- For frontend-only changes, at minimum rerun `node --check .\web\app.js` and smoke-test the affected flow through `python server.py`.

## Commit & Pull Request Guidelines
- No `.git` history is available in this working copy, so commit conventions cannot be verified from local history.
- Use concise Conventional Commit-style messages such as `feat: add device inventory csv import` or `fix: align device api fields`.
- In PRs, include: purpose, changed files/modules, test commands run, and screenshots for visible UI changes.

## Security & Configuration Tips
- Treat `data/*.json` as sensitive operational data. Do not commit real passwords or live school asset records.
- Keep the app on the school intranet only, and review Windows firewall rules before wider access.

## Design Context

### Users
- The primary users are the school Science and Information Department teacher and internal operations staff.
- They use the app during urgent moments such as pre-class network issues, account lookups, and device ledger updates.
- The core job is to find information quickly, judge the situation immediately, and update records without hesitation.

### Brand Personality
- Keep the interface calm, trustworthy, and precise.
- The product should feel like a real internal operations tool, not a promotional page.
- Tone should remain polite and practical rather than playful or decorative.

### Aesthetic Direction
- Use a bright light theme with IBM-style enterprise order and Airtable-style table readability.
- Favor Pretendard-centered Korean readability, white surfaces, soft gray structure, and navy accents.
- Avoid hero-banner layouts, excessive card decoration, purple AI-style palettes, and flashy gradients or glassmorphism.

### Design Principles
- Put search and status checking at the top of each important screen.
- Preserve tables as tables and avoid hiding operational data behind decorative UI.
- Make Korean copy short, naturally wrapped, and easy to scan.
- Show risk states immediately through both labels and color.
- Prioritize alignment, spacing, hierarchy, and repeatable patterns over visual effects.
