# INTEGRATION PLAN — Novahaku × NovaXinWei Synergy

## Date: 2026-09-21
## Workflow: 12-phase integration plan
## Design: Filesystem conventions + Hermes routing (NOT direct imports)

---

## Phase 0: Inventory (Current State)

### Novahaku (D:/Labs/novahaku) — v4.0.0
| File | Lines | Role |
|------|-------|------|
| `techniques/loader.py` | 500 | Payload loader |
| `testing/scripts/webtest.py` | 384 | Web test battery (14 modules) |
| `testing/web2-recon/scripts/recon_pipeline.sh` | 132 | Creates `engagements/<domain>/` structure |
| `testing/web2-recon/scripts/findings_gen.py` | 179 | evidence → findings.csv |
| `testing/web2-recon/scripts/build_xlsx.py` | 116 | XLSX builder |
| `engagements/sub.example.com/` | — | Template engagement (has `findings/findings.csv` header) |
| `SKILL.md` | 253 | Routing table with 58 rules |
| `config/TRIGGER_MAP.json` | — | 17 trigger categories (web-testing, prompt-attack, attack, etc.) |
| `scripts/reverse-skill/master-route.sh` | — | Routing orchestrator |

**Engagement directory structure (from `recon_pipeline.sh`):**
```
engagements/<domain>/
├── evidence/
├── recon/
├── findings/
│   └── findings.csv
└── notes/
```

### NovaXinWei (D:/Labs/novaxinwei) — v1.1.0
| File | Lines | Role |
|------|-------|------|
| `engine/fetch_chain.py` | 1,276 | 4-phase WAF bypass core |
| `engine/phase0.py` | 700 | 15 platform API routes |
| `engine/learning.py` | 179 | Self-learning route memory |
| `engine/observations_log.py` | 62 | JSONL fetch log |
| `channels/__init__.py` | — | 15 channel registry, `fetch_parallel()` |
| `cli.py` | 174 | argparse CLI (fetch, fetch-parallel, dorks, check) |
| `__main__.py` | — | Package entry point |

**NO `engagements/` directory yet.** Only `observations/fetch-YYYY-MM-DD.jsonl`.

### .gitignore Notes
- **Novahaku**: ignores `config.yaml`, `vault.dat`, key files, `__pycache__`
- **NovaXinWei**: ignores `observations/`, `*.jsonl`, `*.env`, `node_modules/`
- **Gaps**: Neither ignores `engagements/` content that might contain sensitive findings

### Hermes Skills Sync
Both repos sync to `C:/Users/Design/AppData/Local/hermes/skills/` and GitHub (novaestellar org). 3-way sync: D:/Labs ↔ hermes skills folder ↔ GitHub.

---

## Phase 1: Design Decisions

### Principle: Loose Coupling via Filesystem Convention

```
NovaXinWei stdout JSON ──→ engagements/<target>/ ──→ Novahaku reads
    (fetch output)           (shared directory)       (recon cache)
```

**NO direct Python imports between skills.** Integration works through:
1. **Filesystem convention**: Both skills agree on `engagements/<target>/` directory structure
2. **Hermes routing**: Agent reads NovaXinWei output, routes to Novahaku via SKILL.md triggers
3. **JSON schema**: Both skills read/write `recon.json` with a shared schema

### Shared Directory Convention
```
engagements/<target>/
├── recon.json              ← NovaXinWei writes, Novahaku reads
├── evidence/
│   ├── *.html              ← raw page captures
│   ├── *.json              ← API responses
│   └── *.har               ← HAR archives
├── recon/
│   ├── subdomains.txt
│   ├── ports.json
│   └── tech-stack.json
├── findings/
│   ├── findings.csv        ← Novahaku generates
│   └── findings.xlsx       ← Novahaku generates
└── notes/
    └── *.md
```

### JSON Schema (recon.json v1.0)

CORRECTED 2026-09-23. This block previously used a flat "waf_detected": false
and omitted subdomains/ports/endpoints. That shape does not match
engine/recon_schema.py, which is the single source of truth, so anything built
from the old example was unreadable by Novahaku (it reads recon.waf.detected,
not recon.waf_detected — the old reader returned None and reported "no WAF"
for every target). Fields below mirror ReconData exactly.

