# TODO CHECKLIST — Synergy Integration

## Phase 0: Discovery ✅
- [x] Deep audit Novahaku (32 .py files, 16 .sh files)
- [x] Deep audit NovaXinWei (44 .py files, 15 channels)
- [x] Map all dependencies
- [x] Identify integration points
- [x] Create INVENTORY.md

## Phase 1: Risk Assessment ✅
- [x] Identify 10 risks
- [x] Mitigate all CRITICAL/HIGH risks
- [x] Create RISK_MATRIX.md

## Phase 2: Backup ✅
- [x] Backup NovaXinWei → D:/Labs/novaxinwei-backup-20260920
- [x] Backup Novahaku → D:/Labs/novahaku-backup-20260920
- [x] Create BACKUP_MANIFEST.md

## Phase 3: Plan ✅
- [x] Create INTEGRATION_PLAN.md
- [x] Create TODO_CHECKLIST.md

## Phase 4: Implementation
- [x] Feature 1: engagement_output.py (NovaXinWei)
- [x] Feature 2: recon_reader.py (Novahaku)
- [x] Feature 3: recon_schema.py (NovaXinWei)
- [!] recon_formatter.py written but NOT WIRED: zero call sites in either repo
      (grep -rn "recon_formatter" returns only this checklist). Present, unused.
- [x] Feature 4: enrichment.py + enrichment_config.py (NovaXinWei)

## Phase 5: SKILL.md Updates
- [x] Novahaku SKILL.md — add triggers
- [x] NovaXinWei SKILL.md — add triggers + capabilities
- [x] TRIGGER_MAP.json — add recon-cache category

## Phase 6: Code Audit
- [x] Verify all new files have no syntax errors
- [x] Verify all existing scripts still work
- [x] Security audit — no hardcoded secrets
- [x] Performance check — no unnecessary loops

## Phase 7-8: Oracle Review
- [ ] Oracle A: Branding/Naming
- [ ] Oracle B: Structural Integrity
- [ ] Oracle C: Code Quality
- [ ] Oracle D: Documentation
- [ ] Oracle E: Git/Integrity

## Phase 9: Tests
- [x] test_synergy.sh — all tests pass
- [x] Existing functionality preserved
- [x] New features work as expected
- [x] engagement_schema.py selftest — 15/15
- [x] engagement_writer.py selftest — 24/24
- [x] chain_state.py selftest — 26/26
- [!] results_reader.py NOT WIRED: zero call sites in either repo, so the
      "NovaXinWei reads Novahaku results" direction has no live consumer yet.
      Selftest passes (40/40) but nothing calls the module.
- [x] threat_intel.py selftest — 41/41
- [x] recon_formatter.py selftest — 41/41
- [x] enrichment_config.py selftest — 27/27
- [x] novahaku engagement.py selftest — all checks passed (assert-based)
- [x] novahaku engage_runner.py selftest — all checks passed (assert-based)

## Phase 10: Reports
- [ ] PHASE_4_REPORT.md
- [ ] PHASE_5_REPORT.md
- [ ] PHASE_6_REPORT.md
- [ ] PHASE_7_REPORT.md
- [ ] PHASE_9_REPORT.md
- [ ] INTEGRATION_SUMMARY.md

## Phase 11: Commit & Push
- [ ] NovaXinWei committed + pushed — NOT DONE: 10 files still uncommitted
- [ ] Novahaku committed + pushed — NOT DONE: 3 files still uncommitted
- [ ] Both synced to hermes skills folder
- [ ] HANDOFF.md created — NOT PRESENT: not found anywhere in either repo
- [ ] ARCHIVE_MANIFEST.md created — NOT PRESENT: not found anywhere in either repo

Note: both lines above previously read "[x]". Verified false on 2026-09-23 with
`find /d/Labs/novaxinwei /d/Labs/novahaku -name "HANDOFF.md" -o -name "ARCHIVE_MANIFEST.md"`
which returned nothing.

Note: the two commit lines above previously read "[x]". They were false - no
commit had been made for this work at that point. Unchecked on 2026-09-23 and
re-checked against `git status --porcelain` in both repos.
