from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class LayoutConfig:
    a0_w: float = 1189.0
    a0_h: float = 841.0
    margin: float = 10.0


def calculate_layout() -> Dict[str, Tuple[float, float]]:
    cfg = LayoutConfig()
    left = cfg.margin + 45
    right = cfg.a0_w - cfg.margin - 45
    center = (left + right) / 2

    return {
        "OFFPAGE_WET_GAS": (left, 620),
        "OFFPAGE_DRY_GAS": (right, 500),
        "OFFPAGE_REGEN_IN": (left, 300),
        "OFFPAGE_REGEN_OUT": (right, 210),
        "OFFPAGE_FLARE": (right, 90),
        "OFFPAGE_CLOSED_DRAIN": (right, 55),
        "DR-301A": (center - 170, 560),
        "DR-301B": (center + 170, 560),
        "H-301": (center - 170, 300),
        "E-301": (center + 110, 210),
        "V-301": (center + 280, 210),
        "F-301": (center + 60, 500),
        "AIT-30101": (center + 210, 500),
        "AIC-30101": (center + 260, 550),
    }
