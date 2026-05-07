from __future__ import annotations

from dataclasses import dataclass

from .visual_validation import SceneRegistry


@dataclass(frozen=True)
class ChecklistItem:
    category: str
    description: str
    evidence_category: str
    evidence_tag: str


DRIER_PACKAGE_CHECKLIST = [
    ChecklistItem("Process", "Wet gas inlet offpage connector", "offpage", "OFFPAGE_WET_GAS"),
    ChecklistItem("Process", "Dry gas outlet offpage connector", "offpage", "OFFPAGE_DRY_GAS"),
    ChecklistItem("Process", "Inlet switching valve per bed", "valve", "XV-30101A"),
    ChecklistItem("Process", "Inlet switching valve per bed", "valve", "XV-30101B"),
    ChecklistItem("Process", "Outlet switching valve per bed", "valve", "XV-30102A"),
    ChecklistItem("Process", "Outlet switching valve per bed", "valve", "XV-30102B"),
    ChecklistItem("Process", "Manual bypass around package", "valve", "XV-30190"),
    ChecklistItem("Process", "Dust filter downstream of beds", "equipment", "F-301"),
    ChecklistItem("Regeneration", "Regen gas source/offpage", "offpage", "OFFPAGE_REGEN_GAS"),
    ChecklistItem("Regeneration", "Regen gas flow control", "instrument", "FIC-30110"),
    ChecklistItem("Regeneration", "Regen heater", "equipment", "H-301"),
    ChecklistItem("Regeneration", "Heater outlet TIC", "instrument", "TIC-30110"),
    ChecklistItem("Regeneration", "Heater outlet TAHH", "instrument", "TAHH-30110"),
    ChecklistItem("Regeneration", "Regen inlet valve per bed", "valve", "XV-30103A"),
    ChecklistItem("Regeneration", "Regen inlet valve per bed", "valve", "XV-30103B"),
    ChecklistItem("Regeneration", "Regen outlet valve per bed", "valve", "XV-30104A"),
    ChecklistItem("Regeneration", "Regen outlet valve per bed", "valve", "XV-30104B"),
    ChecklistItem("Regeneration", "Regen cooler", "equipment", "E-301"),
    ChecklistItem("Regeneration", "Regen KO drum", "equipment", "V-301"),
    ChecklistItem("Regeneration", "Regen return offpage", "offpage", "OFFPAGE_REGEN_RETURN"),
    ChecklistItem("Bed operations", "Depressurization valve per bed", "valve", "XV-30105A"),
    ChecklistItem("Bed operations", "Depressurization valve per bed", "valve", "XV-30105B"),
    ChecklistItem("Bed operations", "Pressurization/equalization valve per bed", "valve", "XV-30106A"),
    ChecklistItem("Bed operations", "Pressurization/equalization valve per bed", "valve", "XV-30106B"),
    ChecklistItem("Bed operations", "Vent per bed", "destination", "DR-301A.VENT"),
    ChecklistItem("Bed operations", "Vent per bed", "destination", "DR-301B.VENT"),
    ChecklistItem("Bed operations", "Drain per bed", "destination", "DR-301A.DRAIN"),
    ChecklistItem("Bed operations", "Drain per bed", "destination", "DR-301B.DRAIN"),
    ChecklistItem("Bed operations", "DP transmitter per bed", "instrument", "PDIT-30101A"),
    ChecklistItem("Bed operations", "DP transmitter per bed", "instrument", "PDIT-30101B"),
    ChecklistItem("Bed operations", "Pressure transmitter per bed", "instrument", "PIT-30102A"),
    ChecklistItem("Bed operations", "Pressure transmitter per bed", "instrument", "PIT-30102B"),
    ChecklistItem("Bed operations", "Temperature indication per bed", "instrument", "TIT-30103A"),
    ChecklistItem("Bed operations", "Temperature indication per bed", "instrument", "TIT-30103B"),
    ChecklistItem("Analyzer", "Moisture analyzer on dry gas outlet", "instrument", "AIT-30101"),
    ChecklistItem("Analyzer", "Analyzer controller bubble", "instrument", "AIC-30101"),
    ChecklistItem("Analyzer", "Sample conditioning", "equipment", "SC-30101"),
    ChecklistItem("Analyzer", "Sample vent", "destination", "ANALYZER.VENT"),
    ChecklistItem("Analyzer", "Sample drain", "destination", "ANALYZER.DRAIN"),
    ChecklistItem("Documentation", "Title block", "document", "TITLE_BLOCK"),
    ChecklistItem("Documentation", "Legend", "document", "LEGEND"),
    ChecklistItem("Documentation", "Notes", "document", "NOTES"),
    ChecklistItem("Documentation", "Sequence table", "document", "SEQUENCE_TABLE"),
]


def engineering_completeness_report(registry: SceneRegistry) -> tuple[str, int, int]:
    passed = 0
    missing: list[str] = []
    for item in DRIER_PACKAGE_CHECKLIST:
        seen = registry.required_seen.get(item.evidence_category, set())
        if item.evidence_tag in seen:
            passed += 1
        else:
            missing.append(f"{item.category}: {item.description} ({item.evidence_tag})")
    total = len(DRIER_PACKAGE_CHECKLIST)
    lines = ["ENGINEERING COMPLETENESS REPORT", "-------------------------------", f"Engineering completeness: {passed}/{total} checks passed"]
    lines.extend(f"MISSING: {entry}" for entry in missing[:12])
    if len(missing) > 12:
        lines.append(f"MISSING: {len(missing) - 12} additional checklist items")
    return "\n".join(lines), passed, total
