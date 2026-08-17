#!/usr/bin/env python3
"""Generate synthetic CMMS corrective work order history for U400 deethanizer."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


RNG = random.Random(501400)
START_DATE = date(2021, 6, 1)
END_DATE = date(2026, 5, 31)
ROW_COUNT = 1250


EQUIPMENT = [
    ("T-501", "deethanizer column", "column", 0.075),
    ("E-501", "deethanizer reboiler", "reboiler", 0.095),
    ("E-502", "deethanizer overhead condenser", "condenser", 0.095),
    ("V-501", "deethanizer reflux drum", "vessel", 0.065),
    ("P-501A", "reflux pump A", "pump", 0.090),
    ("P-501B", "reflux pump B", "pump", 0.075),
    ("P-502A", "bottoms pump A", "pump", 0.070),
    ("P-502B", "bottoms pump B", "pump", 0.055),
    ("E-503", "feed bottoms exchanger", "exchanger", 0.070),
    ("FV-501", "feed flow control valve", "control_valve", 0.055),
    ("FV-502", "reflux flow control valve", "control_valve", 0.065),
    ("PV-501", "column pressure control valve", "control_valve", 0.055),
    ("LV-501", "reflux drum level valve", "control_valve", 0.045),
    ("LV-502", "bottoms level valve", "control_valve", 0.045),
    ("TV-501", "reboiler hot medium valve", "control_valve", 0.060),
    ("TV-502", "condenser cooling valve", "control_valve", 0.055),
    ("XV-501", "feed shutdown valve", "shutdown_valve", 0.030),
    ("PT-501", "column overhead pressure tx", "instrument", 0.032),
    ("DPT-501", "column diff pressure tx", "instrument", 0.030),
    ("LT-501", "reflux drum level tx", "instrument", 0.035),
    ("LT-502", "column bottom level tx", "instrument", 0.035),
    ("FT-501", "feed flow transmitter", "instrument", 0.032),
    ("FT-502", "reflux flow transmitter", "instrument", 0.034),
    ("TT-501B", "sensitive tray temperature tx", "instrument", 0.034),
    ("TT-503", "reboiler outlet temperature tx", "instrument", 0.026),
    ("AIT-501", "overhead C2 analyzer", "analyzer", 0.035),
    ("AIT-502", "bottoms C3+ analyzer", "analyzer", 0.026),
    ("PSV-501A", "column relief valve A", "relief", 0.020),
    ("PSV-501B", "column relief valve B", "relief", 0.016),
    ("PSV-502", "reflux drum relief valve", "relief", 0.014),
]


SCENARIOS = {
    "feed_flow_step": {
        "symptoms": ["feed jump", "column dp high", "fic hunting", "c2 recov down", "lvl swing"],
        "systems": ["FV-501", "FT-501", "E-503", "T-501"],
    },
    "feed_temperature_ramp": {
        "symptoms": ["feed temp high", "tray temp drift", "rb duty up", "ovhd press moving", "spec off"],
        "systems": ["E-503", "TT-501B", "E-501", "TV-501"],
    },
    "feed_composition_shift": {
        "symptoms": ["c3 in feed hi", "anlyzr off", "btm heavy", "ovhd c3 slip", "quality bad"],
        "systems": ["AIT-501", "AIT-502", "T-501", "E-503"],
    },
    "reboiler_duty_loss": {
        "symptoms": ["low heat", "c2 in btm", "tray temp low", "steam/hm valve no resp", "rb circ cold"],
        "systems": ["E-501", "TV-501", "TT-503", "TT-501B"],
    },
    "condenser_fouling": {
        "symptoms": ["high ovhd press", "cw dt low", "cond not pullng", "pic wide open", "drum temp hi"],
        "systems": ["E-502", "TV-502", "PV-501", "PT-501"],
    },
    "reflux_pump_degradation": {
        "symptoms": ["low reflux", "pump vib", "seal weep", "disch press low", "min flow hot"],
        "systems": ["P-501A", "P-501B", "FV-502", "FT-502"],
    },
    "valve_stiction": {
        "symptoms": ["valve sticking", "op jumps", "loop cycling", "air leak", "position bad"],
        "systems": ["FV-501", "FV-502", "PV-501", "LV-501", "LV-502", "TV-501", "TV-502"],
    },
    "pressure_control_fault": {
        "symptoms": ["pic unstable", "press spike", "pshh close call", "pv not movng", "flare valve checked"],
        "systems": ["PV-501", "PT-501", "PSV-501A", "PSV-501B", "E-502"],
    },
    "normal_wear": {
        "symptoms": ["leak", "noise", "bad reading", "plugged impulse", "loose term", "pm found defect"],
        "systems": [],
    },
}


FAILURES = {
    "pump": [
        ("seal leak", "MECH_SEAL", "SEAL", "seal face worn / dry run signs"),
        ("bearing hot", "BRG", "WEAR", "brg rough, lube dark"),
        ("low disch press", "HYD_LOSS", "FOUL", "strainer dirty or impeller wear"),
        ("motor trip", "MOTOR", "ELEC", "overload trip after upset"),
        ("vib high", "VIB", "ALIGN", "coupling align or cavitation"),
    ],
    "exchanger": [
        ("tube fouling", "FOULING", "PROCESS", "duty low, delta t poor"),
        ("gasket weep", "LEAK", "GASKET", "flange sweating"),
        ("plugged pass", "PLUG", "FOUL", "flow restricted"),
        ("temp approach bad", "PERF", "FOUL", "heat transfer loss"),
    ],
    "reboiler": [
        ("low duty", "DUTY_LOSS", "UTILITY", "hm valve/strainer issue"),
        ("rb leak", "LEAK", "GASKET", "channel flange weep"),
        ("fouled bundle", "FOULING", "PROCESS", "bottoms side dirty"),
        ("circ poor", "NO_FLOW", "PLUG", "blocked inlet screen"),
    ],
    "condenser": [
        ("cw fouling", "FOULING", "UTILITY", "cw side scaled"),
        ("high press", "PERF", "FOUL", "condensing duty poor"),
        ("tube leak sus", "LEAK", "TUBE", "hydrotest reqd"),
        ("tv no travel", "VALVE", "STICK", "cooling valve stuck"),
    ],
    "control_valve": [
        ("stiction", "STICK", "PACKING", "stem sticky and pos err"),
        ("air leak", "AIR_LEAK", "TUBING", "positioner supply drop"),
        ("not stroking", "NO_TRAVEL", "ACT", "actuator weak"),
        ("passing", "LEAK_BY", "SEAT", "seat leak by"),
        ("hunting loop", "CTRL_OSC", "TUNE", "bad response after upset"),
    ],
    "shutdown_valve": [
        ("partial stroke fail", "PST_FAIL", "ACT", "slow close/open"),
        ("solenoid fault", "SOL", "ELEC", "coil hot/no shift"),
        ("limit sw bad", "ZSO_ZSC", "ELEC", "feedback mismatch"),
    ],
    "instrument": [
        ("bad reading", "DRIFT", "CAL", "needs calib"),
        ("impulse plugged", "PLUG", "PROCESS", "tap/line dirty"),
        ("loose wire", "SIGNAL", "ELEC", "term loose"),
        ("no signal", "NO_SIGNAL", "ELEC", "24v or card issue"),
        ("range err", "SPAN", "CAL", "span shifted"),
    ],
    "analyzer": [
        ("sample plugged", "PLUG", "SAMPLE", "fast loop low flow"),
        ("anlyzr drift", "DRIFT", "CAL_GAS", "cal gas failed"),
        ("condensate in sample", "LIQ_CARRY", "SAMPLE", "knockout pot full"),
        ("bad gc cycle", "NO_ANALYSIS", "ELEC", "cycle abort"),
    ],
    "relief": [
        ("seat passing", "LEAK_BY", "SEAT", "tail pipe warm"),
        ("due to lift chk", "LIFT_EVENT", "PROCESS", "after pressure excursion"),
        ("car seal broken", "CSO", "HUMAN", "seal missing found"),
    ],
    "column": [
        ("dp high", "DP_HIGH", "FOAM", "trays loading or foaming"),
        ("tray temp bad", "TEMP_DEV", "PROCESS", "profile not normal"),
        ("weeping flange", "LEAK", "GASKET", "manway/flange seep"),
        ("level unstable", "LVL_SWING", "CTRL", "sump level swing"),
    ],
    "vessel": [
        ("level swing", "LVL_SWING", "CTRL", "lt/lic problem"),
        ("pressure erratic", "PRESS_SWING", "CTRL", "pv/pic issue"),
        ("boot drain leak", "LEAK", "VALVE", "closed drain valve passing"),
    ],
}


CRAFTS = ["MECH", "INST", "E&I", "OPS+MECH", "OPS+INST", "ROT", "VALVE", "ANLYZR"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
STATUSES = ["TECO", "CLSD", "COMP"]
SHIFTS = ["A shift", "B shift", "C shift", "night", "days"]
SHORTHANDS = ["pls chk", "asap", "temp fix", "ops req", "bad", "noisy", "chk & revert", "again", "after upset"]


def weighted_equipment(scenario: str) -> tuple[str, str, str]:
    forced = SCENARIOS[scenario]["systems"]
    if forced and RNG.random() < 0.68:
        tag = RNG.choice(forced)
        for item in EQUIPMENT:
            if item[0] == tag:
                return item[:3]
    tags = [item[:3] for item in EQUIPMENT]
    weights = [item[3] for item in EQUIPMENT]
    return RNG.choices(tags, weights=weights, k=1)[0]


def random_date(index: int) -> date:
    total_days = (END_DATE - START_DATE).days
    base = START_DATE + timedelta(days=int(index * total_days / ROW_COUNT))
    return min(END_DATE, base + timedelta(days=RNG.randint(0, 5)))


def typo(text: str) -> str:
    replacements = [
        ("the ", "teh "),
        ("valve", "vavle"),
        ("pressure", "press"),
        ("temperature", "temp"),
        ("transmitter", "tx"),
        ("reboiler", "rebiler"),
        ("condenser", "condnsr"),
        ("column", "colmn"),
        ("reflux", "rflx"),
        ("because", "becoz"),
        ("checked", "chekd"),
        ("control", "ctrl"),
        ("maintenance", "maint"),
        ("running", "runing"),
        ("found", "foud"),
    ]
    for old, new in RNG.sample(replacements, RNG.randint(1, 4)):
        text = text.replace(old, new)
    return text


def short_text(tag: str, failure: str, scenario: str) -> str:
    symptom = RNG.choice(SCENARIOS[scenario]["symptoms"])
    patterns = [
        f"{tag} {failure} {RNG.choice(SHORTHANDS)}",
        f"{tag} {symptom}, {failure}",
        f"chk {tag} - {failure} frm ops",
        f"{tag} not ok after {scenario.replace('_', ' ')}",
        f"{tag} {failure} again, prod upset",
    ]
    return typo(RNG.choice(patterns))[:80]


def long_text(tag: str, desc: str, failure: str, cause_note: str, scenario: str) -> str:
    symptom = RNG.choice(SCENARIOS[scenario]["symptoms"])
    shift = RNG.choice(SHIFTS)
    action = RNG.choice(
        [
            "cleaned and put back online",
            "tightened fittings, leak test ok",
            "stroke tested, response better",
            "changed gasket and boxed up",
            "calibrated, loop checked with CCR",
            "swapped to standby and repaired",
            "flushed impulse/sample line",
            "reset trip and monitored for 2 hrs",
            "replaced positioner tubing and retuned small",
            "opened strainer, cleaned black sludge",
        ]
    )
    result = RNG.choice(
        [
            "unit stable now",
            "ops says ok for now",
            "need watch next feed swing",
            "temp repair only, plan shutdown job",
            "readng close to dcs after job",
            "no leak at handover",
            "still little hunting but acceptable",
        ]
    )
    sentences = [
        f"{shift} called for {tag} {desc}, {symptom} seen during {scenario.replace('_', ' ')}.",
        f"Foud {failure}; {cause_note}.",
        f"{action}.",
        f"{result}.",
        f"notif made by ops, maint attended same shift.",
    ]
    if RNG.random() < 0.45:
        sentences.insert(2, RNG.choice([
            "Could not get permit first time waiting area gas test.",
            "No spare in store at first, used refurb one from shop.",
            "Line was hot so job done slow and with ops standing by.",
            "Tag plate dirty, confirmd by line up with panel.",
            "History shows same complain last mnth.",
        ]))
    return typo(" ".join(sentences))


def scenario_for_index(index: int) -> str:
    planned = [
        ("feed_flow_step", 0.12),
        ("feed_temperature_ramp", 0.10),
        ("feed_composition_shift", 0.10),
        ("reboiler_duty_loss", 0.13),
        ("condenser_fouling", 0.13),
        ("reflux_pump_degradation", 0.14),
        ("valve_stiction", 0.15),
        ("pressure_control_fault", 0.08),
        ("normal_wear", 0.05),
    ]
    names = [item[0] for item in planned]
    weights = [item[1] for item in planned]
    return RNG.choices(names, weights=weights, k=1)[0]


def make_rows() -> list[dict[str, object]]:
    rows = []
    for idx in range(ROW_COUNT):
        scenario = scenario_for_index(idx)
        tag, desc, kind = weighted_equipment(scenario)
        failure, failure_code, cause_code, cause_note = RNG.choice(FAILURES[kind])
        notif_date = random_date(idx)
        order_date = notif_date + timedelta(days=RNG.choice([0, 0, 0, 1, 1, 2]))
        completion_date = order_date + timedelta(days=RNG.choices([0, 1, 2, 3, 5, 7, 14], [25, 34, 18, 10, 7, 4, 2])[0])
        priority = RNG.choices(PRIORITIES, [0.07, 0.29, 0.49, 0.15], k=1)[0]
        outage = "Y" if priority in {"P1", "P2"} and RNG.random() < 0.28 else "N"
        craft = RNG.choice(CRAFTS if kind not in {"instrument", "analyzer"} else ["INST", "E&I", "ANLYZR", "OPS+INST"])
        labor = round(RNG.uniform(1.0, 18.0) + (6.0 if outage == "Y" else 0.0), 1)
        material = round(RNG.uniform(0, 9500) * (1.8 if kind in {"pump", "exchanger", "reboiler", "condenser"} else 0.7), 2)

        rows.append(
            {
                "notification_no": f"10{idx + 450001:06d}",
                "work_order_no": f"40{idx + 870001:06d}",
                "notification_date": notif_date.isoformat(),
                "order_created_date": order_date.isoformat(),
                "completion_date": min(completion_date, END_DATE).isoformat(),
                "functional_location": "U400-DEETHANIZER-500",
                "equipment_tag": tag,
                "equipment_description": desc,
                "equipment_class": kind,
                "priority": priority,
                "status": RNG.choice(STATUSES),
                "craft": craft,
                "process_upset": scenario,
                "failure_mode": failure,
                "failure_code": failure_code,
                "cause_code": cause_code,
                "outage_required": outage,
                "labor_hours": labor,
                "material_cost_usd": material,
                "notification_short_text": short_text(tag, failure, scenario),
                "notification_long_text": long_text(tag, desc, failure, cause_note, scenario),
            }
        )
    return rows


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "deethanizer_U400_cmms_corrective_wo_history_2021-06_to_2026-05.csv"
    rows = make_rows()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(output)
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
