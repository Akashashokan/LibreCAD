"""
Test basic connectivity in the semantic model.

This test verifies that we can:
1. Create equipment with nozzles (using proper Nozzle class)
2. Create valves with internal process continuity
3. Create pumps with fixed ports
4. Connect them via external connections
5. Trace paths through external + internal connectivity
6. Validate the connections
"""

import sys
sys.path.insert(0, '/workspace')

from pid_platform.pid_model.base import PortDomain, PortDirection, TerminationState, PortRef
from pid_platform.pid_model.equipment import Vessel, Pump, ManualValve
from pid_platform.connectivity.connections import ConnectionManager


def test_vessel_nozzle_creation():
    """Test creating a vessel with nozzles."""
    v101 = Vessel(tag="V-101", service="reflux_drum")
    
    # Add nozzles
    n1 = v101.add_nozzle("N1", service="inlet", side="left", role="inlet", connection_point=(-46.0, 0.0))
    n2 = v101.add_nozzle("N2", service="outlet", side="right", role="outlet", connection_point=(46.0, 0.0))
    
    assert len(v101.nozzles) == 2
    assert v101.get_port("N1") is not None
    assert v101.get_port("N1").domain == PortDomain.PROCESS
    assert isinstance(v101.get_port("N1"), type(n1))  # Should be Nozzle type
    print("✓ Vessel nozzle creation passed")


def test_pump_fixed_ports():
    """Test pump with predefined fixed ports."""
    p101 = Pump(tag="P-101", service="reflux")
    
    # Check fixed ports exist
    assert "suction" in p101.fixed_ports
    assert "discharge" in p101.fixed_ports
    assert p101.fixed_ports["suction"].direction == PortDirection.INLET
    assert p101.fixed_ports["discharge"].direction == PortDirection.OUTLET
    print("✓ Pump fixed ports passed")


def test_valve_fixed_ports():
    """Test manual valve with predefined fixed ports."""
    xv101 = ManualValve(tag="XV-101", valve_type="ball")
    
    # Check fixed ports exist
    assert "process_in" in xv101.fixed_ports
    assert "process_out" in xv101.fixed_ports
    assert xv101.fixed_ports["process_in"].direction == PortDirection.INLET
    assert xv101.fixed_ports["process_out"].direction == PortDirection.OUTLET
    assert xv101.fixed_ports["process_in"].domain == PortDomain.PROCESS
    assert xv101.fixed_ports["process_out"].domain == PortDomain.PROCESS
    print("✓ Valve fixed ports passed")


def test_connection_manager():
    """Test connecting objects via the connection manager using PortRef-based tracking."""
    # Create objects
    v101 = Vessel(tag="V-101", service="reflux_drum")
    v101.add_nozzle("N1", service="outlet", side="bottom", role="outlet", connection_point=(0.0, -50.0))
    
    xv101 = ManualValve(tag="XV-101", valve_type="ball")
    
    p101 = Pump(tag="P-101", service="reflux")
    
    # Create connection manager and register objects
    cm = ConnectionManager()
    cm.register(v101)
    cm.register(xv101)
    cm.register(p101)
    
    # V-101.N1 → XV-101.process_in
    conn1 = cm.connect(v101.get_port("N1"), xv101.get_port("process_in"))
    
    # XV-101.process_out → P-101.suction
    conn2 = cm.connect(xv101.get_port("process_out"), p101.get_port("suction"))
    
    # Verify connections
    assert v101.get_port("N1").is_connected()
    assert xv101.get_port("process_in").is_connected()
    assert xv101.get_port("process_out").is_connected()
    assert p101.get_port("suction").is_connected()
    
    # Verify termination states
    assert v101.get_port("N1").termination_state == TerminationState.CONNECTED
    assert p101.get_port("suction").termination_state == TerminationState.CONNECTED
    
    # Trace path - MUST find complete path through external + internal connectivity
    path = cm.trace_path(v101.get_port("N1"), p101.get_port("suction"))
    assert path is not None, "Path tracing failed - should traverse through valve internal continuity"
    assert len(path) == 4, f"Expected 4 ports in path, got {len(path)}"
    
    # Verify the exact path
    assert path[0] == v101.get_port("N1"), "Path should start at V-101.N1"
    assert path[1] == xv101.get_port("process_in"), "Then to XV-101.process_in"
    assert path[2] == xv101.get_port("process_out"), "Through valve internal continuity to process_out"
    assert path[3] == p101.get_port("suction"), "Finally to P-101.suction"
    
    print("✓ Connection manager tests passed")
    print(f"  Path: {' → '.join(str(p) for p in path)}")


def test_unresolved_ports_detected():
    """Test that unresolved ports are detected."""
    v101 = Vessel(tag="V-101")
    v101.add_nozzle("N1", service="outlet", connection_point=(0.0, 0.0))
    v101.add_nozzle("N2", service="vent", connection_point=(0.0, 50.0))
    
    # Only N1 is connected
    p101 = Pump(tag="P-101")
    cm = ConnectionManager()
    cm.register(v101)  # Register so get_unresolved_ports can find it
    cm.register(p101)
    cm.connect(v101.get_port("N1"), p101.get_port("suction"))
    
    # N2 should be unresolved
    assert v101.get_port("N2").termination_state == TerminationState.UNRESOLVED
    
    # Get all unresolved ports
    unresolved = cm.get_unresolved_ports()
    assert any(p.parent.tag == "V-101" and p.id == "N2" for p in unresolved), \
        f"Expected V-101.N2 in unresolved ports, got: {[f'{p.parent}.{p.id}' for p in unresolved]}"
    
    print("✓ Unresolved port detection passed")


if __name__ == "__main__":
    print("\n=== Running Basic Connectivity Tests ===\n")
    
    test_vessel_nozzle_creation()
    test_pump_fixed_ports()
    test_connection_manager()
    test_unresolved_ports_detected()
    
    print("\n=== All Tests Passed ===\n")
