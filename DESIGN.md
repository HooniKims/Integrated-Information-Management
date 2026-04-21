# DESIGN.md

Project: Science and Information Department Internal Work App
Purpose: An internal operations tool used on the school intranet
Design Direction: IBM-style trust and clarity + Airtable-style data readability

## 1. Visual Theme & Atmosphere

- Prioritize trust, order, and operational clarity over visual flair.
- Use a light theme by default. This app will spend long hours showing tables and lists, so dark mode should not be the default.
- The product should feel like a real incident-response tool, not a marketing presentation.
- The first impression should be calm, precise, and actionable. Users should be able to search and check status immediately.
- The visual language should use thin clean lines, clear separation, minimal decoration, and high information density.
- Risk states such as IP conflicts, password exposure, and unknown location must stand out instantly.

Core keywords:

- trust
- public-sector operational order
- fast search
- table-first readability
- low learning cost

## 2. Color Palette & Roles

Basic rules:

- Use only white or very light gray for main backgrounds.
- Use one navy-based accent family as the main emphasis color.
- Keep danger, warning, and success meanings clearly separate.
- Do not use gradients, neon effects, or glassmorphism.

### Core Colors

- `--bg-page: #F5F7FA`
  - App background
- `--bg-surface: #FFFFFF`
  - Cards, tables, form inputs
- `--bg-subtle: #EEF2F6`
  - Filter bars, section dividers, inactive zones
- `--line-default: #D6DEE8`
  - Default border color
- `--line-strong: #B8C4D3`
  - Table header borders, active tab boundaries

### Text Colors

- `--text-primary: #15202B`
  - Titles and critical data
- `--text-secondary: #445266`
  - Supporting explanations
- `--text-muted: #69788C`
  - Metadata
- `--text-inverse: #FFFFFF`
  - Text on dark surfaces

### Brand / Action Colors

- `--accent-primary: #1F4E79`
  - Primary buttons, links, active states
- `--accent-primary-hover: #163A5C`
  - Primary hover state
- `--accent-soft: #DCE8F5`
  - Selected background

### Semantic Colors

- `--success: #2E7D32`
  - Healthy reporting state, verified state
- `--success-soft: #E6F4EA`
- `--warning: #B26A00`
  - Stale information, check needed
- `--warning-soft: #FFF4DD`
- `--danger: #C62828`
  - IP conflict, password exposure warning, missing data
- `--danger-soft: #FDECEC`
- `--info: #1565C0`
  - Informational state
- `--info-soft: #E8F0FE`

### Usage Rules

- On one screen, only up to two strong colors should visibly compete for attention.
- Most table surfaces should stay white, gray, and navy.
- Red is reserved for real risk states only.
- Green should be used for operational states like healthy connection or fresh report, not generic “saved” feedback unless needed.

## 3. Typography Rules

### Font Stack

- Primary Korean / English UI font: `Pretendard`, `Inter`, `system-ui`, `sans-serif`
- Use `JetBrains Mono`, `Consolas`, `monospace` where needed for numbers, IP addresses, and machine-like identifiers.

### Typography Philosophy

- This is an admin tool. Fast reading and quick data recognition matter more than dramatic display typography.
- Korean readability comes first.
- Identifiers such as IP addresses, asset IDs, device names, and account IDs should be visually distinct from ordinary body copy.

### Type Scale

- Page title: `28px / 700 / -0.02em`
- Section title: `22px / 700 / -0.01em`
- Card title: `18px / 700`
- Default body: `15px / 500 / 1.6`
- Secondary body: `14px / 500 / 1.55`
- Table body: `14px / 500 / 1.45`
- Labels / captions: `12px / 600 / 0.02em`
- Code-style identifier: `13px / 600 / monospace`

### Typography Rules

- Prefer short sentences and separated information units over long explanatory paragraphs.
- Use fonts or number settings with tabular figures for tables and IP addresses whenever possible.
- Do not force button labels into full uppercase.
- Avoid overly small text. Minimum `13px` even on mobile.

## 4. Layout Principles

### Shell Structure

- Default layout: fixed top header + left navigation + main content area.
- The main content should flow in this order:
  - search / filters
  - critical status
  - list / table
  - detail panel
- On the first screen, the primary search input must appear before anything else.

### Spacing Scale

- `4, 8, 12, 16, 20, 24, 32, 40, 48`
- Most frequently used spacing: `8, 12, 16, 24`

### Density Rules

- This app must support high information density. Do not over-space cards and rows.
- Default table row height: `44px` to `52px`
- Filter rows should hold as much as possible on one line while preserving `12px` to `16px` breathing room.

### Width Rules

- Maximum content width: `1440px`
- Do not center the main work area into a narrow marketing-style column.
- Table screens should use width generously.

## 5. Component Stylings

### Header

- Height: `64px`
- Left: product or service name
- Center or right: global search or quick jump
- Far right: logged-in user, latest sync time, logout
- White background with only a 1px bottom divider

### Sidebar

- White background
- Active item uses a navy accent plus a soft blue background
- Always show icon and text together, even when the menu grows
- Example menu:
  - IP Scan
  - Site Account Management
  - Device Inventory
  - Audit Log
  - Settings

### Buttons

- Primary:
  - dark navy background, white text
  - for Save, Search, New Entry
- Secondary:
  - white background + gray border
  - for Cancel, Close, Reset
- Danger:
  - soft red background or red outlined text button
  - for Delete, Disable, Revoke Access
- Button height:
  - default `40px`
  - large `44px`
- Border radius: `10px`

### Inputs

- White background
- Default border: `#D6DEE8`
- Focus state: navy outline or 2px soft shadow
- Placeholder text in gray
- Search inputs should feel larger and stronger than ordinary inputs

