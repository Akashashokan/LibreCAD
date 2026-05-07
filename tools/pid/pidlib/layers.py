from __future__ import annotations

from .drafting_standard import FINAL_STYLE, StyleProfile


def layer_colors(style: StyleProfile = FINAL_STYLE) -> dict[str, int]:
    return {
        "PROCESS": style.process_color,
        "REGEN": style.regen_color,
        "FLARE_VENT": style.vent_color,
        "DRAIN": style.drain_color,
        "INSTRUMENT": style.instrument_color,
        "SIGNAL_ELECTRIC": style.signal_color,
        "SIGNAL_PNEUMATIC": style.signal_color,
        "TEXT": style.text_color,
        "EQUIPMENT": style.equipment_color,
        "BORDER": style.border_color,
        "TABLE": style.table_color,
        "QA_OVERLAY": style.qa_color,
    }


def setup_layers(doc, style: StyleProfile = FINAL_STYLE) -> None:
    for name, color in layer_colors(style).items():
        if name not in doc.layers:
            doc.layers.add(name=name, color=color)
        else:
            doc.layers.get(name).dxf.color = color