```json
{
  "version": "1.0",
  "target": "example.com",
  "timestamp": "2026-09-21T12:00:00Z",
  "source": "novaxinwei",
  "recon": {
    "subdomains": [],
    "ports": [],
    "tech_stack": {},
    "waf": {"detected": false, "product": null},
    "origin_ip": null,
    "endpoints": [],
    "dns": null,
    "certificates": null,
    "whois": null
  },
  "dorks": {
    "shodan": [],
    "github": []
  },
  "dorks": {
    "shodan": [],
    "github": []
  },
  "fetch_trace": {
    "attempts": 0,
    "verdict": "",
    "winner": {}
  },
  "metadata": {
    "fetches": 0,
    "cache_hits": 0,
    "channels_used": []
  }
}
```

### Sensitivity Rules
- `engagements/<target>/` must be in `.gitignore` — raw findings are SENSITIVE
- `recon.json` contains target info — must never be pushed to GitHub
- Only the schema definition and code go to GitHub, never engagement data
- Add `engagements/` to both repos' `.gitignore`

---

## Phase 2: Feature Implementation

### Feature 1: Auto-Handoff (NovaXinWei → Novahaku)

**Mechanism:** NovaXinWei CLI outputs JSON → agent reads → routes to Novahaku via SKILL.md trigger.

**New file:** `D:/Labs/novaxinwei/engine/engagement_writer.py`
- Standalone module, no imports from Novahaku
- `write_engagement(target, recon_data)` → creates `engagements/<target>/` dir + `recon.json`
- Called after successful fetch (opt-in: `--save-engagement` flag)

**New CLI flag in `D:/Labs/novaxinwei/cli.py`:**
- Add `--save-engagement` to `fetch` and `fetch-parallel` subcommands
- When set, calls `engagement_writer.write_engagement()`
- Default: OFF (no change to existing behavior)

**New file:** `D:/Labs/novaxinwei/engine/engagement_schema.py`
- Schema validator for `recon.json`
- `validate_recon(data) -> list[str]` returns errors or empty list
- Used by engagement_writer to validate before writing

**Verification:**
```bash
cd D:/Labs/novaxinwei
# Test schema validator
python -c "from engine.engagement_schema import validate_recon; print(validate_recon({'version':'1.0','target':'test.com','timestamp':'2026-09-21T00:00:00Z','source':'novaxinwei','recon':{'subdomains':[],'ports':[],'tech_stack':{},'waf':{},'endpoints':[]}}))"
# Expected: [] (no errors)

# Test engagement writer
python -c "from engine.engagement_writer import write_engagement; write_engagement('test.example.com', {'version':'1.0','target':'test.example.com','timestamp':'2026-09-21T00:00:00Z','source':'novaxinwei','recon':{'subdomains':[],'ports':[],'tech_stack':{},'waf':{},'endpoints':[]}})"
ls engagements/test.example.com/
cat engagements/test.example.com/recon.json | python -m json.tool

# Test CLI flag exists
python -m novaxinwei fetch --help | grep save-engagement
```

**Risk: LOW** — New files only. CLI flag is additive (opt-in).

---

### Feature 2: Shared Engagements Directory (NovaXinWei creates)

**Mechanism:** `engagement_writer.py` (from Feature 1) creates the directory structure matching Novahaku's convention.

**What engagement_writer.py creates:**
```python
def write_engagement(target: str, recon_data: dict) -> Path:
    base = Path("engagements") / target
    for sub in ["evidence", "recon", "findings", "notes"]:
        (base / sub).mkdir(parents=True, exist_ok=True)
    recon_path = base / "recon.json"
    with open(recon_path, "w", encoding="utf-8") as f:
        json.dump(recon_data, f, ensure_ascii=False, indent=2)
    # Write metadata
    meta = {
        "source": "novaxinwei",
        "created": datetime.utcnow().isoformat() + "Z",
        "schema_version": "1.0"
    }
    with open(base / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return base
```

**Verification:**
```bash
cd D:/Labs/novaxinwei
python -c "
from engine.engagement_writer import write_engagement
p = write_engagement('example.test', {'version':'1.0','target':'example.test','timestamp':'','source':'novaxinwei','recon':{},'dorks':{},'fetch_trace':{},'metadata':{}})
import os
for root, dirs, files in os.walk(p):
    for f in files:
        print(os.path.join(root, f))
"
# Expected: engagements/example.test/recon.json + metadata.json
# Expected dirs: evidence/, recon/, findings/, notes/
```

**Risk: LOW** — New file, creates directories only.

