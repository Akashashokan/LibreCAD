from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class LayoutConfig:
    a0_w: float = 1189.0
    a0_h: float = 841.0
    margin: float = 10.0


def calculate_layout() -> tuple[Dict[str, Tuple[float, float]], Dict[Tuple[str, str], List[Tuple[float, float]]]]:
    cfg = LayoutConfig()
    left = cfg.margin + 45
    right = cfg.a0_w - cfg.margin - 45
    center = (left + right) / 2

    pos = {
        "OFFPAGE_WET_GAS": (left, 620),
        "OFFPAGE_DRY_GAS": (right, 500),
        "OFFPAGE_REGEN_IN": (left, 300),
        "OFFPAGE_REGEN_OUT": (right, 210),
        "DR-301A": (center - 170, 560),
        "DR-301B": (center + 170, 560),
        "DR-301A.N1": (center - 195, 590),
        "DR-301B.N1": (center + 145, 590),
        "DR-301A.N2": (center - 145, 530),
        "DR-301B.N2": (center + 195, 530),
        "DR-301A.N3": (center - 195, 545),
        "DR-301B.N3": (center + 145, 545),
        "DR-301A.N4": (center - 145, 575),
        "DR-301B.N4": (center + 195, 575),
        "H-301": (center - 170, 300),
        "E-301": (center + 110, 210),
        "V-301": (center + 280, 210),
        "F-301": (center + 60, 500),
        "AIT-30101": (center + 210, 500),
        "AIC-30101": (center + 260, 550),
        "XV-30101A": (center - 250, 590),
        "XV-30101B": (center + 90, 590),
        "XV-30102A": (center - 90, 530),
        "XV-30102B": (center + 250, 530),
        "XV-30103A": (center - 250, 545),
        "XV-30103B": (center + 90, 545),
        "XV-30104A": (center - 90, 575),
        "XV-30104B": (center + 250, 575),
    }

    route = {
        ("OFFPAGE_WET_GAS", "XV-30101A"): [(left, 620), (center - 250, 620), (center - 250, 590)],
        ("XV-30101A", "DR-301A.N1"): [(center - 250, 590), (center - 195, 590)],
        ("OFFPAGE_WET_GAS", "XV-30101B"): [(left, 620), (center + 90, 620), (center + 90, 590)],
        ("XV-30101B", "DR-301B.N1"): [(center + 90, 590), (center + 145, 590)],
        ("DR-301A.N2", "XV-30102A"): [(center - 145, 530), (center - 90, 530)],
        ("DR-301B.N2", "XV-30102B"): [(center + 195, 530), (center + 250, 530)],
        ("XV-30102A", "F-301"): [(center - 90, 530), (center - 20, 530), (center - 20, 500), (center + 60, 500)],
        ("XV-30102B", "F-301"): [(center + 250, 530), (center + 210, 530), (center + 210, 500), (center + 60, 500)],
        ("F-301", "OFFPAGE_DRY_GAS"): [(center + 60, 500), (right, 500)],
        ("OFFPAGE_REGEN_IN", "H-301"): [(left, 300), (center - 170, 300)],
        ("H-301", "XV-30103A"): [(center - 170, 300), (center - 250, 300), (center - 250, 545)],
        ("XV-30103A", "DR-301A.N3"): [(center - 250, 545), (center - 195, 545)],
        ("H-301", "XV-30103B"): [(center - 170, 300), (center + 90, 300), (center + 90, 545)],
        ("XV-30103B", "DR-301B.N3"): [(center + 90, 545), (center + 145, 545)],
        ("DR-301A.N4", "XV-30104A"): [(center - 145, 575), (center - 90, 575)],
        ("DR-301B.N4", "XV-30104B"): [(center + 195, 575), (center + 250, 575)],
        ("XV-30104A", "E-301"): [(center - 90, 575), (center + 110, 575), (center + 110, 210)],
        ("XV-30104B", "E-301"): [(center + 250, 575), (center + 300, 575), (center + 300, 210), (center + 110, 210)],
        ("E-301", "V-301"): [(center + 110, 210), (center + 280, 210)],
        ("V-301", "OFFPAGE_REGEN_OUT"): [(center + 280, 210), (right, 210)],
        ("AIT-30101", "AIC-30101"): [(center + 210, 500), (center + 260, 500), (center + 260, 550)],
    }
    return pos, route
