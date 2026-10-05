---
name: terratrace-audit
description: Strict guidelines for conducting concept-fidelity and verification audits in the TerraTrace project.
---

# TerraTrace — Full System Recovery & Concept-Fidelity Audit Guidelines

When asked to audit, verify, or review the TerraTrace codebase, you MUST adhere to the following strict rules:

1. **Prove What Exists**: You are not summarizing what you built. You are proving what exists. Every claim in your output must cite the exact file path and line number. "Implemented X" with no citation is not acceptable output.
2. **No Narrative Summaries**: Output is a structured table, per item below: STATUS (`REAL` / `STUB` / `BROKEN` / `MISSING` / `CANNOT VERIFY`), FILE:LINE evidence, and one factual sentence. Nothing else.
3. **Compilation is not Functioning**: "It builds with zero TypeScript errors" is not evidence of anything in this audit. Compiling is not functioning. Do not report it as progress.
4. **Manual Verification**: If something cannot be verified without running the app live, say `CANNOT VERIFY — REQUIRES MANUAL TEST` explicitly. Do not guess and report it as done.
5. **Feature Freeze**: Do not add, redesign, or "improve" anything during this pass. Feature work and visual work are frozen until the audit is 100% accounted for. Fixing a confirmed BROKEN item is allowed; anything beyond the minimum fix to make it REAL is not.
6. **Authoritative Sources**: Treat the following as the ONLY authoritative source of truth for what should exist: 
   - `TerraTrace_App_Architecture.md`
   - `TerraTrace_Functional_Spec.md`
   - The project PRD
   - The dataset READMEs
   If the current code disagrees with these documents, the documents win — the code is wrong, not the spec, unless explicitly told otherwise.
