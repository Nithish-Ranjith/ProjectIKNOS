---
name: deliver-webapp
description: Strict workflow for packaging the project and generating a status report when the user asks for the webapp.
---

# Deliver WebApp Workflow

When the user asks for the "webapp", "give me the webapp", or requests a packaged version of the current project, you MUST execute the following steps exactly as described. DO NOT skip any steps.

## Step 1: Create a Clean Archive
Generate a zip file of the project workspace. You must exclude heavy caches and environment folders.
1. Run a background terminal command to zip the core directories (e.g., `webapp`, `backend`, `docs`).
2. Use the exact exclusion flags: `-x "*/node_modules/*" "*/venv/*" "*/__pycache__/*" "*/dist/*" "*/.DS_Store" "*/.git/*"`
3. Save the zip file in the root of the workspace.

## Step 2: Generate Project Status Report
Create an artifact named `project_status_report.md`. The report MUST be structured exactly as follows. Do not skip any section even if empty:

1. **FILES CHANGED THIS SESSION** — full paths, one per line. Use your memory or `git status --short`.
2. **ROUTES/SCREENS IMPLEMENTED** — cross-check against the Master Route Map (e.g., App Architecture markdown). State: NOT STARTED / IN PROGRESS / DONE, with the actual file path implementing it.
3. **KNOWN BUGS OR INCOMPLETE LOGIC** — explicitly list anything built that is UI-only or not wired to real backend data. Be exhaustive and honest; an incomplete but disclosed gap is required.
4. **DEVIATIONS FROM SPEC** — anywhere the actual implementation differs from the specs, and why.
5. **GIT LOG** — output of `git log --oneline -20`.

## Step 3: Handoff
Reply to the user providing the absolute path to the generated zip file and prompting them to review the Project Status Report artifact.