---

### Feature 3: Recon Cache Reader (Novahaku)

**Mechanism:** Novahaku reads `engagements/<target>/recon.json` if it exists. No code coupling to NovaXinWei — just reads a JSON file at a known path.

**New file:** `D:/Labs/novahaku/testing/web2-recon/scripts/recon_reader.py`
```python
"""Read recon.json from NovaXinWei engagement output.

Standalone — no imports from novaxinwei. Reads a JSON file at a
filesystem convention path. Returns None if no cache exists.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

# Convention: engagements live in the repo root's engagements/ dir
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def load_recon(target: str) -> Optional[dict]:
    """Load engagements/<target>/recon.json. Returns None if missing."""
    recon_path = _REPO_ROOT / "engagements" / target / "recon.json"
    if not recon_path.exists():
        return None
    with open(recon_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Basic validation
    if not isinstance(data, dict) or "version" not in data:
        return None
    return data

def get_waf_info(target: str) -> Optional[dict]:
    """Extract WAF detection info from cached recon."""
    data = load_recon(target)
    if data is None:
        return None
    # recon.waf is an object: {"detected": bool, "product": str|None}.
    # "waf_detected" was never a real key - this returned None for every target.
    return data.get("recon", {}).get("waf")

def get_tech_stack(target: str) -> Optional[dict]:
    """Extract tech stack from cached recon."""
    data = load_recon(target)
    if data is None:
        return None
    return data.get("recon", {}).get("tech_stack", {})
```

**Verification:**
```bash
cd D:/Labs/novahaku
# Test with no cache (should return None gracefully)
python -c "from testing.web2-recon.scripts.recon_reader import load_recon; print(load_renonexistent.target'))"
# Expected: None

# Test with existing cache (after Feature 2 creates one)
# First create a test engagement in novahaku's engagements/
mkdir -p engagements/test-cache
echo '{"version":"1.0","target":"test-cache","recon":{"waf":{"detected":true},"subdomains":[],"ports":[],"tech_stack":{},"endpoints":[]}}' > engagements/test-cache/recon.json
python -c "from testing.web2-recon.scripts.recon_reader import load_recon; print(load_recon('test-cache'))"
# Expected: dict with version, target, recon
rm -rf engagements/test-cache
```

**Risk: LOW** — New file, graceful fallback.

---

### Feature 4: Threat Intel Enrichment Pipeline

**Mechanism:** NovaXinWei fetches → writes recon.json → agent routes to Novahaku → Novahaku analyzes. No direct code path between skills.

**New file:** `D:/Labs/novaxinwei/engine/enrichment.py`
- Standalone module
- `enrich_recon(recon_data: dict) -> dict` — adds threat intel fields to recon.json
- Sources: WHOIS lookup, DNS history (passive), certificate transparency logs
- Uses only stdlib (`urllib.request`) + `json` — no new dependencies

**New CLI flag in `D:/Labs/novaxinwei/cli.py`:**
- Add `--enrich` to `fetch` subcommand
- When set, runs enrichment on successful fetch and includes in output/engagement
- Default: OFF (no change to existing behavior)

**New file:** `D:/Labs/novaxinwei/engine/threat_intel.py`
- Helper functions: `whois_lookup(domain)`, `ct_logs(domain)`, `dns_history(domain)`
- All use public APIs / stdlib HTTP — no API keys required for basic lookups
- Results merge into `recon.json` under `recon.threat_intel` key

**Enriched recon.json adds:**
```json
{
  "recon": {
    "threat_intel": {
      "whois": {"registrar": "...", "created": "...", "expires": "..."},
      "ct": {"certs": [], "issuer": "..."},
      "dns": {"records": [], "history": []}
    }
  }
}
```

**Verification:**
```bash
cd D:/Labs/novaxinwei
python -c "
from engine.enrichment import enrich_recon
data = {'version':'1.0','target':'example.com','recon':{},'dorks':{},'fetch_trace':{},'metadata':{}}
enriched = enrich_recon(data)
print('threat_intel' in enriched.get('recon', {}))
"
python -m novaxinwei fetch --help | grep enrich
```

**Risk: MEDIUM** — New files, opt-in via `--enrich`. No impact on existing fetch pipeline unless flag is set.

---

## Phase 3: SKILL.md Updates (Add-Only)

### Novahaku SKILL.md — ADD these entries (append only, DO NOT remove existing)

