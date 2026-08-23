"""
Equipment models for P&ID semantic representation.

Equipment includes vessels, columns, pumps, compressors, heat exchangers, etc.
Equipment objects expose nozzle ports for process connections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .base import PIDObject, Port, PortDomain, PortDirection


@dataclass
class Nozzle(Port):
    """
    A nozzle is a process port on equipment.
    
    Nozzles have additional metadata beyond basic ports:
    - Service (what flows through)
    - Side (which side of equipment)
    - Physical dimensions (optional, for detailed design)
    
    Attributes:
        id: Nozzle identifier (e.g., "N1", "A")
        domain: Always PROCESS for nozzles
        direction: Flow direction
        parent: Parent equipment
        local_anchor: Local coordinates relative to parent insertion point
        direction_hint: Preferred routing direction
        connections: List of connected ports
        termination_state: State if not connected
        service: Service description (e.g., "feed", "overhead", "bottoms")
        side: Equipment side ("left", "right", "top", "bottom", "front", "back")
        role: Functional role (e.g., "inlet", "outlet", "vent", "drain")
        wall_point: Point where nozzle meets equipment wall
        stub_end: End of nozzle stub
        flange_point: Flange connection point
        connection_point: Final connection point for piping
    """
    service: str = ""
    side: str = ""
    role: str = ""
    wall_point: tuple[float, float] = (0.0, 0.0)
    stub_end: tuple[float, float] = (0.0, 0.0)
    flange_point: tuple[float, float] = (0.0, 0.0)
    connection_point: tuple[float, float] = (0.0, 0.0)
    
    def __post_init__(self):
        """Ensure domain is always PROCESS for nozzles."""
        self.domain = PortDomain.PROCESS


@dataclass
class Equipment(PIDObject):
    """
    Base class for all equipment items.
    
    Equipment has:
    - A tag (e.g., "V-101", "T-501")
    - Equipment type
    - Service description
    - Nozzles (process ports)
    - Optional fixed ports (for standardized equipment like pumps)
    """
    equipment_type: str = ""
    service: str = ""
    nozzles: dict[str, Nozzle] = field(default_factory=dict)
    fixed_ports: dict[str, Port] = field(default_factory=dict)
    
    def add_nozzle(
        self,
        name: str,
        service: str = "",
        side: str = "",
        role: str = "",
        connection_point: tuple[float, float] = (0.0, 0.0),
    ) -> Nozzle:
        """Add a nozzle to this equipment."""
        from .base import PortDirection, TerminationState
        
        nozzle = Nozzle(
            id=name,
            domain=PortDomain.PROCESS,  # Explicitly set domain
            direction=PortDirection.BIDIRECTIONAL,
            parent=self,
            local_anchor=connection_point,
            direction_hint="east",
            connections=[],
            termination_state=TerminationState.UNRESOLVED,
            service=service,
            side=side,
            role=role,
            connection_point=connection_point,
            wall_point=(0.0, 0.0),
            stub_end=(0.0, 0.0),
            flange_point=(0.0, 0.0),
        )
        self.nozzles[name] = nozzle
        return nozzle
    
    def get_ports(self) -> list[Port]:
        """Return all nozzles and fixed ports."""
        all_ports: list[Port] = []
        all_ports.extend(self.nozzles.values())
        all_ports.extend(self.fixed_ports.values())
        return all_ports
    
    def get_port(self, port_id: str) -> Port | None:
        """Get a port by ID (searches nozzles first, then fixed ports)."""
        if port_id in self.nozzles:
            return self.nozzles[port_id]
        # Call get_ports() to ensure fixed_ports is populated for subclasses
        # that populate fixed_ports in their get_ports() implementation
        self.get_ports()
        return self.fixed_ports.get(port_id)


@dataclass
class Vessel(Equipment):
    """A vessel (tank, drum, separator)."""
    equipment_type: str = "vessel"
    orientation: Literal["horizontal", "vertical"] = "horizontal"


@dataclass
class Column(Equipment):
    """A distillation/absorption column with trays or packing."""
    equipment_type: str = "column"
    orientation: Literal["vertical"] = "vertical"
    tray_count: int = 0
    packing_height: float = 0.0


@dataclass
class Pump(Equipment):
    """A pump (centrifugal, positive displacement)."""
    equipment_type: str = "pump"
    pump_type: str = "centrifugal"
    
    def __post_init__(self):
        # Standard pump ports
        self.fixed_ports["suction"] = Port(
            id="suction",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-24.0, 0.0),
            direction_hint="west",
        )
        self.fixed_ports["discharge"] = Port(
            id="discharge",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(24.0, 8.0),
            direction_hint="east",
        )
        self.fixed_ports["drain"] = Port(
            id="drain",
            domain=PortDomain.PROCESS,
            parent=self,
            local_anchor=(0.0, -18.0),
            direction_hint="south",
        )
        self.fixed_ports["vent"] = Port(
            id="vent",
            domain=PortDomain.PROCESS,
            parent=self,
            local_anchor=(0.0, 18.0),
            direction_hint="north",
        )
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Return internal process continuities for this pump.
        
        A pump has process continuity from suction to discharge
        when the pump is running. For normal modeling, we assume
        the pump is in operation.
        
        Future enhancement: Add condition="pump_running" to model
        pump start/stop states.
        """
        from .base import InternalContinuity
        
        return [
            InternalContinuity(
                owner=self,
                from_port_id="suction",
                to_port_id="discharge",
                continuity_type="process",
                condition=None,  # Could be "pump_running" for dynamic modeling
                bidirectional=False,  # Pumps typically only flow one way
            )
        ]


