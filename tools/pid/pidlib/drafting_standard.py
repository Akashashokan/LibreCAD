from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftingStandard:
    title_text_h: float = 5.0
    subtitle_text_h: float = 4.0
    equipment_tag_h: float = 3.5
    tag_text_h: float = 2.5
    note_text_h: float = 2.0
    line_label_h: float = 2.5
    table_text_h: float = 2.3

    instrument_bubble_radius: float = 6.0
    actuator_bubble_radius: float = 4.0
    valve_symbol_len: float = 10.0
    valve_symbol_ht: float = 6.0
    flow_arrow_len: float = 4.5

    min_parallel_line_spacing: float = 15.0
    min_text_clearance: float = 5.0
    min_symbol_clearance: float = 6.0
    instrument_stack_spacing: float = 18.0
    feedback_stack_spacing: float = 36.0
    valve_tag_offset: float = 8.0
    valve_fail_offset: float = 8.0
    line_label_offset: float = 5.0
    equipment_tag_offset: float = 22.0

    sheet_w: float = 1189.0
    sheet_h: float = 841.0
    border_margin: float = 10.0
    inner_border_margin: float = 25.0

    title_block_x: float = 850.0
    title_block_y: float = 25.0
    title_block_w: float = 315.0
    title_block_h: float = 92.0

    lw_major: float = 0.35
    lw_minor: float = 0.25
    lw_signal: float = 0.18
    lw_border: float = 0.35


@dataclass(frozen=True)
class StyleProfile:
    name: str
    process_color: int
    regen_color: int
    drain_color: int
    vent_color: int
    instrument_color: int
    signal_color: int
    text_color: int
    equipment_color: int
    border_color: int
    table_color: int
    qa_color: int = 2


FINAL_STYLE = StyleProfile(
    name="final",
    process_color=7,
    regen_color=7,
    drain_color=7,
    vent_color=7,
    instrument_color=7,
    signal_color=8,
    text_color=7,
    equipment_color=7,
    border_color=7,
    table_color=8,
)

DEBUG_STYLE = StyleProfile(
    name="debug",
    process_color=1,
    regen_color=5,
    drain_color=30,
    vent_color=3,
    instrument_color=6,
    signal_color=2,
    text_color=7,
    equipment_color=4,
    border_color=7,
    table_color=8,
)


DEFAULT_STANDARD = DraftingStandard()


def style_from_name(name: str) -> StyleProfile:
    if name == "final":
        return FINAL_STYLE
    if name == "debug":
        return DEBUG_STYLE
    raise ValueError(f"Unknown drawing style: {name}")