**New routing rules (append to routing table):**
```markdown
### Recon Integration (NovaXinWei synergy)
| Trigger | Action | Script |
|---------|--------|--------|
| `recon-cache`, `cached-recon`, `recon.json reader` | Load cached recon data | `testing/web2-recon/scripts/recon_reader.py` |
| `novaxinwei-output`, `waf-bypass results` | Read NovaXinWei fetch output | `engagements/<target>/recon.json` |
| `threat-intel enriched`, `enriched-recon` | Analyze enriched recon | Route to appropriate testing module |
```

**New trigger keywords (append to TRIGGER_MAP.json):**
```json
"recon-cache": {
  "description": "Cached recon data from NovaXinWei or previous scans",
  "keywords": [
    "recon-cache", "cached recon", "recon.json", "previously scanned",
    "engagement data", "skip recon", "use cached", "existing recon",
    "load recon", "read recon"
  ]
}
```

### NovaXinWei SKILL.md — ADD these entries (append only, DO NOT remove existing)

**New capabilities section (append):**
```markdown
### Engagement Output & Enrichment
- Write `engagements/<target>/` directory with standardized recon.json
- Schema validation before write
- Optional threat intel enrichment (WHOIS, CT logs, DNS)
- CLI flags: `--save-engagement`, `--enrich`
- Compatible with Novahaku's engagement directory convention
```

**New triggers (append):**
```yaml
triggers:
  - engagement output
  - save engagement
  - enrich recon
  - threat intel
```

### .gitignore Updates (add-only, DO NOT remove existing)

**Add to Novahaku `.gitignore`:**
```
# Engagement data (sensitive — never push)
engagements/*/
```

**Add to NovaXinWei `.gitignore`:**
```
# Engagement data (sensitive — never push)
engagements/*/
```

**Verification:**
```bash
cd D:/Labs/novahaku
# Confirm SKILL.md has new entries
grep -c "recon-cache" SKILL.md
# Expected: >0

cd D:/Labs/novaxinwei
grep -c "engagement output" SKILL.md
# Expected: >0

# Confirm .gitignore updated
grep "engagements" .gitignore
```

---

## Phase 4: 3-Way Sync Strategy

### Sync Flow
```
D:/Labs/novaxinwei/  ←→  GitHub novaestellar  ←→  hermes skills folder
D:/Labs/novahaku/     ←→  GitHub novaestellar  ←→  hermes skills folder
```

### What Goes Where
| Component | D:/Labs | GitHub | hermes/skills/ |
|-----------|---------|--------|----------------|
| Source code (engagement_writer.py, recon_reader.py, etc.) | ✅ | ✅ | ✅ |
| SKILL.md updates | ✅ | ✅ | ✅ |
| .gitignore updates | ✅ | ✅ | ✅ |
| engagements/ data (recon.json, evidence, findings) | ✅ | ❌ NEVER | ❌ NEVER |
| config.yaml, vault.dat, .env | ✅ | ❌ | ❌ |

### Sync Commands (post-implementation)
```bash
# Step 1: Commit code (not data) to GitHub
cd D:/Labs/novaxinwei
git add engine/engagement_writer.py engine/engagement_schema.py engine/enrichment.py engine/threat_intel.py cli.py SKILL.md .gitignore
git commit -m "feat: engagement output, enrichment pipeline (synergy integration)"
git push

cd D:/Labs/novahaku
git add testing/web2-recon/scripts/recon_reader.py SKILL.md config/TRIGGER_MAP.json .gitignore
git commit -m "feat: recon cache reader (NovaXinWei synergy)"
git push

# Step 2: Sync to hermes skills folder (rsync, skip sensitive)
rsync -av --exclude='engagements/' --exclude='config.yaml' --exclude='vault.dat' --exclude='*.env' \
  D:/Labs/novaxinwei/ C:/Users/Design/AppData/Local/hermes/skills/novaxinwei/

rsync -av --exclude='engagements/' --exclude='config.yaml' --exclude='vault.dat' --exclude='*.env' \
  D:/Labs/novahaku/ C:/Users/Design/AppData/Local/hermes/skills/novahaku/

# Step 3: Verify sync
diff <(cat D:/Labs/novaxinwei/engine/engagement_writer.py) <(cat C:/Users/Design/AppData/Local/hermes/skills/novaxinwei/engine/engagement_writer.py)
diff <(cat D:/Labs/novahaku/testing/web2-recon/scripts/recon_reader.py) <(cat C:/Users/Design/AppData/Local/hermes/skills/novahaku/testing/web2-recon/scripts/recon_reader.py)
```

