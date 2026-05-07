from __future__ import annotations

from pathlib import Path

import ezdxf

from tools.pid.pidlib.cad_primitives import (
    DrawContext,
    draw_branch,
    draw_equipment_box,
    draw_flow_arrow,
    draw_header,
    draw_instrument_bubble,
    draw_line_jump,
    draw_line_label,
    draw_notes_block,
    draw_offpage_connector,
    draw_pipe,
    draw_signal_line,
    draw_title_block,
    draw_valve_on_line,
    draw_vessel,
)
from tools.pid.pidlib.drafting_standard import DEFAULT_STANDARD, style_from_name
from tools.pid.pidlib.drier_package_checklist import engineering_completeness_report
from tools.pid.pidlib.instrument_zones import build_drier_instrument_zones, place_instrument_stack
from tools.pid.pidlib.layers import setup_layers
from tools.pid.pidlib.validation import PIDValidationError, validate_visual_audit
from tools.pid.pidlib.visual_validation import draw_qa_overlay, run_visual_qa


REQUIRED_XV = [
    "XV-30101A",
    "XV-30102A",
    "XV-30103A",
    "XV-30104A",
    "XV-30105A",
    "XV-30106A",
    "XV-30101B",
    "XV-30102B",
    "XV-30103B",
    "XV-30104B",
    "XV-30105B",
    "XV-30106B",
]

REQUIRED_EQUIPMENT = ["DR-301A", "DR-301B", "H-301", "E-301", "V-301", "F-301"]

REQUIRED_LINES = [
    "12-PG-301001-A1A-HC",
    "12-PG-301002-A1A-HC",
    "4-RG-301101-A1A-HC",
    "4-RG-301107-A1A-HC",
    "3-FL-301201-A1A-HC",
    "2-CD-301301-A1A-HC",
    "2-SV-301401-A1A-HC",
    "2-PG-301021-A1A-HC",
    "12-PG-301090-A1A-HC",
]


def draw_dual_drier_template(output: Path, *, validate: bool = True, style_name: str = "final", qa_overlay: bool = False) -> None:
    doc = ezdxf.new("R2010")
    standard = DEFAULT_STANDARD
    style = style_from_name(style_name)
    setup_layers(doc, style)
    _ensure_linetypes(doc)
    msp = doc.modelspace()
    ctx = DrawContext(msp, standard=standard, style=style)
    zones = build_drier_instrument_zones(standard)
    feedback_slots = _build_feedback_slots(zones)

    draw_border(ctx)
    draw_title_block(
        ctx,
        project="DUAL MOLECULAR SIEVE DRIER PACKAGE",
        drawing_no="U300-PID-301",
        rev="A",
        unit="U-300",
        service="PROCESS GAS DEHYDRATION",
        status="FOR STUDY",
    )
    _draw_heading(ctx)
    ports = _draw_beds(ctx, zones)
    _draw_process_gas(ctx, ports, feedback_slots)
    _draw_regen_system(ctx, ports, feedback_slots)
    _draw_safety_and_utility_headers(ctx, ports, feedback_slots)
    _draw_analyzer_system(ctx)
    _draw_sequence_table(ctx)
    _draw_legend(ctx)
    draw_notes_block(
        ctx,
        [
            "All shutdown valves are remote actuated with ZSO/ZSC feedback to DCS.",
            "DR-301A/B protected by PSV per relief study; PSV detail shown on U300-PID-302.",
            "Manual bypass valve XV-30190 is normally closed and car-sealed closed.",
            "Minimum 15 mm drafting separation maintained between parallel package headers.",
            "Instrument signals are electric unless otherwise noted.",
        ],
        x=55,
        y=128,
    )

    if validate:
        legacy_errors = validate_visual_audit(
            ctx.audit,
            required_line_labels=REQUIRED_LINES,
            required_equipment=REQUIRED_EQUIPMENT,
            required_valves=REQUIRED_XV,
            required_destinations=["DR-301A.VENT", "DR-301A.DRAIN", "DR-301B.VENT", "DR-301B.DRAIN", "ANALYZER.VENT", "ANALYZER.DRAIN"],
        )
        visual_report = run_visual_qa(
            ctx.registry,
            required_valves=REQUIRED_XV,
            required_equipment=REQUIRED_EQUIPMENT,
            required_line_labels=REQUIRED_LINES,
            standard=standard,
        )
        checklist_report, _, _ = engineering_completeness_report(ctx.registry)
        print(visual_report.format())
        print(checklist_report)
        hard_failures = visual_report.failures
        if hard_failures:
            raise PIDValidationError("Template QA failed:\n- " + "\n- ".join(hard_failures))

    if qa_overlay:
        draw_qa_overlay(msp, ctx.registry)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)


