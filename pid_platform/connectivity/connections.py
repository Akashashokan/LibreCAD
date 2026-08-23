"""
Connection management for P&ID semantic model.

Provides the ConnectionManager class for creating, tracking, and validating
connections between ports in the semantic model.

ARCHITECTURAL NOTE:
Uses PortRef (stable immutable references) as dictionary keys instead of
mutable Port objects. This ensures reliable hashing even when port state changes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pid_platform.pid_model.base import (
    InternalContinuity,
    Port,
    PortConnection,
    PortRef,
    TerminationState,
)

if TYPE_CHECKING:
    from pid_platform.pid_model.base import PIDObject


@dataclass
class ConnectionManager:
    """
    Manages all connections in a P&ID semantic model.
    
    The ConnectionManager:
    - Creates and tracks connections between ports
    - Validates port compatibility
    - Traces paths through the network (external + internal continuity)
    - Detects unresolved ports
    - Builds the connectivity graph
    
    Attributes:
        connections: All external connections between objects
        internal_continuities: All internal component continuities
        port_connections: Map of PortRef → list of external connections
        objects: All registered objects
        _port_ref_cache: Cache mapping PortRef → Port for fast lookup
    """
    connections: list[PortConnection] = field(default_factory=list)
    internal_continuities: list[InternalContinuity] = field(default_factory=list)
    port_connections: dict[PortRef, list[PortConnection]] = field(default_factory=lambda: defaultdict(list))
    objects: dict[str, 'PIDObject'] = field(default_factory=dict)
    _port_ref_cache: dict[PortRef, Port] = field(default_factory=dict)
    
    def _get_port_ref(self, port: Port) -> PortRef:
        """Get or create a PortRef for a port and cache it."""
        ref = port.as_ref()
        self._port_ref_cache[ref] = port
        return ref
    
    def _resolve_port_ref(self, ref: PortRef) -> Port | None:
        """Resolve a PortRef back to its Port object."""
        if ref in self._port_ref_cache:
            return self._port_ref_cache[ref]
        # Try to find in registered objects
        obj = self.objects.get(ref.owner_uuid)
        if obj:
            port = obj.get_port(ref.port_id)
            if port:
                self._port_ref_cache[ref] = port
                return port
        return None
    
    def register(self, obj: 'PIDObject') -> None:
        """Register an object in the connection manager."""
        self.objects[obj.uuid] = obj
        # Pre-cache all port references
        for port in obj.get_ports():
            self._get_port_ref(port)
        
        # Register internal continuities if the object defines them
        if hasattr(obj, 'get_internal_continuities'):
            for continuity in obj.get_internal_continuities():
                self.internal_continuities.append(continuity)
    
    def connect(
        self,
        source: Port,
        target: Port,
        connection_type: str = "generic",
        metadata: dict | None = None,
    ) -> PortConnection:
        """
        Create a connection between two ports.
        
        Args:
            source: Source port
            target: Target port
            connection_type: Type of connection (pipe, signal, etc.)
            metadata: Additional connection properties
            
        Returns:
            The created PortConnection
            
        Raises:
            ValueError: If ports are incompatible
        """
        # Auto-register parent objects if they have internal continuities
        # This ensures junctions, valves, etc. are captured without explicit registration
        for port in [source, target]:
            if port.parent and hasattr(port.parent, 'get_internal_continuities'):
                # Check if already registered by looking for existing continuities
                owner_tags = [c.owner.tag for c in self.internal_continuities]
                if port.parent.tag not in owner_tags:
                    self.register(port.parent)
        
        # Validate port compatibility
        if not self._are_ports_compatible(source, target):
            raise ValueError(
                f"Incompatible ports: {source} ({source.domain.value}) "
                f"cannot connect to {target} ({target.domain.value})"
            )
        
        # Create connection
        conn = PortConnection(
            source=source,
            target=target,
            connection_type=connection_type,
            metadata=metadata or {},
        )
        
        # Get stable references for tracking
        source_ref = self._get_port_ref(source)
        target_ref = self._get_port_ref(target)
        
        # Track connection using PortRef keys
        self.connections.append(conn)
        self.port_connections[source_ref].append(conn)
        self.port_connections[target_ref].append(conn)
        
        # Update port states
        source.connect(target, conn)
        target.connect(source, conn)
        
        return conn
    
    def disconnect(self, port: Port) -> None:
        """Remove all connections from a port."""
        port_ref = self._get_port_ref(port)
        port.disconnect_all()
        
        # Remove from tracking using PortRef
        if port_ref in self.port_connections:
            del self.port_connections[port_ref]
        
        # Remove connections that reference this port
        self.connections = [
            c for c in self.connections
            if c.source != port and c.target != port
        ]
        
        # Clean up other side of connections
        for other_ref, conns in list(self.port_connections.items()):
            self.port_connections[other_ref] = [
                c for c in conns
                if c.source != port and c.target != port
            ]
    
    def _are_ports_compatible(self, port1: Port, port2: Port) -> bool:
        """Check if two ports can be connected."""
        # Same domain is always compatible
        if port1.domain == port2.domain:
            return True
        
        # Special compatibility rules for instrument connections
        # PROCESS can connect to MEASUREMENT (via impulse line or direct tap)
        from pid_platform.pid_model.base import PortDomain
        if {port1.domain, port2.domain} == {PortDomain.PROCESS, PortDomain.MEASUREMENT}:
            return True
        
        # Signal compatibility rules
        compatible_pairs = {
            (PortDomain.SIGNAL_ANALOG, PortDomain.SIGNAL_ANALOG),
            (PortDomain.SIGNAL_DIGITAL, PortDomain.SIGNAL_DIGITAL),
            (PortDomain.SIGNAL_COMMUNICATION, PortDomain.SIGNAL_COMMUNICATION),
            (PortDomain.MEASUREMENT, PortDomain.MEASUREMENT),
        }
        
        return (port1.domain, port2.domain) in compatible_pairs or \
               (port2.domain, port1.domain) in compatible_pairs
    
    def trace_path(
        self,
        start: Port,
        end: Port,
        max_hops: int = 100,
    ) -> list[Port] | None:
        """
        Trace a path from start port to end port.
        
        Uses breadth-first search to find a path through connected ports.
        Uses PortRef for visited set to ensure proper hashing.
        
        Args:
            start: Starting port
            end: Target port
            max_hops: Maximum number of hops to search
            
        Returns:
            List of ports in the path, or None if no path exists
        """
        if start == end:
            return [start]
        
        # Use PortRef for visited set since Port objects are not hashable
        start_ref = self._get_port_ref(start)
        end_ref = self._get_port_ref(end)
        visited = {start_ref}
        queue = [(start, [start])]
        
        while queue and len(queue) < max_hops:
            current, path = queue.pop(0)
            current_ref = self._get_port_ref(current)
            
            # Get all connected ports using PortRef lookup
            for conn in self.port_connections.get(current_ref, []):
                next_port = conn.target if conn.source == current else conn.source
                next_ref = self._get_port_ref(next_port)
                
                if next_ref in visited:
                    continue
                
                if next_ref == end_ref:
                    return path + [next_port]
                
                visited.add(next_ref)
                queue.append((next_port, path + [next_port]))
            
            # ALSO traverse internal continuities within the same component
            for continuity in self.internal_continuities:
                if not continuity.is_active():
                    continue
                    
                from_port, to_port = continuity.get_ports()
                
                # Check if current port is part of this continuity
                current_from_ref = self._get_port_ref(from_port)
                current_to_ref = self._get_port_ref(to_port)
                
                next_port = None
                if current_ref == current_from_ref:
                    next_port = to_port
                elif current_ref == current_to_ref and continuity.bidirectional:
                    next_port = from_port
                
                if next_port is None:
                    continue
                    
                next_ref = self._get_port_ref(next_port)
                
                if next_ref in visited:
                    continue
                
                if next_ref == end_ref:
                    return path + [next_port]
                
                visited.add(next_ref)
                queue.append((next_port, path + [next_port]))
        
        return None
    
    def get_unresolved_ports(self) -> list[Port]:
        """Get all ports with UNRESOLVED termination state."""
        unresolved = []
        for obj in self.objects.values():
            for port in obj.get_ports():
                if port.termination_state == TerminationState.UNRESOLVED:
                    unresolved.append(port)
        return unresolved
    
    def get_all_ports(self) -> list[Port]:
        """Get all ports from all registered objects."""
        all_ports = []
        for obj in self.objects.values():
            all_ports.extend(obj.get_ports())
        return all_ports
    
    def validate(self) -> list[str]:
        """
        Validate the current connection state.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check for unresolved ports
        unresolved = self.get_unresolved_ports()
        if unresolved:
            for port in unresolved:
                parent_tag = port.parent.tag if port.parent else "<orphan>"
                errors.append(f"Unresolved port: {parent_tag}.{port.id}")
        
        # Check for incompatible connections (shouldn't happen but verify)
        for conn in self.connections:
            if not self._are_ports_compatible(conn.source, conn.target):
                errors.append(
                    f"Incompatible connection: {conn.source} ↔ {conn.target}"
                )
        
        return errors
    
    def get_network_summary(self) -> str:
        """Generate a summary of the connectivity network."""
        lines = [
            "CONNECTIVITY NETWORK SUMMARY",
            "=" * 40,
            f"Objects: {len(self.objects)}",
            f"Connections: {len(self.connections)}",
            f"Total ports: {len(self.get_all_ports())}",
            f"Unresolved ports: {len(self.get_unresolved_ports())}",
            "",
            "OBJECTS:",
        ]
        
        for obj in sorted(self.objects.values(), key=lambda o: o.tag):
            ports = obj.get_ports()
            connected = sum(1 for p in ports if p.is_connected())
            lines.append(f"  {obj.tag}: {connected}/{len(ports)} ports connected")
        
        return "\n".join(lines)
