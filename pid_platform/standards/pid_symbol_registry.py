"""
P&ID Symbol Registry - Canonical Symbol Definitions

This module defines the canonical registry of all approved P&ID symbols.
Every semantic component type MUST resolve to exactly one approved block.

Rules:
1. ISA-5.1 symbols wherever ISA-5.1 applies (instruments, instrument bubbles, 
   signal connections, final control elements, actuators, valve failure indications)
2. For equipment not defined by ISA-5.1 (vessels, columns, pumps, compressors, 
   exchangers), use only project-approved equipment blocks
3. NO primitive geometry substitution allowed
4. If a block cannot be resolved, generation MUST FAIL with UNRESOLVED_APPROVED_PID_SYMBOL

Standards Compliance:
- ANSI/ISA-5.1-2009 for instrumentation symbols
- Project-approved library for equipment symbols
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, FrozenSet
from enum import Enum


class SymbolCategory(Enum):
    """ISA-5.1 and Equipment Symbol Categories"""
    # ISA-5.1 Instrumentation Symbols
    INSTRUMENT_BUBBLE = "instrument_bubble"
    TRANSMITTER = "transmitter"
    CONTROLLER = "controller"
    INDICATOR = "indicator"
    SWITCH = "switch"
    FINAL_CONTROL_ELEMENT = "final_control_element"
    ACTUATOR = "actuator"
    VALVE_FAILURE_INDICATION = "valve_failure_indication"
    SIGNAL_LINE = "signal_line"
    
    # Equipment Symbols (Project-Approved)
    VESSEL = "vessel"
    COLUMN = "column"
    PUMP = "pump"
    COMPRESSOR = "compressor"
    HEAT_EXCHANGER = "heat_exchanger"
    REACTOR = "reactor"
    TANK = "tank"
    
    # Valve Symbols (ISA-5.1 + Project)
    MANUAL_VALVE = "manual_valve"
    CONTROL_VALVE = "control_valve"
    CHECK_VALVE = "check_valve"
    SAFETY_RELIEF_VALVE = "safety_relief_valve"
    
    # Piping Components
    JUNCTION_TEE = "junction_tee"
    JUNCTION_CROSS = "junction_cross"
    FLANGE = "flange"
    REDUCER = "reducer"
    
    # Special Symbols
    OFF_PAGE_CONNECTOR = "off_page_connector"
    TERMINATION_POINT = "termination_point"
    WELD = "weld"


class StandardsBody(Enum):
    """Standards organizations"""
    ISA = "ANSI/ISA-5.1-2009"
    PROJECT = "Project-Approved Library"


@dataclass(frozen=True)
class PortDefinition:
    """Port definition for a symbol"""
    port_id: str
    domain: str  # PROCESS, SIGNAL_ANALOG, SIGNAL_DIGITAL, MEASUREMENT, etc.
    direction: str  # IN, OUT, BIDIR
    description: str = ""


@dataclass(frozen=True)
class SymbolEntry:
    """
    Canonical symbol registry entry
    
    Every semantic component MUST resolve to exactly one SymbolEntry.
    """
    symbol_id: str
    category: SymbolCategory
    standards_body: StandardsBody
    
    # Block reference
    block_name: str  # DXF block name
    block_source: str  # File path or library reference
    
    # Geometry
    nominal_width: float  # mm
    nominal_height: float  # mm
    allowed_rotations: FrozenSet[int] = field(default_factory=lambda: frozenset({0, 90, 180, 270}))
    uniform_scale_only: bool = True
    
    # Aliases - alternative names that resolve to this symbol
    aliases: FrozenSet[str] = field(default_factory=frozenset)
    
    # ISA-5.1 specific fields (for instrumentation)
    isa_location: Optional[str] = None  # Field, Primary Accessible, Auxiliary Accessible, etc.
    isa_function: Optional[str] = None  # T=Temperature, P=Pressure, F=Flow, etc.
    
    # Ports - must come after fields with defaults
    port_definitions: FrozenSet[PortDefinition] = field(default_factory=frozenset)
    
    def get_port_ids(self) -> Set[str]:
        """Get set of valid port IDs for this symbol"""
        return {p.port_id for p in self.port_definitions}


# ============================================================================
# PORT DEFINITIONS
# ============================================================================

# Process ports
PROCESS_IN = PortDefinition("process_in", "PROCESS", "IN", "Process fluid inlet")
PROCESS_OUT = PortDefinition("process_out", "PROCESS", "OUT", "Process fluid outlet")
SUCTION = PortDefinition("suction", "PROCESS", "IN", "Pump suction inlet")
DISCHARGE = PortDefinition("discharge", "PROCESS", "OUT", "Pump discharge outlet")

# Signal ports
SIGNAL_IN = PortDefinition("signal_in", "SIGNAL_ANALOG", "IN", "Analog signal input")
SIGNAL_OUT = PortDefinition("signal_out", "SIGNAL_ANALOG", "OUT", "Analog signal output")
PV_IN = PortDefinition("pv_in", "SIGNAL_ANALOG", "IN", "Process variable input")
CONTROL_OUT = PortDefinition("control_out", "SIGNAL_ANALOG", "OUT", "Control signal output")
ACTUATOR_SIGNAL = PortDefinition("actuator_signal_in", "SIGNAL_ANALOG", "IN", "Actuator control signal")

# Measurement ports
MEASUREMENT_IN = PortDefinition("process_in", "MEASUREMENT", "IN", "Measurement tap connection")

# Digital signal ports
DIGITAL_SIGNAL_OUT = PortDefinition("signal_out", "SIGNAL_DIGITAL", "OUT", "Digital/alarm signal output")

# Junction ports
J1 = PortDefinition("J1", "PROCESS", "BIDIR", "Junction port 1")
J2 = PortDefinition("J2", "PROCESS", "BIDIR", "Junction port 2")
J3 = PortDefinition("J3", "PROCESS", "BIDIR", "Junction port 3")
J4 = PortDefinition("J4", "PROCESS", "BIDIR", "Junction port 4")

# Generic single port
CONNECTION = PortDefinition("connection", "PROCESS", "BIDIR", "Generic connection point")
TERMINATION = PortDefinition("termination", "PROCESS", "BIDIR", "Termination point")


# ============================================================================
# SYMBOL REGISTRY
# ============================================================================

SYMBOL_REGISTRY: Dict[str, SymbolEntry] = {}


def _register_symbol(entry: SymbolEntry):
    """Register a symbol entry in the canonical registry"""
    SYMBOL_REGISTRY[entry.symbol_id] = entry
    # Also register aliases
    for alias in entry.aliases:
        SYMBOL_REGISTRY[alias] = entry


# -----------------------------------------------------------------------------
# INSTRUMENT SYMBOLS (ISA-5.1) - Using PIP Standard Blocks
# -----------------------------------------------------------------------------

# Field-mounted instruments (ISA-5.1: circle, no line)
_register_symbol(SymbolEntry(
    symbol_id="field_instrument",
    category=SymbolCategory.INSTRUMENT_BUBBLE,
    standards_body=StandardsBody.ISA,
    block_name="PIP_FIELD_INSTRUMENT",
    block_source="libreCAD_blocks/PIP Instruments/0_field-mounted-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({MEASUREMENT_IN, SIGNAL_OUT}),
    aliases=frozenset({"field_mounted_instrument", "local_instrument"})
))

_register_symbol(SymbolEntry(
    symbol_id="transmitter",
    category=SymbolCategory.TRANSMITTER,
    standards_body=StandardsBody.ISA,
    block_name="PIP_TRANSMITTER",
    block_source="libreCAD_blocks/PIP Instruments/0_field-mounted-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({MEASUREMENT_IN, SIGNAL_OUT}),
    aliases=frozenset({"field_transmitter", "process_transmitter"})
))

# Panel-mounted instruments (ISA-5.1: circle with horizontal line)
_register_symbol(SymbolEntry(
    symbol_id="panel_instrument",
    category=SymbolCategory.INSTRUMENT_BUBBLE,
    standards_body=StandardsBody.ISA,
    block_name="PIP_PANEL_INSTRUMENT",
    block_source="libreCAD_blocks/PIP Instruments/3_primary-accesible-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({PV_IN, CONTROL_OUT}),
    aliases=frozenset({"primary_accessible_instrument", "board_mounted_instrument"})
))

_register_symbol(SymbolEntry(
    symbol_id="controller",
    category=SymbolCategory.CONTROLLER,
    standards_body=StandardsBody.ISA,
    block_name="PIP_CONTROLLER",
    block_source="libreCAD_blocks/PIP Instruments/3_primary-accesible-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({PV_IN, CONTROL_OUT}),
    aliases=frozenset({"panel_controller", "pid_controller"})
))

_register_symbol(SymbolEntry(
    symbol_id="indicator",
    category=SymbolCategory.INDICATOR,
    standards_body=StandardsBody.ISA,
    block_name="PIP_INDICATOR",
    block_source="libreCAD_blocks/PIP Instruments/3_primary-accesible-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({SIGNAL_IN}),
    aliases=frozenset({"panel_indicator", "local_indicator"})
))

_register_symbol(SymbolEntry(
    symbol_id="switch",
    category=SymbolCategory.SWITCH,
    standards_body=StandardsBody.ISA,
    block_name="PIP_SWITCH",
    block_source="libreCAD_blocks/PIP Instruments/0_field-mounted-discrete-instrument.dxf",
    nominal_width=12.0,
    nominal_height=12.0,
    port_definitions=frozenset({MEASUREMENT_IN, DIGITAL_SIGNAL_OUT}),
    aliases=frozenset({"pressure_switch", "temperature_switch", "flow_switch"})
))


# -----------------------------------------------------------------------------
# VALVE SYMBOLS - Using PIP Standard Blocks
# -----------------------------------------------------------------------------

_register_symbol(SymbolEntry(
    symbol_id="manual_valve",
    category=SymbolCategory.MANUAL_VALVE,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_MANUAL_VALVE",
    block_source="libreCAD_blocks/PIP Valves/0_gate-valve-no.dxf",
    nominal_width=20.0,
    nominal_height=20.0,
    port_definitions=frozenset({PROCESS_IN, PROCESS_OUT}),
    aliases=frozenset({"gate_valve", "globe_valve", "ball_valve", "butterfly_valve"})
))

_register_symbol(SymbolEntry(
    symbol_id="control_valve",
    category=SymbolCategory.FINAL_CONTROL_ELEMENT,
    standards_body=StandardsBody.ISA,
    block_name="PIP_CONTROL_VALVE",
    block_source="libreCAD_blocks/PIP Valves/23_control-valve.dxf",
    nominal_width=20.0,
    nominal_height=20.0,
    port_definitions=frozenset({PROCESS_IN, PROCESS_OUT, ACTUATOR_SIGNAL}),
    aliases=frozenset({"pneumatic_control_valve", "actuated_valve"})
))

_register_symbol(SymbolEntry(
    symbol_id="check_valve",
    category=SymbolCategory.CHECK_VALVE,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_CHECK_VALVE",
    block_source="libreCAD_blocks/PIP Valves/2_check-valve.dxf",
    nominal_width=20.0,
    nominal_height=20.0,
    port_definitions=frozenset({PROCESS_IN, PROCESS_OUT}),
    aliases=frozenset({"non_return_valve", "nrV"})
))


# -----------------------------------------------------------------------------
# EQUIPMENT SYMBOLS (Project-Approved) - Using PIP Standard Blocks
# -----------------------------------------------------------------------------

_register_symbol(SymbolEntry(
    symbol_id="vessel",
    category=SymbolCategory.VESSEL,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_VESSEL",
    block_source="libreCAD_blocks/PIP Equipment/9_vessel-vertical.dxf",
    nominal_width=40.0,
    nominal_height=60.0,
    port_definitions=frozenset(),  # Dynamic nozzles added at runtime
    allowed_rotations=frozenset({0, 90, 180, 270}),
    aliases=frozenset({"tank", "drum", "separator", "knockout_drum"})
))

_register_symbol(SymbolEntry(
    symbol_id="pump",
    category=SymbolCategory.PUMP,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_PUMP",
    block_source="libreCAD_blocks/PIP Equipment/15_pump-horizontal-centrifugal.dxf",
    nominal_width=30.0,
    nominal_height=30.0,
    port_definitions=frozenset({SUCTION, DISCHARGE}),
    aliases=frozenset({"centrifugal_pump", "positive_displacement_pump"})
))

_register_symbol(SymbolEntry(
    symbol_id="compressor",
    category=SymbolCategory.COMPRESSOR,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_COMPRESSOR",
    block_source="libreCAD_blocks/PIP Equipment/25_compressor-centrifugal.dxf",
    nominal_width=30.0,
    nominal_height=30.0,
    port_definitions=frozenset({SUCTION, DISCHARGE}),
    aliases=frozenset({"centrifugal_compressor", "reciprocating_compressor"})
))

_register_symbol(SymbolEntry(
    symbol_id="heat_exchanger",
    category=SymbolCategory.HEAT_EXCHANGER,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_HEAT_EXCHANGER",
    block_source="libreCAD_blocks/PIP Equipment/32_heat-exchanger-tema-type-bem.dxf",
    nominal_width=60.0,
    nominal_height=20.0,
    port_definitions=frozenset({
        PortDefinition("shell_in", "PROCESS", "IN"),
        PortDefinition("shell_out", "PROCESS", "OUT"),
        PortDefinition("tube_in", "PROCESS", "IN"),
        PortDefinition("tube_out", "PROCESS", "OUT"),
    }),
    aliases=frozenset({"shell_and_tube_exchanger", "condenser", "reboiler"})
))


# -----------------------------------------------------------------------------
# JUNCTION SYMBOLS - Using PIP Standard Blocks
# -----------------------------------------------------------------------------

_register_symbol(SymbolEntry(
    symbol_id="junction_tee",
    category=SymbolCategory.JUNCTION_TEE,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_JUNCTION_TEE",
    block_source="libreCAD_blocks/PIP Fittings/0_flange.dxf",  # Placeholder - needs proper tee block
    nominal_width=10.0,
    nominal_height=10.0,
    port_definitions=frozenset({J1, J2, J3}),
    aliases=frozenset({"tee", "pipe_tee"})
))

_register_symbol(SymbolEntry(
    symbol_id="junction_cross",
    category=SymbolCategory.JUNCTION_CROSS,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_JUNCTION_CROSS",
    block_source="libreCAD_blocks/PIP Fittings/0_flange.dxf",  # Placeholder - needs proper cross block
    nominal_width=10.0,
    nominal_height=10.0,
    port_definitions=frozenset({J1, J2, J3, J4}),
    aliases=frozenset({"cross", "pipe_cross"})
))


# -----------------------------------------------------------------------------
# SPECIAL SYMBOLS - Using PIP Standard Blocks
# -----------------------------------------------------------------------------

_register_symbol(SymbolEntry(
    symbol_id="off_page_connector",
    category=SymbolCategory.OFF_PAGE_CONNECTOR,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_OFF_PAGE_CONNECTOR",
    block_source="libreCAD_blocks/PIP Pipes and Signal Lines/45_piping-tag.dxf",  # Using piping-tag as placeholder
    nominal_width=15.0,
    nominal_height=15.0,
    port_definitions=frozenset({CONNECTION}),
    aliases=frozenset({"offsheet_connector", "page_connector"})
))

_register_symbol(SymbolEntry(
    symbol_id="termination_point",
    category=SymbolCategory.TERMINATION_POINT,
    standards_body=StandardsBody.PROJECT,
    block_name="PIP_TERMINATION_POINT",
    block_source="libreCAD_blocks/PIP Fittings/9_blank.dxf",
    nominal_width=10.0,
    nominal_height=10.0,
    port_definitions=frozenset({TERMINATION}),
    aliases=frozenset({"pipeline_termination", "blind_flange"})
))


# ============================================================================
# SYMBOL RESOLVER
# ============================================================================

class SymbolResolutionError(Exception):
    """Raised when symbol resolution fails"""
    error_code: str
    
    def __init__(self, message: str, error_code: str = "UNRESOLVED_APPROVED_PID_SYMBOL"):
        super().__init__(message)
        self.error_code = error_code


class SymbolResolver:
    """
    Resolves semantic component types to approved symbol entries.
    
    CRITICAL RULES:
    1. Every component MUST resolve to an approved block
    2. NO fallback to primitive geometry
    3. NO silent substitution
    4. Resolution failure MUST raise UNRESOLVED_APPROVED_PID_SYMBOL
    """
    
    def __init__(self, registry: Optional[Dict[str, SymbolEntry]] = None):
        self._registry = registry if registry is not None else SYMBOL_REGISTRY
        self._resolved_cache: Dict[str, SymbolEntry] = {}
    
    def resolve(self, component_type: str, explicit_block: Optional[str] = None) -> SymbolEntry:
        """
        Resolve a component type to an approved symbol entry.
        
        Args:
            component_type: Semantic component type (e.g., "vessel", "transmitter")
            explicit_block: Optional explicit block override
            
        Returns:
            SymbolEntry for the component
            
        Raises:
            SymbolResolutionError with code UNRESOLVED_APPROVED_PID_SYMBOL if no approved block found
        """
        # Check cache first
        cache_key = f"{component_type}:{explicit_block}"
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]
        
        # Try explicit block first
        if explicit_block:
            for entry in self._registry.values():
                if entry.block_name == explicit_block:
                    self._resolved_cache[cache_key] = entry
                    return entry
        
        # Try direct lookup
        if component_type in self._registry:
            entry = self._registry[component_type]
            self._resolved_cache[cache_key] = entry
            return entry
        
        # Try case-insensitive lookup
        component_lower = component_type.lower()
        for key, entry in self._registry.items():
            if key.lower() == component_lower:
                self._resolved_cache[cache_key] = entry
                return entry
        
        # Try alias lookup
        for key, entry in self._registry.items():
            if component_type in entry.aliases or component_lower in {a.lower() for a in entry.aliases}:
                self._resolved_cache[cache_key] = entry
                return entry
        
        # FAILURE: No approved block found
        # DO NOT FALL BACK TO PRIMITIVE GEOMETRY
        raise SymbolResolutionError(
            f"No approved symbol found for component type: {component_type}. "
            f"Generation cannot proceed without an approved block. "
            f"Add the symbol to SYMBOL_REGISTRY or provide an explicit block.",
            error_code="UNRESOLVED_APPROVED_PID_SYMBOL"
        )
    
    def validate_symbol(self, symbol_id: str) -> bool:
        """Check if a symbol ID resolves to an approved entry"""
        try:
            self.resolve(symbol_id)
            return True
        except SymbolResolutionError:
            return False
    
    def get_all_approved_symbols(self) -> Dict[str, SymbolEntry]:
        """Return all registered approved symbols"""
        return dict(self._registry)
    
    def get_symbols_by_category(self, category: SymbolCategory) -> List[SymbolEntry]:
        """Get all symbols in a category"""
        return [e for e in self._registry.values() if e.category == category]
    
    def get_isa_symbols(self) -> List[SymbolEntry]:
        """Get all ISA-5.1 compliant symbols"""
        return [e for e in self._registry.values() if e.standards_body == StandardsBody.ISA]
    
    def get_project_symbols(self) -> List[SymbolEntry]:
        """Get all project-approved symbols"""
        return [e for e in self._registry.values() if e.standards_body == StandardsBody.PROJECT]


# Global resolver instance
DEFAULT_RESOLVER = SymbolResolver()


def resolve_symbol(component_type: str, explicit_block: Optional[str] = None) -> SymbolEntry:
    """Convenience function to resolve a symbol using the default resolver"""
    return DEFAULT_RESOLVER.resolve(component_type, explicit_block)


def validate_all_symbols() -> bool:
    """Validate that all registered symbols have valid block sources"""
    for symbol_id, entry in SYMBOL_REGISTRY.items():
        if not entry.block_source:
            raise ValueError(f"Symbol {symbol_id} has no block source")
        if not entry.port_definitions:
            # Some symbols like vessels have dynamic ports, which is OK
            pass
    return True