def draw_border(ctx: DrawContext) -> None:
    s = ctx.standard
    ctx.msp.add_lwpolyline([(s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.border_margin), (s.sheet_w - s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.sheet_h - s.border_margin), (s.border_margin, s.border_margin)], dxfattribs={"layer": "BORDER", "lineweight": int(s.lw_border * 100)})
    ctx.msp.add_lwpolyline([(s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.inner_border_margin), (s.sheet_w - s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.sheet_h - s.inner_border_margin), (s.inner_border_margin, s.inner_border_margin)], dxfattribs={"layer": "BORDER", "lineweight": int(s.lw_border * 100)})


def _draw_heading(ctx: DrawContext) -> None:
    ctx.msp.add_text("PIPING AND INSTRUMENTATION DIAGRAM", dxfattribs={"height": ctx.standard.title_text_h, "layer": "TEXT"}).set_placement((55, 792))
    ctx.msp.add_text("DUAL-BED MOLECULAR SIEVE PROCESS GAS DRIER", dxfattribs={"height": ctx.standard.subtitle_text_h, "layer": "TEXT"}).set_placement((55, 777))


def _draw_beds(ctx: DrawContext, zones) -> dict[str, dict[str, tuple[float, float]]]:
    ports_a = draw_vessel(ctx, "DR-301A", 430, 575, height=122, width=44)
    ports_b = draw_vessel(ctx, "DR-301B", 430, 415, height=122, width=44)
    _bed_instruments(ctx, "A", 430, 575, zones["BED_A_LEFT"])
    _bed_instruments(ctx, "B", 430, 415, zones["BED_B_LEFT"])
    return {"DR-301A": ports_a, "DR-301B": ports_b}


def _bed_instruments(ctx: DrawContext, suffix: str, x: float, y: float, zone) -> None:
    placements = place_instrument_stack(zone, [f"PDIT-30101{suffix}", f"PIT-30102{suffix}", f"TIT-30103{suffix}"])
    taps = {
        f"PDIT-30101{suffix}": (x - 22, y + 42),
        f"PIT-30102{suffix}": (x - 22, y),
        f"TIT-30103{suffix}": (x - 22, y - 42),
    }
    for tag, (ix, iy) in placements.items():
        draw_instrument_bubble(ctx, tag, ix, iy)
        draw_signal_line(ctx, [(ix + ctx.standard.instrument_bubble_radius, iy), taps[tag]])
    ctx.msp.add_text(f"PSV/protection note {suffix}", dxfattribs={"height": ctx.standard.note_text_h, "layer": "TEXT"}).set_placement((x - 78, y - 76))
    ctx.registry.mark("document", f"PSV_NOTE_{suffix}")


def _draw_process_gas(ctx: DrawContext, ports: dict[str, dict[str, tuple[float, float]]], feedback_slots: dict[str, tuple[float, float]]) -> None:
    wet = "12-PG-301001-A1A-HC"
    dry = "12-PG-301002-A1A-HC"
    bypass = "12-PG-301090-A1A-HC"
    draw_offpage_connector(ctx, "OFFPAGE_WET_GAS", 55, 710, "in", "U300-PFD-001", "PROCESS")
    draw_header(ctx, [(77, 710), (975, 710)], wet, "wet gas inlet header", "PROCESS")
    draw_line_label(ctx, wet, 132, 722)
    draw_offpage_connector(ctx, "OFFPAGE_DRY_GAS", 1108, 675, "out", "U300-PFD-001", "PROCESS")
    draw_header(ctx, [(520, 675), (1086, 675)], dry, "dry gas outlet header", "PROCESS")
    draw_line_label(ctx, dry, 815, 687)

    for suffix, bed, lane_y in [("A", "DR-301A", 575), ("B", "DR-301B", 415)]:
        branch_x = 292 if suffix == "A" else 332
        inlet_valve = f"XV-30101{suffix}"
        outlet_valve = f"XV-30102{suffix}"
        draw_branch(ctx, [(branch_x, 710), (branch_x, lane_y + 61), (430, lane_y + 61)], wet, f"wet gas to bed {suffix}", "PROCESS")
        draw_valve_on_line(ctx, inlet_valve, branch_x, lane_y + 61, "V", "XV", "FC")
        draw_xv_feedback(ctx, inlet_valve, (branch_x, lane_y + 61), feedback_slots[inlet_valve])
        draw_flow_arrow(ctx, 370, lane_y + 61, "RIGHT")
        draw_branch(ctx, [(430, lane_y - 61), (560, lane_y - 61), (560, 675)], dry, f"dry gas from bed {suffix}", "PROCESS")
        draw_valve_on_line(ctx, outlet_valve, 500, lane_y - 61, "H", "XV", "FC")
        draw_xv_feedback(ctx, outlet_valve, (500, lane_y - 61), feedback_slots[outlet_valve])
        draw_flow_arrow(ctx, 557, 640 if suffix == "A" else 510, "UP")

    draw_equipment_box(ctx, "F-301", 720, 675, 48, 28, "DUST FILTER")
    draw_pipe(ctx, [(744, 675), (1086, 675)], dry, "dry gas after dust filter", "PROCESS")
    draw_flow_arrow(ctx, 925, 675, "RIGHT")

    draw_branch(ctx, [(155, 710), (155, 735), (930, 735), (930, 675)], bypass, "manual package bypass", "PROCESS")
    draw_line_jump(ctx, 292, 735, "H")
    draw_line_jump(ctx, 332, 735, "H")
    draw_valve_on_line(ctx, "XV-30190", 560, 735, "H", "manual", "NC/CSC")
    draw_line_label(ctx, bypass, 607, 746)


