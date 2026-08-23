"""
Base classes for P&ID semantic objects.

All semantic objects in the P&ID model inherit from PIDObject.
Objects are identified by UUID and tag, and expose typed ports.

ARCHITECTURAL NOTE:
Ports have SEPARATE identity from their mutable state. A PortRef provides
a stable, hashable reference to a port that remains valid even when the
port's mutable attributes (coordinates, termination state, etc.) change.
This enables reliable use as dictionary keys in the connection manager.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pid_platform.pid_model.base import PIDObject


class PortDomain(Enum):
    """
    Port domain defines what type of entity can flow through the port.
    
    Compatible domains can be connected; incompatible domains cannot.
    """
    PROCESS = "process"  # Fluid/gas material flow
    MEASUREMENT = "measurement"  # Process sensing (pressure tap, temperature well)
    SIGNAL_ANALOG = "signal_analog"  # 4-20mA, pneumatic 3-15psi
    SIGNAL_DIGITAL = "signal_digital"  # Discrete on/off, fieldbus
    SIGNAL_COMMUNICATION = "signal_communication"  # Ethernet, serial
    MECHANICAL = "mechanical"  # Mechanical linkage
    UTILITY = "utility"  # Steam, air, water utilities
    ELECTRICAL_POWER = "electrical_power"  # Power supply
    RELIEF = "relief"  # Relief/discharge to flare or atmosphere


class PortDirection(Enum):
    """Flow direction through a port."""
    INLET = "inlet"
    OUTLET = "outlet"
    BIDIRECTIONAL = "bidirectional"


class TerminationState(Enum):
    """
    State of a port's termination.
    
    Not all ports must be CONNECTED - some valid states include
    CAPPED, OPEN_TO_ATMOSPHERE, OFF_PAGE, etc.
    """
    UNRESOLVED = "unresolved"  # Not yet connected (invalid in final model)
    CONNECTED = "connected"  # Connected to another port
    CAPPED = "capped"  # Intentionally capped/plugged
    PLUGGED = "plugged"  # Intentionally plugged
    OPEN_TO_ATMOSPHERE = "open_to_atmosphere"  # Vent/drain to atmosphere
    OFF_PAGE = "off_page"  # Continues on another drawing
    RESERVED = "reserved"  # Future connection
    NOT_APPLICABLE = "not_applicable"  # N/A for this instance


@dataclass(frozen=True)
class PortRef:
    """
    Immutable reference to a port for use as dictionary keys and in graph operations.
    
    A PortRef provides stable identity separate from mutable Port state.
    It consists of:
    - owner_uuid: UUID of the parent PIDObject
    - port_id: String identifier unique within the parent
    
    This allows ports to be used reliably in:
    - Connection manager dictionaries
    - Graph traversal algorithms
    - Serialization/deserialization
    - DEXPI export/import
    
    Even when mutable port attributes change (coordinates, termination state,
    connections), the PortRef remains stable.
    """
    owner_uuid: str
    port_id: str
    
    def __hash__(self) -> int:
        return hash((self.owner_uuid, self.port_id))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PortRef):
            return NotImplemented
        return self.owner_uuid == other.owner_uuid and self.port_id == other.port_id
    
    def __repr__(self) -> str:
        return f"PortRef({self.owner_uuid[:8]}...{self.port_id})"


@dataclass
class PIDObject(ABC):
    """
    Abstract base class for all P&ID semantic objects.
    
    Attributes:
        tag: ISA-style tag (e.g., "V-101", "PIT-501")
        uuid: Unique identifier (auto-generated)
        description: Human-readable description
        metadata: Additional key-value properties
    """
    tag: str
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def get_ports(self) -> list[Port]:
        """Return all ports exposed by this object."""
        pass
    
    def get_port(self, port_id: str) -> Port | None:
        """Get a specific port by ID."""
        for port in self.get_ports():
            if port.id == port_id:
                return port
        return None
    
    def get_port_ref(self, port_id: str) -> PortRef | None:
        """Get a stable reference to a port by ID."""
        port = self.get_port(port_id)
        if port is None:
            return None
        return port.as_ref()
    
    def __hash__(self) -> int:
        return hash(self.uuid)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PIDObject):
            return NotImplemented
        return self.uuid == other.uuid


@dataclass
class Port:
    """
    A connection point on a P&ID object.
    
    Ports have:
    - An ID unique within their parent object
    - A domain (process, measurement, signal, mechanical, communication)
    - A direction (inlet, outlet, bidirectional)
    - Optional local anchor coordinates for CAD rendering
    - Connection state (unconnected, connected, terminated, etc.)
    
    IMPORTANT: Port objects themselves should NOT be used as dictionary keys.
    Use port.as_ref() to obtain a stable PortRef for graph operations.
    
    Attributes:
        id: Port identifier (unique within parent)
        domain: Port domain/type
        direction: Flow direction
        parent: Parent PIDObject
        local_anchor: Local coordinates relative to parent insertion point
        direction_hint: Preferred routing direction for CAD
        connections: List of connected ports (mutable state)
        termination_state: State if not connected
    """
    id: str
    domain: PortDomain
    direction: PortDirection = PortDirection.BIDIRECTIONAL
    parent: PIDObject | None = None
    local_anchor: tuple[float, float] = (0.0, 0.0)
    direction_hint: str = "east"
    connections: list[PortConnection] = field(default_factory=list)
    termination_state: TerminationState = TerminationState.UNRESOLVED
    
    def as_ref(self) -> PortRef:
        """
        Create a stable, immutable reference to this port.
        
        The PortRef can be used as a dictionary key and remains valid
        even when mutable port attributes change.
        """
        if self.parent is None:
            raise ValueError("Cannot create PortRef for orphan port")
        return PortRef(owner_uuid=self.parent.uuid, port_id=self.id)
    
    def connect(self, target: Port, connection: PortConnection | None = None) -> None:
        """Connect this port to another port.
        
        SPECIAL CASE: Ports with intentional termination states (OFF_PAGE,
        OPEN_TO_ATMOSPHERE, CAPPED, etc.) preserve their termination state
        even when connected. Only UNRESOLVED ports become CONNECTED.
        """
        if connection is None:
            connection = PortConnection(source=self, target=target)
        self.connections.append(connection)
        
        # Preserve intentional termination states
        intentional_states = {
            TerminationState.OFF_PAGE,
            TerminationState.OPEN_TO_ATMOSPHERE,
            TerminationState.CAPPED,
            TerminationState.PLUGGED,
            TerminationState.RESERVED,
            TerminationState.NOT_APPLICABLE,
        }
        
        if self.termination_state not in intentional_states:
            self.termination_state = TerminationState.CONNECTED
    
    def disconnect_all(self) -> None:
        """Remove all connections from this port."""
        self.connections.clear()
        self.termination_state = TerminationState.UNRESOLVED
    
    def is_connected(self) -> bool:
        """Check if port has any connections."""
        return len(self.connections) > 0
    
    def get_connected_ports(self) -> list[Port]:
        """Get all ports connected to this port."""
        connected = []
        for conn in self.connections:
            if conn.source == self:
                connected.append(conn.target)
            else:
                connected.append(conn.source)
        return connected
    
    def __eq__(self, other: object) -> bool:
        """Ports are equal if they have the same parent and ID."""
        if not isinstance(other, Port):
            return NotImplemented
        return self.parent == other.parent and self.id == other.id
    
    def __repr__(self) -> str:
        parent_tag = self.parent.tag if self.parent else "<orphan>"
        return f"Port({parent_tag}.{self.id}, domain={self.domain.value})"


@dataclass
class PortConnection:
    """
    Represents a connection between two ports.
    
    Attributes:
        source: Source port
        target: Target port
        connection_type: Type of connection (pipe, signal, etc.)
        metadata: Additional properties
    """
    source: Port
    target: Port
    connection_type: str = "generic"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Update termination states, but preserve intentional termination states
        # (OFF_PAGE, OPEN_TO_ATMOSPHERE, CAPPED, etc.)
        intentional_states = {
            TerminationState.OFF_PAGE,
            TerminationState.OPEN_TO_ATMOSPHERE,
            TerminationState.CAPPED,
            TerminationState.PLUGGED,
            TerminationState.RESERVED,
            TerminationState.NOT_APPLICABLE,
        }
        
        if self.source.termination_state not in intentional_states:
            self.source.termination_state = TerminationState.CONNECTED
        
        if self.target.termination_state not in intentional_states:
            self.target.termination_state = TerminationState.CONNECTED
    
    def __repr__(self) -> str:
        return f"PortConnection({self.source} ↔ {self.target}, type={self.connection_type})"


@dataclass
class InternalContinuity:
    """
    Represents internal process/signal continuity within a component.
    
    Unlike external PortConnection which connects two separate objects,
    InternalContinuity represents the flow path INSIDE a component.
    
    Examples:
    - Valve: process_in ↔ process_out (when open)
    - Pump: suction ↔ discharge (when running)
    - Heat Exchanger: tube_in ↔ tube_out, shell_in ↔ shell_out
    - Check Valve: inlet ↔ outlet (forward only)
    
    This enables trace_path() to traverse through components correctly.
    
    Attributes:
        owner: The component that has this internal continuity
        from_port_id: ID of the source port within the owner
        to_port_id: ID of the target port within the owner
        continuity_type: Type of continuity (process, signal, mechanical)
        condition: Optional condition for continuity (e.g., "valve_open", "pump_running")
                   If None, continuity is always active
        bidirectional: Whether flow can go both ways (default True for most cases)
    """
    owner: PIDObject
    from_port_id: str
    to_port_id: str
    continuity_type: str = "process"
    condition: str | None = None
    bidirectional: bool = True
    
    def get_ports(self) -> tuple[Port, Port]:
        """Get the two ports involved in this continuity."""
        from_port = self.owner.get_port(self.from_port_id)
        to_port = self.owner.get_port(self.to_port_id)
        if from_port is None or to_port is None:
            raise ValueError(f"Invalid port IDs in internal continuity: {self.from_port_id} or {self.to_port_id}")
        return from_port, to_port
    
    def is_active(self) -> bool:
        """Check if this continuity is currently active."""
        # For now, all continuities without conditions are active
        # Future: could check valve position, pump status, etc.
        return self.condition is None
    
    def __repr__(self) -> str:
        direction = "↔" if self.bidirectional else "→"
        cond = f" [{self.condition}]" if self.condition else ""
        return f"InternalContinuity({self.owner.tag}.{self.from_port_id} {direction} {self.owner.tag}.{self.to_port_id}{cond})"
