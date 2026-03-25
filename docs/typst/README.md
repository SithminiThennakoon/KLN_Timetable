# Typst Documentation Project

This directory is the source of truth for the handover documentation package.

Outputs:

- `out/User Manual.pdf`
- `out/Technical Documentation.pdf`
- `out/ABC Handover.pdf`

## Files

- `theme.typ`: shared styling and reusable blocks
- `user-manual.typ`: end-user manual
- `technical-documentation.typ`: client technical setup and troubleshooting guide
- `abc-handover.typ`: ABC handover and delivery checklist
- `build-docs.ps1`: local build script

## Build

Install Typst and run:

```powershell
cd docs/typst
.\build-docs.ps1
```

If `typst` is not on PATH, pass it explicitly:

```powershell
.\build-docs.ps1 -TypstExe "C:\path\to\typst.exe"
```

## Authoring Rule

Before updating any section, verify that section against the current repo state first. These documents are meant to describe the active snapshot-first system, not historical flows.