def _draw_regen_system(ctx: DrawContext, ports: dict[str, dict[str, tuple[float, float]]], feedback_slots: dict[str, tuple[float, float]]) -> None:
    supply = "4-RG-301101-A1A-HC"
    ret = "4-RG-301107-A1A-HC"
    draw_offpage_connector(ctx, "OFFPAGE_REGEN_GAS", 55, 285, "in", "U300-UTL-010", "REGEN")
    draw_header(ctx, [(77, 285), (220, 285)], supply, "regen gas supply", "REGEN")
    draw_instrument_bubble(ctx, "FIC-30110", 160, 315, "dcs")
    draw_signal_line(ctx, [(160, 306), (160, 285)])
    draw_equipment_box(ctx, "H-301", 260, 285, 58, 36, "REGEN HEATER")
    draw_instrument_bubble(ctx, "TIC-30110", 285, 335, "dcs")
    draw_instrument_bubble(ctx, "TAHH-30110", 355, 335, "field")
    draw_signal_line(ctx, [(285, 326), (285, 303)])
    draw_signal_line(ctx, [(355, 326), (315, 285)])
    draw_line_label(ctx, supply, 90, 298)

    draw_header(ctx, [(289, 285), (620, 285), (620, 545)], supply, "hot regen gas manifold", "REGEN")
    draw_flow_arrow(ctx, 620, 430, "UP", "REGEN")
    for suffix, y in [("A", 553), ("B", 393)]:
        valve = f"XV-30103{suffix}"
        draw_branch(ctx, [(620, y), (452, y)], supply, f"regen inlet to bed {suffix}", "REGEN")
        draw_valve_on_line(ctx, valve, 570, y, "H", "XV", "FC", "REGEN")
        draw_xv_feedback(ctx, valve, (570, y), feedback_slots[valve])
        draw_flow_arrow(ctx, 500, y, "LEFT", "REGEN")

    for suffix, y in [("A", 597), ("B", 437)]:
        valve = f"XV-30104{suffix}"
        draw_branch(ctx, [(452, y), (670, y), (670, 245)], ret, f"regen outlet from bed {suffix}", "REGEN")
        draw_valve_on_line(ctx, valve, 560, y, "H", "XV", "FC", "REGEN")
        draw_xv_feedback(ctx, valve, (560, y), feedback_slots[valve])
        draw_flow_arrow(ctx, 655, y, "RIGHT", "REGEN")

    draw_equipment_box(ctx, "E-301", 725, 245, 58, 32, "REGEN COOLER")
    draw_equipment_box(ctx, "V-301", 835, 245, 42, 58, "KO DRUM")
    draw_header(ctx, [(670, 245), (696, 245), (754, 245), (814, 245), (1066, 245)], ret, "regen return", "REGEN")
    draw_flow_arrow(ctx, 780, 245, "RIGHT", "REGEN")
    draw_line_label(ctx, ret, 760, 258)
    draw_offpage_connector(ctx, "OFFPAGE_REGEN_RETURN", 1088, 245, "out", "U300-FG-020", "REGEN")


