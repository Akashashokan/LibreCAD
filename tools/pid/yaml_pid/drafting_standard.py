from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftingStandard:
    sheet_w: float = 1189.0
    sheet_h: float = 841.0
    border_margin: float = 10.0
    inner_border_margin: float = 25.0
    title_block_x: float = 838.0
    title_block_y: float = 25.0
    title_block_w: float = 330.0
    title_block_h: float = 92.0
    title_text_h: float = 5.0
    equipment_tag_h: float = 3.5
    tag_text_h: float = 2.5
    note_text_h: float = 2.0
    line_label_h: float = 2.3
    instrument_bubble_radius: float = 6.0
    valve_symbol_len: float = 10.0
    valve_symbol_ht: float = 6.0
    flow_arrow_len: float = 6.0
    min_text_clearance: float = 4.0
    min_symbol_clearance: float = 5.0
    instrument_stack_spacing: float = 18.0
    line_label_offset: float = 5.0
    lw_major: float = 35
    lw_minor: float = 25
    lw_signal: float = 18


@dataclass(frozen=True)
class StyleProfile:
    name: str
    process_color: int
    utility_color: int
    signal_color: int
    instrument_color: int
    equipment_color: int
    text_color: int
    border_color: int
    qa_color: int
    fallback_allowed: bool


FINAL_STYLE = StyleProfile("final", 7, 8, 8, 7, 7, 7, 7, 2, False)
DEBUG_STYLE = StyleProfile("debug", 1, 5, 2, 6, 4, 7, 7, 2, True)
DEFAULT_STANDARD = DraftingStandard()


def style_from_name(name: str) -> StyleProfile:
    if name == "final":
        return FINAL_STYLE
    if name == "debug":
        return DEBUG_STYLE
    raise ValueError(f"Unknown drawing style: {name}")

