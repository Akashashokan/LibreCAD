"""Test Junction objects for branching topology."""

from pid_platform.pid_model.equipment import Vessel, ManualValve, Pump
from pid_platform.pid_model.junction import Junction, JunctionType
from pid_platform.connectivity.connections import ConnectionManager


def test_junction_creation():
    """Test that Junction can be created with proper ports."""
    j = Junction(tag="J-101", junction_type=JunctionType.TEE)
    
    # Should have 3 ports for TEE
    ports = j.get_ports()
    assert len(ports) == 3, f"Expected 3 ports for TEE, got {len(ports)}"
    
    # Ports should be accessible by reference
    port_west = j.get_port("west")
    assert port_west is not None
    
    print(f"✓ Junction J-101 created with {len(ports)} ports: {[p.id for p in ports]}")


def test_junction_branching():
    """Test path tracing through a junction."""
    cm = ConnectionManager()
    
    # Create components and register them
    vessel = Vessel(tag="V-101")
    vessel.add_nozzle("N1", role="outlet")
    cm.register(vessel)
    
    valve = ManualValve(tag="XV-101")
    cm.register(valve)
    
    junction = Junction(tag="J-101", junction_type=JunctionType.TEE)
    cm.register(junction)
    
    pump1 = Pump(tag="P-101")
    cm.register(pump1)
    
    pump2 = Pump(tag="P-102")
    cm.register(pump2)
    
    # Connect: V-101.N1 -> XV-101.IN
    cm.connect(vessel.get_port("N1"), valve.get_port("process_in"))
    
    # Connect: XV-101.OUT -> J-101.west
    cm.connect(valve.get_port("process_out"), junction.get_port("west"))
    
    # Connect: J-101.south -> P-101.SUCTION
    cm.connect(junction.get_port("south"), pump1.get_port("suction"))
    
    # Connect: J-101.east -> P-102.SUCTION
    cm.connect(junction.get_port("east"), pump2.get_port("suction"))
    
    # Trace path from vessel to pump1
    path = cm.trace_path(vessel.get_port("N1"), pump1.get_port("suction"))
    assert path is not None, "Path should exist from V-101.N1 to P-101.SUCTION"
    assert len(path) >= 4, f"Path should go through junction, got {len(path)} hops"
    
    print(f"✓ Path V-101.N1 → P-101.SUCTION: {len(path)} hops")
    print(f"  Path: {' → '.join([str(p) for p in path])}")


def test_junction_internal_continuity():
    """Test that junction provides internal continuity between all ports."""
    j = Junction(tag="J-102", junction_type=JunctionType.CROSS)
    
    # CROSS should have 4 ports
    ports = j.get_ports()
    assert len(ports) == 4, f"Expected 4 ports for CROSS, got {len(ports)}"
    
    # Internal continuity should exist
    continuities = j.get_internal_continuities()
    assert len(continuities) > 0, "Junction should have internal continuities"
    
    print(f"✓ Junction J-102 has {len(continuities)} internal continuities")


if __name__ == "__main__":
    test_junction_creation()
    test_junction_branching()
    test_junction_internal_continuity()
    print("\n✅ All junction tests passed!")