def _draw_safety_and_utility_headers(ctx: DrawContext, ports: dict[str, dict[str, tuple[float, float]]], feedback_slots: dict[str, tuple[float, float]]) -> None:
    flare = "3-FL-301201-A1A-HC"
    drain = "2-CD-301301-A1A-HC"
    vent = "2-SV-301401-A1A-HC"
    press = "2-PG-301021-A1A-HC"

    draw_offpage_connector(ctx, "OFFPAGE_FLARE", 1088, 198, "out", "U300-FL-001", "FLARE_VENT")
    draw_header(ctx, [(150, 198), (1066, 198)], flare, "flare header", "FLARE_VENT")
    draw_line_label(ctx, flare, 180, 210)
    draw_offpage_connector(ctx, "OFFPAGE_CLOSED_DRAIN", 1088, 163, "out", "U300-CD-001", "DRAIN")
    draw_header(ctx, [(150, 163), (1066, 163)], drain, "closed drain header", "DRAIN")
    draw_line_label(ctx, drain, 180, 175)
    draw_offpage_connector(ctx, "OFFPAGE_SAFE_VENT", 1088, 128, "out", "U300-VT-001", "FLARE_VENT")
    draw_header(ctx, [(150, 128), (1066, 128)], vent, "safe vent header", "FLARE_VENT")
    draw_line_label(ctx, vent, 180, 140)

    for suffix, bed, y in [("A", "DR-301A", 575), ("B", "DR-301B", 415)]:
        dep_x = 365 if suffix == "A" else 385
        vent_x = 335 if suffix == "A" else 355
        drain_x = 465 if suffix == "A" else 485
        draw_branch(ctx, [(408, y + 52), (dep_x, y + 52), (dep_x, 198)], flare, f"bed {suffix} depressurization to flare", "FLARE_VENT")
        draw_valve_on_line(ctx, f"XV-30105{suffix}", dep_x, y + 20, "V", "XV", "FO", "FLARE_VENT")
        draw_xv_feedback(ctx, f"XV-30105{suffix}", (dep_x, y + 20), feedback_slots[f"XV-30105{suffix}"])
        ctx.audit.destinations[f"{bed}.VENT"] = "OFFPAGE_SAFE_VENT"
        ctx.audit.destinations[f"{bed}.DRAIN"] = "OFFPAGE_CLOSED_DRAIN"
        ctx.registry.mark("destination", f"{bed}.VENT")
        ctx.registry.mark("destination", f"{bed}.DRAIN")
        draw_branch(ctx, [(420, y + 66), (vent_x, y + 66), (vent_x, 128)], vent, f"bed {suffix} vent to safe vent", "FLARE_VENT")
        draw_branch(ctx, [(430, y - 66), (drain_x, y - 66), (drain_x, 163)], drain, f"bed {suffix} drain to closed drain", "DRAIN")
        draw_flow_arrow(ctx, dep_x, 230, "DOWN", "FLARE_VENT")
        draw_flow_arrow(ctx, drain_x, 185, "DOWN", "DRAIN")
        press_x = 790 if suffix == "A" else 820
        draw_branch(ctx, [(press_x, 675), (press_x, y + 8), (452, y + 8)], press, f"pressurization/equalization bed {suffix}", "PROCESS")
        draw_valve_on_line(ctx, f"XV-30106{suffix}", press_x, y + 8, "V", "XV", "FC", "PROCESS")
        draw_xv_feedback(ctx, f"XV-30106{suffix}", (press_x, y + 8), feedback_slots[f"XV-30106{suffix}"])

    draw_line_label(ctx, press, 835, 615)


def _draw_analyzer_system(ctx: DrawContext) -> None:
    sample = "1-SM-301501-A1A-HC"
    draw_branch(ctx, [(890, 675), (890, 620), (940, 620)], sample, "moisture analyzer sample", "INSTRUMENT")
    draw_equipment_box(ctx, "SC-30101", 975, 620, 52, 28, "SAMPLE COND.")
    draw_instrument_bubble(ctx, "AIT-30101", 1055, 620, "field")
    draw_instrument_bubble(ctx, "AIC-30101", 1055, 585, "dcs")
    draw_signal_line(ctx, [(1055, 611), (1055, 594)])
    draw_branch(ctx, [(1000, 606), (1000, 128)], "2-SV-301401-A1A-HC", "analyzer vent", "FLARE_VENT")
    draw_branch(ctx, [(980, 606), (980, 163)], "2-CD-301301-A1A-HC", "analyzer drain", "DRAIN")
    draw_flow_arrow(ctx, 890, 645, "DOWN", "INSTRUMENT")
    ctx.audit.destinations["ANALYZER.VENT"] = "OFFPAGE_SAFE_VENT"
    ctx.audit.destinations["ANALYZER.DRAIN"] = "OFFPAGE_CLOSED_DRAIN"
    ctx.registry.mark("destination", "ANALYZER.VENT")
    ctx.registry.mark("destination", "ANALYZER.DRAIN")


