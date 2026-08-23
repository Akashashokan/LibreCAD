"""
CAD Symbol Definitions with Block-Local Port Anchors

Each symbol defines:
- block_name: DXF block reference
- local port anchors in block-local coordinates
- scale, rotation policies
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from pid_platform.pid_model.base import PortRef, PortDomain


@dataclass(frozen=True)
class PortAnchor:
    """Block-local anchor for a semantic port"""
    port_ref: PortRef
    x: float
    y: float
    domain: PortDomain


@dataclass
class SymbolDefinition:
    """CAD symbol definition with port anchors"""
    symbol_id: str
    block_name: str
    anchors: List[PortAnchor]
    nominal_width: float = 20.0
    nominal_height: float = 20.0
    allowed_rotations: List[int] = field(default_factory=lambda: [0, 90, 180, 270])
    uniform_scale: bool = True


# ============================================================================
# EQUIPMENT SYMBOLS
# ============================================================================

VESSEL_SYMBOL = SymbolDefinition(
    symbol_id="vessel",
    block_name="ISA_VESSEL",
    nominal_width=40.0,
    nominal_height=60.0,
    anchors=[
        # Dynamic nozzles will be added at runtime based on equipment instance
    ]
)


PUMP_SYMBOL = SymbolDefinition(
    symbol_id="pump",
    block_name="ISA_PUMP",
    nominal_width=30.0,
    nominal_height=30.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "suction"), -15.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "discharge"), 15.0, 0.0, PortDomain.PROCESS),
    ]
)


# ============================================================================
# VALVE SYMBOLS
# ============================================================================

MANUAL_VALVE_SYMBOL = SymbolDefinition(
    symbol_id="manual_valve",
    block_name="ISA_MANUAL_VALVE",
    nominal_width=20.0,
    nominal_height=20.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "process_in"), -10.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "process_out"), 10.0, 0.0, PortDomain.PROCESS),
    ]
)


CONTROL_VALVE_SYMBOL = SymbolDefinition(
    symbol_id="control_valve",
    block_name="ISA_CONTROL_VALVE",
    nominal_width=20.0,
    nominal_height=20.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "process_in"), -10.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "process_out"), 10.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "actuator_signal_in"), 0.0, 12.0, PortDomain.SIGNAL_ANALOG),
    ]
)


# ============================================================================
# INSTRUMENT SYMBOLS
# ============================================================================

FIELD_INSTRUMENT_SYMBOL = SymbolDefinition(
    symbol_id="field_instrument",
    block_name="ISA_FIELD_INSTRUMENT",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "process_in"), 0.0, -6.0, PortDomain.MEASUREMENT),
        PortAnchor(PortRef("TEMPLATE", "signal_out"), 6.0, 0.0, PortDomain.SIGNAL_ANALOG),
    ]
)


PANEL_INSTRUMENT_SYMBOL = SymbolDefinition(
    symbol_id="panel_instrument",
    block_name="ISA_PANEL_INSTRUMENT",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "pv_in"), -6.0, 0.0, PortDomain.SIGNAL_ANALOG),
        PortAnchor(PortRef("TEMPLATE", "control_out"), 6.0, 0.0, PortDomain.SIGNAL_ANALOG),
    ]
)


TRANSMITTER_SYMBOL = SymbolDefinition(
    symbol_id="transmitter",
    block_name="ISA_TRANSMITTER",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "process_in"), 0.0, -6.0, PortDomain.MEASUREMENT),
        PortAnchor(PortRef("TEMPLATE", "signal_out"), 6.0, 0.0, PortDomain.SIGNAL_ANALOG),
    ]
)


CONTROLLER_SYMBOL = SymbolDefinition(
    symbol_id="controller",
    block_name="ISA_CONTROLLER",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "pv_in"), -6.0, 0.0, PortDomain.SIGNAL_ANALOG),
        PortAnchor(PortRef("TEMPLATE", "control_out"), 6.0, 0.0, PortDomain.SIGNAL_ANALOG),
    ]
)


INDICATOR_SYMBOL = SymbolDefinition(
    symbol_id="indicator",
    block_name="ISA_INDICATOR",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "signal_in"), -6.0, 0.0, PortDomain.SIGNAL_ANALOG),
    ]
)


SWITCH_SYMBOL = SymbolDefinition(
    symbol_id="switch",
    block_name="ISA_SWITCH",
    nominal_width=12.0,
    nominal_height=12.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "process_in"), 0.0, -6.0, PortDomain.MEASUREMENT),
        PortAnchor(PortRef("TEMPLATE", "signal_out"), 6.0, 0.0, PortDomain.SIGNAL_DIGITAL),
    ]
)


# ============================================================================
# JUNCTION SYMBOLS
# ============================================================================

JUNCTION_TEE_SYMBOL = SymbolDefinition(
    symbol_id="junction_tee",
    block_name="JUNCTION_TEE",
    nominal_width=10.0,
    nominal_height=10.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "J1"), -5.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "J2"), 5.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "J3"), 0.0, 5.0, PortDomain.PROCESS),
    ]
)


JUNCTION_CROSS_SYMBOL = SymbolDefinition(
    symbol_id="junction_cross",
    block_name="JUNCTION_CROSS",
    nominal_width=10.0,
    nominal_height=10.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "J1"), -5.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "J2"), 5.0, 0.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "J3"), 0.0, 5.0, PortDomain.PROCESS),
        PortAnchor(PortRef("TEMPLATE", "J4"), 0.0, -5.0, PortDomain.PROCESS),
    ]
)


# ============================================================================
# SPECIAL SYMBOLS
# ============================================================================

OFF_PAGE_CONNECTOR_SYMBOL = SymbolDefinition(
    symbol_id="off_page_connector",
    block_name="OFF_PAGE_CONNECTOR",
    nominal_width=15.0,
    nominal_height=15.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "connection"), 0.0, 0.0, PortDomain.PROCESS),
    ]
)


TERMINATION_POINT_SYMBOL = SymbolDefinition(
    symbol_id="termination_point",
    block_name="TERMINATION_POINT",
    nominal_width=10.0,
    nominal_height=10.0,
    anchors=[
        PortAnchor(PortRef("TEMPLATE", "termination"), 0.0, 0.0, PortDomain.PROCESS),
    ]
)


# ============================================================================
# SYMBOL REGISTRY
# ============================================================================

SYMBOL_REGISTRY = {
    "vessel": VESSEL_SYMBOL,
    "pump": PUMP_SYMBOL,
    "manual_valve": MANUAL_VALVE_SYMBOL,
    "control_valve": CONTROL_VALVE_SYMBOL,
    "field_instrument": FIELD_INSTRUMENT_SYMBOL,
    "panel_instrument": PANEL_INSTRUMENT_SYMBOL,
    "transmitter": TRANSMITTER_SYMBOL,
    "controller": CONTROLLER_SYMBOL,
    "indicator": INDICATOR_SYMBOL,
    "switch": SWITCH_SYMBOL,
    "junction_tee": JUNCTION_TEE_SYMBOL,
    "junction_cross": JUNCTION_CROSS_SYMBOL,
    "off_page_connector": OFF_PAGE_CONNECTOR_SYMBOL,
    "termination_point": TERMINATION_POINT_SYMBOL,
}


def get_symbol(symbol_id: str) -> SymbolDefinition:
    """Retrieve symbol definition by ID"""
    if symbol_id not in SYMBOL_REGISTRY:
        raise ValueError(f"Unknown symbol: {symbol_id}")
    return SYMBOL_REGISTRY[symbol_id]
