"""Generates data/evaluations/golden.json (25 cases). Deterministic. Run after generate_dataset.py."""

from __future__ import annotations

import json
from pathlib import Path

from generate_dataset import CAUSES, EQUIPMENT

ROOT = Path(__file__).resolve().parent.parent
EQ_BY_TYPE = {}
for e in EQUIPMENT:
    EQ_BY_TYPE.setdefault(e["type"], []).append(e)

TECH_A = {"user": "ana@example.com", "role": "technician", "plants": ["PLANT-A"]}
ADMIN = {"user": "root@example.com", "role": "administrator", "plants": ["*"]}


def req(i: int, eq: dict, symptoms: list[str], message: str = "Diagnostica la falla y recomienda verificaciones") -> dict:
    return {"incident_id": f"INC-G{i:02d}", "equipment_id": eq["equipment_id"], "plant_id": eq["plant_id"], "symptoms": symptoms, "message": message}


def main() -> None:
    cases: list[dict] = []
    n = 0
    # 10 positive: canonical symptoms of a (type, cause) pair on equipment of that type -> that cause must rank first
    positives = [("pump", "bearing_wear"), ("pump", "cavitation"), ("pump", "seal_leak"), ("pump", "impeller_damage"),
                 ("pump", "lubrication_failure"), ("compressor", "valve_failure"), ("compressor", "surge"),
                 ("compressor", "oil_contamination"), ("motor", "winding_overheat"), ("motor", "phase_imbalance")]
    for etype, cause in positives:
        n += 1
        eq = EQ_BY_TYPE[etype][0]
        cases.append({"case_id": f"G-{n:02d}", "category": "positive", "principal": ADMIN if eq["plant_id"] != "PLANT-A" else TECH_A,
                      "request": req(n, eq, CAUSES[(etype, cause)][0]), "expect": {"http": 200, "top_cause": cause, "min_hypotheses": 1, "cites_equipment_type": etype}})
    # 6 ambiguous: partial symptom sets shared by several causes -> several hypotheses, no overconfidence
    amb = [["high_vibration", "high_bearing_temperature"], ["high_vibration", "low_discharge_pressure"], ["high_bearing_temperature", "noise_grinding"],
           ["low_discharge_pressure", "high_vibration", "flow_fluctuation"], ["high_vibration"], ["high_bearing_temperature"]]
    for s in amb:
        n += 1
        cases.append({"case_id": f"G-{n:02d}", "category": "ambiguous", "principal": TECH_A, "request": req(n, EQ_BY_TYPE["pump"][0], s),
                      "expect": {"http": 200, "min_hypotheses": 2, "max_top_confidence": 0.9}})
    # 5 no evidence: must ask for more data, never conclude
    for s in (["unknown_weird_symptom"], ["strange_smell"], ["display_blank"], ["intermittent_signal_loss"], []):
        n += 1
        cases.append({"case_id": f"G-{n:02d}", "category": "no_evidence", "principal": TECH_A, "request": req(n, EQ_BY_TYPE["pump"][0], s),
                      "expect": {"http": 200, "status": "needs_more_data", "max_hypotheses": 0, "requires_checks": True}})
    # 4 authorization denied
    for eq, who in ((EQ_BY_TYPE["pump"][2], TECH_A), (EQ_BY_TYPE["motor"][0], TECH_A),
                    (EQ_BY_TYPE["pump"][0], {"user": "eva@example.com", "role": "technician", "plants": ["PLANT-B"]}),
                    (EQ_BY_TYPE["pump"][0], {"user": "v@example.com", "role": "viewer", "plants": ["PLANT-A"]})):
        n += 1
        cases.append({"case_id": f"G-{n:02d}", "category": "authorization_denied", "principal": who,
                      "request": req(n, eq, ["high_vibration"]), "expect": {"http": 403}})
    assert len(cases) == 25
    out = ROOT / "data/evaluations/golden.json"
    out.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(cases)} golden cases -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
