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
- [ ] Feature 1: engagement_output.py (NovaXinWei)
- [ ] Feature 2: recon_reader.py (Novahaku)
- [ ] Feature 3: recon_schema.py + recon_formatter.py (NovaXinWei)
- [ ] Feature 4: enrichment.py + enrichment_config.py (NovaXinWei)

## Phase 5: SKILL.md Updates
- [ ] Novahaku SKILL.md — add triggers
- [ ] NovaXinWei SKILL.md — add triggers + capabilities
- [ ] TRIGGER_MAP.json — add recon-cache category

## Phase 6: Code Audit
- [ ] Verify all new files have no syntax errors
- [ ] Verify all existing scripts still work
- [ ] Security audit — no hardcoded secrets
- [ ] Performance check — no unnecessary loops

## Phase 7-8: Oracle Review
- [ ] Oracle A: Branding/Naming
- [ ] Oracle B: Structural Integrity
- [ ] Oracle C: Code Quality
- [ ] Oracle D: Documentation
- [ ] Oracle E: Git/Integrity

## Phase 9: Tests
- [ ] test_synergy.sh — all tests pass
- [ ] Existing functionality preserved
- [ ] New features work as expected

## Phase 10: Reports
- [ ] PHASE_4_REPORT.md
- [ ] PHASE_5_REPORT.md
- [ ] PHASE_6_REPORT.md
- [ ] PHASE_7_REPORT.md
- [ ] PHASE_9_REPORT.md
- [ ] INTEGRATION_SUMMARY.md

## Phase 11: Commit & Push
- [ ] NovaXinWei committed + pushed
- [ ] Novahaku committed + pushed
- [ ] Both synced to hermes skills folder
- [ ] HANDOFF.md created
- [ ] ARCHIVE_MANIFEST.md created