@dataclass
class Compressor(Equipment):
    """A compressor."""
    equipment_type: str = "compressor"
    compressor_type: str = "centrifugal"
    
    def __post_init__(self):
        self.fixed_ports["suction"] = Port(
            id="suction",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
        )
        self.fixed_ports["discharge"] = Port(
            id="discharge",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
        )


@dataclass
class HeatExchanger(Equipment):
    """
    A heat exchanger (shell-and-tube, plate, air cooler).
    
    Has separate shell-side and tube-side ports.
    """
    equipment_type: str = "heat_exchanger"
    exchanger_type: str = "shell_and_tube"
    
    def __post_init__(self):
        # Shell side
        self.fixed_ports["shell_in"] = Port(
            id="shell_in",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-46.0, 8.0),
        )
        self.fixed_ports["shell_out"] = Port(
            id="shell_out",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(46.0, 8.0),
        )
        # Tube side
        self.fixed_ports["tube_in"] = Port(
            id="tube_in",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-46.0, -8.0),
        )
        self.fixed_ports["tube_out"] = Port(
            id="tube_out",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(46.0, -8.0),
        )
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Return internal process continuities for this heat exchanger.
        
        A shell-and-tube heat exchanger has TWO separate flow paths:
        - Tube side: tube_in ↔ tube_out
        - Shell side: shell_in ↔ shell_out
        
        These paths must NEVER cross (no tube-to-shell leakage in ideal model).
        """
        from .base import InternalContinuity
        
        return [
            InternalContinuity(
                owner=self,
                from_port_id="tube_in",
                to_port_id="tube_out",
                continuity_type="process",
                condition=None,
                bidirectional=True,
            ),
            InternalContinuity(
                owner=self,
                from_port_id="shell_in",
                to_port_id="shell_out",
                continuity_type="process",
                condition=None,
                bidirectional=True,
            ),
        ]


@dataclass
class ManualValve(Equipment):
    """
    A manual valve (gate, ball, globe, plug).
    
    Valves have internal process continuity: process_in connects internally
    to process_out when the valve is open. For semantic modeling, we assume
    valves are normally open unless specified otherwise.
    """
    equipment_type: str = "manual_valve"
    valve_type: str = "ball"
    
    def __post_init__(self):
        # Fixed process ports
        self.fixed_ports["process_in"] = Port(
            id="process_in",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-12.0, 0.0),
            direction_hint="west",
        )
        self.fixed_ports["process_out"] = Port(
            id="process_out",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(12.0, 0.0),
            direction_hint="east",
        )
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Return internal process continuities for this valve.
        
        A manual valve has process continuity between inlet and outlet
        when the valve is in normal (open) state.
        """
        from .base import InternalContinuity
        
        return [
            InternalContinuity(
                owner=self,
                from_port_id="process_in",
                to_port_id="process_out",
                continuity_type="process",
                condition=None,  # No condition = always active (normally open)
                bidirectional=True,  # Flow can go both ways
            )
        ]