---

## Phase 5: Verification Matrix

### Pre-Implementation Checklist
- [ ] All new files are ADD-ONLY (no existing files modified except SKILL.md/CLI append)
- [ ] No direct Python imports between novaxinwei and novahaku
- [ ] `engagements/*` in both .gitignore files
- [ ] Schema is self-contained (no external deps)
- [ ] CLI flags are opt-in (default OFF)
- [ ] No hardcoded API keys or secrets
- [ ] No hardcoded filesystem paths (use pathlib relative to repo root)

### Post-Implementation Checklist
```bash
# Feature 1: Auto-handoff
cd D:/Labs/novaxinwei
python -c "from engine.engagement_schema import validate_recon; print('PASS: schema validator')"
python -c "from engine.engagement_writer import write_engagement; print('PASS: engagement writer')"
python -m novaxinwei fetch --help | grep -q save-engagement && echo "PASS: CLI flag exists"

# Feature 2: Shared engagements dir
python -c "
from engine.engagement_writer import write_engagement
from pathlib import Path
import shutil
p = write_engagement('_test_verify', {'version':'1.0','target':'_test_verify','timestamp':'','source':'novaxinwei','recon':{},'dorks':{},'fetch_trace':{},'metadata':{}})
assert (p / 'recon.json').exists(), 'recon.json missing'
assert (p / 'metadata.json').exists(), 'metadata.json missing'
for d in ['evidence','recon','findings','notes']:
    assert (p / d).is_dir(), f'{d}/ missing'
shutil.rmtree(p)
print('PASS: engagement directory structure')
"

# Feature 3: Recon cache reader
cd D:/Labs/novahaku
python -c "
from testing.web2-recon.scripts.recon_reader import load_recon
result = load_recon('nonexistent_target')
assert result is None, 'Should return None for missing target'
print('PASS: graceful fallback'
)"
# With real cache
mkdir -p engagements/_test_verify
echo '{"version":"1.0","target":"_test_verify","recon":{}}' > engagements/_test_verify/recon.json
python -c "
from testing.web2-recon.scripts.recon_reader import load_recon
r = load_recon('_test_verify')
assert r is not None, 'Should load cached recon'
assert r['version'] == '1.0'
print('PASS: cache read')
"
rm -rf engagements/_test_verify

# Feature 4: Enrichment
cd D:/Labs/novaxinwei
python -c "
from engine.enrichment import enrich_recon
data = {'version':'1.0','target':'example.com','recon':{},'dorks':{},'fetch_trace':{},'metadata':{}}
enriched = enrich_recon(data)
assert 'threat_intel' in enriched.get('recon', {}), 'Enrichment missing'
print('PASS: enrichment pipeline')
"

# Existing functionality intact
cd D:/Labs/novaxinwei
python -c "from engine.fetch_chain import fetch; print('PASS: fetch_chain intact')"
python -c "from channels import fetch_parallel; print('PASS: channels intact')"
python -m novaxinwei check && echo "PASS: CLI check"
python -m novaxinwei fetch --help > /dev/null && echo "PASS: fetch help"
```

### Sensitive Data Audit
```bash
# Confirm no engagement data in git
cd D:/Labs/novaxinwei
git status --porcelain | grep -v "^??" | grep -i engagement
# Expected: only .py and .md files, NO engagement data

cd D:/Labs/novahaku
git status --porcelain | grep -v "^??" | grep -i engagement
# Expected: only .py and .md files, NO engagement data
```

---

## Phase 6: Implementation Order

### Step 1: Schema (foundation — everything depends on this)
- Create `D:/Labs/novaxinwei/engine/engagement_schema.py`
- Create `D:/Labs/novaxinwei/engine/engagement_writer.py`
- Verify: schema validates, writer creates dirs

### Step 2: NovaXinWei engagement output
- Modify `D:/Labs/novaxinwei/cli.py` — add `--save-engagement` flag (append to argparse)
- Verify: `python -m novaxinwei fetch --help` shows flag

### Step 3: Novahaku recon reader
- Create `D:/Labs/novahaku/testing/web2-recon/scripts/recon_reader.py`
- Verify: loads cached recon, returns None gracefully

