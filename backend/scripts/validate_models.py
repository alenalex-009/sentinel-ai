"""Sentinel AI — model validation script for CI.

Runs the same invariants the previous inline .gitlab-ci.yml block asserted,
but as a real file: no YAML/shell/Python triple-quoting, readable, and
testable locally via `python scripts/validate_models.py` from backend/.

Exits non-zero (and prints FAIL lines) if any invariant is violated, so the
CI job fails loudly when engine constants drift from the validated seeds.
"""

import sys

sys.path.insert(0, ".")

from app.services.risk_engine import compute_risk, compute_vulnerability
from app.services.risk_validation import (
    validate_munnar_central,
    validate_site_a_capacity,
    validate_suitability_site_a,
)

failures = []


def check(label, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        failures.append(label)


# 1. Vulnerability matches the validated seed value.
v = compute_vulnerability(78, 71, 76, 69)
check("Vulnerability", abs(v - 73.85) < 0.1, f"computed {v:.2f} (expected ~73.85)")

# 2. Risk computes from hazard/exposure/vulnerability.
r = compute_risk(88, 84, v)
check("Risk", 0 <= r <= 100, f"computed {r:.2f} from hazard=88 exposure=84 vuln={v:.2f}")

# 3. Full Munnar Central audit runs, and the engine's operational risk
#    still reproduces the validated demo seed (94).
audit = validate_munnar_central()
c = audit["computed"]
check(
    "Munnar Central audit",
    c["current_risk_matches_seed"] is True
    and all(k in c for k in ("vulnerability", "current_risk", "rpi")),
    f"vuln={c['vulnerability']}, base={c['base_risk']}, "
    f"current={c['current_risk']} (seed {c['stored_demo_risk']}), rpi={c['rpi']}",
)

# 4. Site A carrying capacity: c_safe and bottleneck match the seed.
cap = validate_site_a_capacity()
check(
    "Capacity",
    cap["c_safe"] == 3200 and cap["bottleneck"] == "water",
    f"c_safe={cap['c_safe']}, bottleneck={cap['bottleneck']}",
)

# 5. Suitability score recomputed from components matches the seed.
suit = validate_suitability_site_a()
check(
    "Suitability",
    bool(suit["match"]),
    f"computed={suit['computed_suitability']}, seed={suit['seed_suitability']}",
)

if failures:
    print(f"\n{len(failures)} model validation(s) FAILED: {', '.join(failures)}")
    sys.exit(1)

print("\nAll model validations PASSED")
