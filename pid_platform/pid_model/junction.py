"""
Junction and Off-Page Connector models for explicit branching and drawing continuation.

Following ISA-5.1 and DEXPI standards:
- Junctions represent explicit branch points (Tees, crosses)
- Off-Page Connectors represent intentional drawing terminations
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .base import PIDObject, Port, PortRef, PortDomain, PortDirection, InternalContinuity, TerminationState


class JunctionType(Enum):
    """Types of piping junctions."""
    TEE = "tee"  # 3-way connection
    CROSS = "cross"  # 4-way connection
    ELBOW = "elbow"  # Direction change (2-way, but explicit)
    REDUCER = "reducer"  # Size change (2-way, but explicit)


@dataclass
class Junction(PIDObject):
    """
    Explicit junction object for piping branches.
    
    A junction is NOT inferred from geometry - it must be explicitly created.
    This distinguishes connected branches from mere line crossings.
    
    Example:
        J-102 with ports: west, east, south
        All three connect to J-102, forming a T-branch
        
        LINE-A crosses LINE-B with no junction = not connected
    """
    junction_type: JunctionType = JunctionType.TEE
    parent_network: Optional[str] = None  # e.g., "PROCESS_NET_17"
    ports: dict[str, Port] = field(default_factory=dict)
    
    def get_ports(self) -> list[Port]:
        """Return all ports exposed by this junction."""
        return list(self.ports.values())
    
    def __post_init__(self):
        # Create ports based on junction type
        self._create_ports()
    
    def _create_ports(self):
        """Create appropriate ports based on junction type."""
        if self.junction_type == JunctionType.TEE:
            port_names = ["west", "east", "south"]
        elif self.junction_type == JunctionType.CROSS:
            port_names = ["west", "east", "north", "south"]
        elif self.junction_type == JunctionType.ELBOW:
            port_names = ["inlet", "outlet"]
        elif self.junction_type == JunctionType.REDUCER:
            port_names = ["large_end", "small_end"]
        else:
            port_names = ["port_1", "port_2"]
        
        for name in port_names:
            port = Port(
                id=name,
                domain=PortDomain.PROCESS,
                direction=PortDirection.BIDIRECTIONAL,
                parent=self,
            )
            self.ports[name] = port
    
    def get_internal_continuities(self) -> list[InternalContinuity]:
        """
        Define internal connectivity based on junction type.
        
        For TEE and CROSS: all ports are interconnected as a single network
        For ELBOW/REDUCER: only the two specific ports connect
        
        Returns a list where each item represents a connectivity group.
        For TEE/CROSS, returns one continuity with all ports connected together.
        """
        continuities = []
        
        if self.junction_type in [JunctionType.TEE, JunctionType.CROSS]:
            # All ports form one interconnected network
            # Create continuities connecting ALL pairs of ports
            port_keys = list(self.ports.keys())
            
            # For a TEE (west, east, south), we need:
            # west <-> east, west <-> south, east <-> south
            # This ensures any port can reach any other port
            for i, from_port in enumerate(port_keys):
                for to_port in port_keys[i+1:]:
                    continuities.append(InternalContinuity(
                        owner=self,
                        from_port_id=from_port,
                        to_port_id=to_port,
                        continuity_type="process",
                        bidirectional=True,
                    ))
        elif self.junction_type in [JunctionType.ELBOW, JunctionType.REDUCER]:
            # Only specific pairs
            port_keys = list(self.ports.keys())
            if len(port_keys) >= 2:
                continuities.append(InternalContinuity(
                    owner=self,
                    from_port_id=port_keys[0],
                    to_port_id=port_keys[1],
                    continuity_type="process",
                    bidirectional=True,
                ))
        
        return continuities


@dataclass
class OffPageConnector(PIDObject):
    """
    Explicit off-page connector for drawing continuation.
    
    A line ending at the edge of a drawing terminates at an OPC,
    not at nothing. This distinguishes intentional termini from
    dangling lines.
    
    References DEXPI PipeOffPageConnector concept.
    """
    connector_type: str = "process"  # process, signal, hydraulic, etc.
    service: Optional[str] = None  # e.g., "deethanizer_overhead"
    drawing_from: Optional[str] = None  # e.g., "PID-701"
    drawing_to: Optional[str] = None  # e.g., "PID-702"
    continuation_id: Optional[str] = None  # e.g., "C17"
    target_connector_ref: Optional[str] = None  # Reference to matching OPC
    ports: dict[str, Port] = field(default_factory=dict)
    
    def get_ports(self) -> list[Port]:
        """Return list of ports for this OPC."""
        return list(self.ports.values())
    
    def __post_init__(self):
        # Create the continuation port
        domain = PortDomain.PROCESS if self.connector_type == "process" else PortDomain.SIGNAL_ANALOG
        port = Port(
            id="continuation",
            domain=domain,
            direction=PortDirection.BIDIRECTIONAL,
            parent=self,
            termination_state=TerminationState.OFF_PAGE,
        )
        self.ports["continuation"] = port
    
    def validate_match(self, other_opc: 'OffPageConnector') -> bool:
        """
        Validate that two OPCs form a valid pair.
        
        Checks:
        - Same service
        - drawing_from of one matches drawing_to of other
        - Compatible connector types
        """
        if self.service != other_opc.service:
            return False
        
        # Check drawing references match
        drawings_match = (
            (self.drawing_from == other_opc.drawing_to and 
             self.drawing_to == other_opc.drawing_from) or
            (self.drawing_from and not self.drawing_to and 
             other_opc.drawing_to and not other_opc.drawing_from)
        )
        
        if not drawings_match:
            return False
        
        if self.connector_type != other_opc.connector_type:
            return False
        
        return True


@dataclass
class TerminationPoint(PIDObject):
    """
    Explicit termination point for vents, drains, sample points, etc.
    
    Used for:
    - Vents to atmosphere
    - Open drains
    - Sample points
    - Test connections
    - Future/plugged connections
    """
    termination_type: str = "vent"  # vent, drain, sample, test, future
    termination_state: TerminationState = TerminationState.OPEN_TO_ATMOSPHERE
    service: Optional[str] = None
    description: Optional[str] = None
    ports: dict[str, Port] = field(default_factory=dict)
    
    def get_ports(self) -> list[Port]:
        """Return list of ports."""
        return list(self.ports.values())
    
    def __post_init__(self):
        # Create the termination port
        port = Port(
            id="termination",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            termination_state=self.termination_state,
        )
        self.ports["termination"] = port
