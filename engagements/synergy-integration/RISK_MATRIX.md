# RISK MATRIX — Novahaku × NovaXinWei Synergy Integration

## Date: 2026-09-20

| # | Risk | Probability | Impact | Severity | Mitigation | Status |
|---|------|-------------|--------|----------|------------|--------|
| R1 | NovaXinWei `cli.py` breaks from new `engagements/` output | LOW | HIGH | MEDIUM | Add `--engagements-dir` flag, default OFF. Existing CLI unchanged. | MITIGATED |
| R2 | Novahaku `webtest.py` breaks from new `recon.json` reader | LOW | HIGH | MEDIUM | New file `engagement_reader.py` — no modification to existing `webtest.py`. | MITIGATED |
| R3 | `recon_pipeline.sh` overwrites existing `engagements/` structure | LOW | CRITICAL | CRITICAL | Read-only check: only ADD `recon.json`, never delete/modify existing files. | MITIGATED |
| R4 | `fetch_chain.py` output format change breaks downstream | MEDIUM | HIGH | HIGH | JSON schema v1.0 — additive fields only, backward compatible. | MITIGATED |
| R5 | `learning.py` conflicts with new cache system | LOW | MEDIUM | LOW | Separate concerns: `learning.py` = route memory, `recon_cache.py` = engagement cache. No overlap. | MITIGATED |
| R6 | Hermes routing breaks from new SKILL.md triggers | LOW | HIGH | MEDIUM | Triggers are ADD-ONLY, never remove existing. Add new trigger lines at end. | MITIGATED |
| R7 | `content_safety.py` blocks enrichment output as prompt injection | MEDIUM | MEDIUM | LOW | Enrichment passes through same safety envelope. No bypass. | MITIGATED |
| R8 | GitHub push includes sensitive data | LOW | CRITICAL | CRITICAL | `.gitignore` already blocks `.env`, `vault.dat`, `keys_*.txt`. Add `recon.json` pattern. | MITIGATED |
| R9 | `build_xlsx.py` fails on new evidence format | LOW | LOW | INFO | Additive fields only — `recon.json` is separate from existing evidence. | ACCEPTED |
| R10 | `observations_log.py` grows unbounded | LOW | LOW | INFO | Existing rotation: daily JSONL files. No change needed. | ACCEPTED |

## Summary
- **CRITICAL:** 2 (R3, R8) — both mitigated with clear protocols
- **HIGH:** 2 (R4, R2) — mitigated with backward-compatible design
- **MEDIUM:** 3 (R1, R6, R7) — mitigated with additive-only approach
- **LOW/INFO:** 3 (R5, R9, R10) — accepted

## Gate Status: ✅ ALL CRITICAL RISKS MITIGATED — Proceed to Phase 3