### Step 4: Enrichment pipeline
- Create `D:/Labs/novaxinwei/engine/threat_intel.py`
- Create `D:/Labs/novaxinwei/engine/enrichment.py`
- Modify `D:/Labs/novaxinwei/cli.py` — add `--enrich` flag (append to argparse)
- Verify: enrichment adds threat_intel to recon data

### Step 5: SKILL.md + TRIGGER_MAP updates (add-only)
- Append routing rules to Novahaku SKILL.md
- Append capability + triggers to NovaXinWei SKILL.md
- Append `recon-cache` category to Novahaku TRIGGER_MAP.json

### Step 6: .gitignore updates (add-only)
- Append `engagements/*/` to both .gitignore files

### Step 7: Full verification
- Run all verification commands from Phase 5
- Test both CLIs still work
- Confirm sensitive data excluded from git

### Step 8: Commit + sync
- Git add only new/modified code files (not engagement data)
- Push to GitHub
- Sync to hermes skills folder via rsync
- Verify sync with diff

---

## Phase 7: Files Summary

### New Files (6 total)
| File | Lines (est.) | Skill |
|------|-------------|-------|
| `D:/Labs/novaxinwei/engine/engagement_schema.py` | ~80 | NovaXinWei |
| `D:/Labs/novaxinwei/engine/engagement_writer.py` | ~60 | NovaXinWei |
| `D:/Labs/novaxinwei/engine/enrichment.py` | ~100 | NovaXinWei |
| `D:/Labs/novaxinwei/engine/threat_intel.py` | ~120 | NovaXinWei |
| `D:/Labs/novahaku/testing/web2-recon/scripts/recon_reader.py` | ~50 | Novahaku |
| `INTEGRATION_PLAN.md` (this file) | ~350 | Documentation |

### Modified Files (4 total, append-only)
| File | Change | Risk |
|------|--------|------|
| `D:/Labs/novaxinwei/cli.py` | Add 2 CLI flags (`--save-engagement`, `--enrich`) | LOW |
| `D:/Labs/novaxinwei/SKILL.md` | Append capability section + triggers | LOW |
| `D:/Labs/novahaku/SKILL.md` | Append routing rules | LOW |
| `D:/Labs/novahaku/config/TRIGGER_MAP.json` | Append `recon-cache` category | LOW |

### Updated Files (2 total, append-only)
| File | Change |
|------|--------|
| `D:/Labs/novaxinwei/.gitignore` | Append `engagements/*/` |
| `D:/Labs/novahaku/.gitignore` | Append `engagements/*/` |

---

## Phase 8: Risk Matrix

| Risk | Severity | Mitigation |
|------|----------|------------|
| Existing CLI behavior broken | HIGH | Flags are opt-in (default OFF), no existing code paths modified |
| Direct Python imports between skills | MEDIUM | Enforced by design — all integration via filesystem + JSON |
| Sensitive data pushed to GitHub | HIGH | .gitignore updated, engagement_writer creates under engagements/ which is gitignored |
| Schema version drift | LOW | Schema version in JSON header, reader validates version field |
| 3-way sync conflict | LOW | Only new files + append-only changes, rsync excludes sensitive dirs |
| Enrichment adds latency | LOW | Opt-in via --enrich flag, not in default fetch path |

---

## Phase 9: Decision Log

| Decision | Choice | Reason |
|----------|--------|--------|
| Coupling mechanism | Filesystem + Hermes routing | Loose coupling requirement, each skill works independently |
| Schema location | NovaXinWei repo only | NovaXinWei is the writer, Novahaku is the reader; single source of truth |
| CLI flags | Opt-in (default OFF) | No existing functionality broken |
| Engagement data location | `engagements/<target>/` in each repo | Matches Novahaku convention, NovaXinWei adopts same |
| Enrichment approach | Stdlib HTTP only | No new dependencies, stays lazy |
| Sensitive data | .gitignore + never sync to GitHub | Security requirement |

---

## Phase 10: Future Enhancements (Not In Scope)

- [ ] NovaXinWei `--engagements-dir` flag for custom engagement path
- [ ] Novahaku `recon_pipeline.sh` integration (auto-read cache before scan)
- [ ] Cross-skill learning (NovaXinWei learning.py feeds Novahaku findings)
- [ ] Shared findings format (Novahaku findings.csv → NovaXinWei enrichment)
- [ ] Webhook/event notification between skills (when engagement is updated)