def draw_xv_feedback(ctx: DrawContext, tag: str, source: tuple[float, float], slot: tuple[float, float]) -> None:
    x, y = slot
    draw_instrument_bubble(ctx, f"ZSO-{tag[-6:]}", x, y + 9, "field")
    draw_instrument_bubble(ctx, f"ZSC-{tag[-6:]}", x, y - 9, "field")
    draw_signal_line(ctx, [source, (x - 18, y - 2), (x - ctx.standard.instrument_bubble_radius, y - 2)], "electric")
    ctx.audit.xv_feedback.add(tag)
    ctx.registry.mark("instrument", f"ZSO-{tag[-6:]}")
    ctx.registry.mark("instrument", f"ZSC-{tag[-6:]}")


def _build_feedback_slots(zones) -> dict[str, tuple[float, float]]:
    slots: dict[str, tuple[float, float]] = {}
    for suffix, zone_name in [("A", "BED_A_RIGHT"), ("B", "BED_B_RIGHT")]:
        tags = [f"XV-3010{idx}{suffix}" for idx in range(1, 7)]
        placements = place_instrument_stack(zones[zone_name], tags)
        slots.update(placements)
    return slots


def _draw_sequence_table(ctx: DrawContext) -> None:
    x, y = 505, 128
    ctx.msp.add_lwpolyline([(x, y), (x + 320, y), (x + 320, y - 90), (x, y - 90), (x, y)], dxfattribs={"layer": "TABLE"})
    ctx.msp.add_text("DRIER SEQUENCE TABLE", dxfattribs={"height": 3.2, "layer": "TEXT"}).set_placement((x + 6, y - 12))
    rows = [
        ("STEP", "BED A", "BED B", "KEY XV STATE"),
        ("1 ADSORB A", "ADSORB", "REGEN", "30101A/30102A OPEN"),
        ("2 HEAT B", "ADSORB", "HEAT", "30103B/30104B OPEN"),
        ("3 COOL B", "ADSORB", "COOL", "30103B/30104B OPEN"),
        ("4 SWITCH", "DEPRESS", "PRESS", "30105A / 30106B"),
    ]
    for idx, row in enumerate(rows):
        yy = y - 25 - idx * 12
        ctx.msp.add_text(row[0], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement((x + 6, yy))
        ctx.msp.add_text(row[1], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement((x + 72, yy))
        ctx.msp.add_text(row[2], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement((x + 132, yy))
        ctx.msp.add_text(row[3], dxfattribs={"height": 2.3, "layer": "TEXT"}).set_placement((x + 190, yy))
    ctx.registry.mark("document", "SEQUENCE_TABLE")


def _draw_legend(ctx: DrawContext) -> None:
    x, y = 55, 760
    ctx.msp.add_text("LEGEND", dxfattribs={"height": 3.2, "layer": "TEXT"}).set_placement((x, y))
    draw_pipe(ctx, [(x, y - 15), (x + 45, y - 15)], "legend-process", "process", "PROCESS")
    ctx.msp.add_text("Process gas", dxfattribs={"height": 2.4, "layer": "TEXT"}).set_placement((x + 55, y - 18))
    draw_pipe(ctx, [(x, y - 30), (x + 45, y - 30)], "legend-regen", "regen", "REGEN")
    ctx.msp.add_text("Regeneration gas", dxfattribs={"height": 2.4, "layer": "TEXT"}).set_placement((x + 55, y - 33))
    draw_pipe(ctx, [(x, y - 45), (x + 45, y - 45)], "legend-flare", "flare", "FLARE_VENT")
    ctx.msp.add_text("Flare / vent", dxfattribs={"height": 2.4, "layer": "TEXT"}).set_placement((x + 55, y - 48))
    ctx.msp.add_text("SYMBOLS: XV shutdown valve, circle field/DCS instrument, triangle off-page connector", dxfattribs={"height": 2.2, "layer": "TEXT"}).set_placement((x, y - 65))
    ctx.msp.add_text("ABBREVIATIONS: NC normally closed, CSC car-sealed closed, FO fail open, FC fail closed", dxfattribs={"height": 2.2, "layer": "TEXT"}).set_placement((x, y - 78))
    ctx.registry.mark("document", "LEGEND")


def _ensure_linetypes(doc) -> None:
    for name, pattern in {
        "DASHED": [0.5, 0.25, -0.12],
        "DOTTED": [0.2, 0.03, -0.08],
    }.items():
        if name not in doc.linetypes:
            doc.linetypes.add(name, pattern=pattern)


if __name__ == "__main__":
    draw_dual_drier_template(Path(__file__).resolve().parents[1] / "outputs" / "U300-PID-301.dxf")