### Tabs

- Use for views like IP scan, by device, by user, conflict history
- Segmented tabs fit better than underline-only tabs
- Active tab: soft blue background + strong text

### Cards

- White card background
- Very light shadow or almost no shadow
- Use lines and spacing instead of visual gimmicks
- Inside cards, repeat the “label / value” pattern for fast scanning

### Tables

- Tables are the core component of this product.
- Use a light gray header background.
- On row hover, use a very soft blue background.
- The first column should usually hold the main identifier or name.
- Important columns:
  - IP
  - Device Name
  - User
  - Location
  - Device Type
  - Last Report Time
  - Status
- Prefer row click opening a right-side detail panel.
- If one cell contains more than one level of information, use a two-line structure:
  - line 1: primary value
  - line 2: supporting description

### Status Badges

- healthy: soft green background + green text
- needs check: soft yellow background + brown text
- conflict / danger: soft red background + red text
- locked / secure: soft blue or dark gray

### Detail Panel / Drawer

- Open from the right when a table row is selected
- Prefer this over full-page navigation for faster admin workflows
- Include edit actions, notes, history, and linked account information inside the panel

### Modal

- Use only for sensitive actions such as viewing passwords, confirming deletion, or changing permissions
- Always show a warning message and audit logging note inside the modal for sensitive actions

## 6. Screen-Specific Guidance

### A. IP Scan Page

This is the most important screen.

Required structure:

1. Top search bar
   - IP
   - computer name
   - user name
2. Quick filters
   - currently suspected conflict
   - no report in the last 24 hours
   - teacher laptop
   - tablet
3. Results table
4. Right-side detail panel

On this screen, the search area must be the most visually prominent element.

### B. Site ID / Password Management Page

- The page should feel halfway between a table and a secure vault.
- Users should be able to see site name, account ID, owner, last modified date, and access permission immediately.
- Passwords should be hidden by default.
- A “View” action must show a warning and explain that the access will be logged.
- This is a sensitive-information screen, so keep the tone even more restrained than the rest of the app.

### C. Device Inventory Page

- The goal is to replace the spreadsheet workflow, so table quality, filtering, and batch-edit flow matter.
- Do not try to model every field from day one.
- Start with the core fields first:
  - asset ID
  - device name
  - user
  - location
  - purchase year
  - years in use
  - status

## 7. Depth & Elevation

- Minimize shadows.
- Use borders and subtle background changes as the primary way to separate layers.
- Only floating elements should get a noticeable shadow.
- The UI should feel like a precise work surface, not a stack of floating marketing cards.

### Shadow Tokens

- `--shadow-soft: 0 2px 8px rgba(15, 23, 42, 0.06)`
- `--shadow-panel: 0 8px 24px rgba(15, 23, 42, 0.10)`

## 8. Motion & Interaction

- Motion should be short and restrained.
- Duration range: `140ms` to `220ms`
- Main uses:
  - table row hover
  - tab switching
  - opening the detail panel
  - save-complete toast

Avoid:

- large parallax effects
- exaggerated scale-up motion
- floating card animations
- meaningless loading spinner overuse

## 9. Do's and Don'ts

### Do

- Put search and status checking at the very top of the first screen.
- Keep tables as tables. Do not force them into narrow card grids.
- Make important identifiers like device names, IPs, and usernames bold and easy to scan.
- Make warning states immediately visible.
- Prioritize table and filter readability over decorative button styling.
- Use short, practical Korean copy in the actual product UI.
  - Examples:
    - `최근 보고 없음`
    - `위치 미확인`
    - `충돌 의심`
    - `저장 완료`

### Don't

- Do not add a giant hero banner like a landing page.
- Do not use the generic purple AI palette.
- Do not use glassmorphism, shiny gradients, or neon outlines.
- Do not hide real work data behind too many decorative cards.
- Do not over-style tables.
- Do not make charts the main attraction when charts are not the main job.

## 10. Responsive Behavior

- Desktop-first design
- Mobile support matters, but the first priority is usability on school PCs and laptops

### Breakpoints

- `>= 1280px`: full three-part work layout
- `768px ~ 1279px`: compact sidebar, wrapping filters
- `< 768px`: convert some tables into summary cards, detail opens as full-screen panel

### Touch Targets

- Minimum button / tab height: `40px`
- Keep spacing tablet-friendly

## 11. Voice & Microcopy

- Tone should be polite, but short
- Copy should be clear and admin-tool appropriate
- Avoid vague wording

Good examples:

- `최근 24시간 동안 보고되지 않았습니다.`
- `이 계정의 비밀번호를 열람하면 기록에 남습니다.`
- `같은 IP를 사용하는 장치가 2대 이상 감지되었습니다.`

Avoid:

- `문제가 발생했습니다`
- `Oops!`
- `매우 놀라운 통합 관리 경험`

## 12. Accessibility Rules

- Maintain at least WCAG AA contrast
- Do not rely on color alone for status. Pair color with labels and icons.
- Keyboard focus must always be visible.
- Never omit table headers or input labels.

## 13. Implementation Prompt Guide

When generating UI from this document, keep these directions:

- Make it feel like a school intranet operations tool
- Use calm IBM-style enterprise UI as the base visual language
- Make tables and filters as readable as Airtable
- Put IP search and status checking at the center of the first screen
- Favor readability and information density over decoration
- Use Pretendard-centered Korean UI defaults

## 14. One-Line Design Thesis

This app should feel like a bright, calm, data-centered internal operations tool that the school’s Science and Information Department can trust during urgent pre-class network incidents.
