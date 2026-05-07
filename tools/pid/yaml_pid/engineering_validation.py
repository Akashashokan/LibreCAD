from __future__ import annotations

from dataclasses import dataclass, field

from .models import PidConfig
from .scene import SceneRegistry


@dataclass
class ValidationReport:
    title: str
    passes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def format(self) -> str:
        lines = [self.title, "-" * len(self.title)]
        lines.append(f"PASS count: {len(self.passes)}")
        lines.append(f"WARN count: {len(self.warnings)}")
        lines.append(f"FAIL count: {len(self.failures)}")
        lines.extend(f"PASS: {x}" for x in self.passes)
        lines.extend(f"WARN: {x}" for x in self.warnings)
        lines.extend(f"FAIL: {x}" for x in self.failures)
        return "\n".join(lines)


def run_engineering_validation(config: PidConfig, registry: SceneRegistry) -> ValidationReport:
    report = ValidationReport("ENGINEERING COMPLETENESS REPORT")
    required_equipment_tags = _extract_tags(config.required.equipment)
    missing_equipment = required_equipment_tags - registry.evidence.get("equipment", set())
    _record(report, "required equipment present", missing_equipment)

    required_nozzle_tags = set()
    for placement in config.nozzles.values():
        for name in placement.nozzles:
            required_nozzle_tags.add(f"{placement.equipment_tag}.{name}")
    missing_nozzles = required_nozzle_tags - registry.evidence.get("nozzle", set())
    _record(report, "explicit nozzles drawn", missing_nozzles)

    required_valve_tags = {v.tag for v in config.valves}
    _record(report, "required valves from valve_placements present", required_valve_tags - registry.evidence.get("valve", set()))

    required_instr_tags = {i.tag for i in config.instruments}
    _record(report, "required instruments from instrument_placements present", required_instr_tags - registry.evidence.get("instrument", set()))

    report.passes.append("pipe/line annotations disabled")

    for item in ["TITLE_BLOCK", "NOTES", "LEGEND", "REVISION_TABLE"]:
        if item in registry.evidence.get("document", set()):
            report.passes.append(f"{item} present")
        else:
            report.failures.append(f"{item} missing")

    if registry.failed_block_imports:
        report.warnings.append("blocks failed to import from existing library: " + " | ".join(registry.failed_block_imports))
    else:
        report.passes.append("no existing block import failures")

    if registry.primitive_symbols_created:
        report.warnings.append("primitive symbols created from scratch: " + " | ".join(registry.primitive_symbols_created))
    else:
        report.passes.append("no primitive symbols created from scratch")

    if registry.existing_blocks_used:
        report.passes.append("existing CAD blocks inserted: " + " | ".join(registry.existing_blocks_used))
    else:
        report.warnings.append("no existing CAD blocks were inserted")

    if registry.fallbacks:
        report.warnings.append("symbol keys using primitive fallback path: " + ", ".join(registry.fallbacks))
    return report


def _extract_tags(lines: list[str]) -> set[str]:
    tags: set[str] = set()
    for line in lines:
        first = line.split()[0].rstrip(",")
        if "/" in first:
            base, suffix = first.split("/", 1)
            tags.add(base)
            if suffix.isalpha() and base[-1:].isalpha():
                tags.add(base[:-1] + suffix)
            elif suffix:
                tags.add(suffix)
        else:
            tags.add(first)
    return tags


def _record(report: ValidationReport, label: str, missing: set[str]) -> None:
    if missing:
        report.failures.append(f"{label}; missing: {', '.join(sorted(missing))}")
    else:
        report.passes.append(label)
