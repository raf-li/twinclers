# Project: Twinclers Guard Codebase Audit

## Architecture & Codebase Map
- `core/`: Core security, cryptography, NTFS ACL manipulation, locking engines, configuration, master key logic.
- `gui/`: User interface components, views, dialogs, status monitors, settings windows.
- `libs/`: Shared utility libraries, system abstraction layers, helper modules.
- `locales/`: Internationalization / translation files and strings.
- `build_scripts/`: Packaging, compilation, and distribution scripts.
- `main.py`: Application entry point, CLI arguments, initialization workflow.

## Feature & Audit Inventory
| # | Feature / Area | Scope | Assigned Domain | Status |
|---|----------------|-------|-----------------|--------|
| 1 | Cryptography & Key Derivation | core/ crypto routines, key derivation, AES modes, IV/nonce handling, secret storage, padding, constant-time comparison | Explorer Track 1 (Crypto) | IN_PROGRESS |
| 2 | Windows NTFS ACL & Access Control | core/ locking, NTFS ACLs, inheritance, icacls/win32 API, privilege escalation, bypass vectors | Explorer Track 2 (ACL/Win32) | IN_PROGRESS |
| 3 | Maintainability, DRY & SSOT | Architecture, duplicate logic, single source of truth, modularity across core, gui, libs, build_scripts, main.py | Explorer Track 3 (Architecture/DRY) | IN_PROGRESS |
| 4 | Agent Rules & Anti-AI Code Signs | Over-commenting, generic names, boilerplate, blind defensive exceptions, redundant docstrings | Explorer Track 4 (Code Hygiene) | IN_PROGRESS |
| 5 | Report Compilation & Synthesis | Consolidate all findings into Bahasa Indonesia report at d:/Twinclers/audit_reports.txt | Worker (Synthesizer) | PLANNED |
| 6 | Gate Review & Audit Verification | Independent verification of report accuracy, line citations, and rule compliance | Reviewer / Auditor | PLANNED |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Deep Domain Exploration | Parallel exploration of 4 technical tracks across codebase | None | IN_PROGRESS |
| 2 | Report Compilation | Write d:/Twinclers/audit_reports.txt in Bahasa Indonesia | M1 | PLANNED |
| 3 | Independent Verification | Review findings, line citations, severities, and anti-AI compliance | M2 | PLANNED |
| 4 | Final Delivery | Final verification and reporting to Sentinel | M3 | PLANNED |
