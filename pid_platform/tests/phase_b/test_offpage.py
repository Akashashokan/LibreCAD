"""Test Off-Page Connector objects for drawing continuation."""

from pid_platform.pid_model.equipment import Vessel
from pid_platform.pid_model.junction import OffPageConnector, TerminationState
from pid_platform.connectivity.connections import ConnectionManager


def test_offpage_connector_creation():
    """Test that OffPageConnector can be created with proper port."""
    opc = OffPageConnector(
        tag="OPC-101",
        connector_type="process",
        service="deethanizer_overhead",
        drawing_from="PID-701",
        drawing_to="PID-702",
        continuation_id="C17",
    )
    
    # Should have 1 port
    ports = opc.get_ports()
    assert len(ports) == 1, f"Expected 1 port for OPC, got {len(ports)}"
    
    # Port should have OFF_PAGE termination state
    port = opc.get_port("continuation")
    assert port is not None
    assert port.termination_state == TerminationState.OFF_PAGE
    
    print(f"✓ OPC-101 created with port in OFF_PAGE state")


def test_offpage_connection():
    """Test that connections to OPC don't report as unresolved."""
    cm = ConnectionManager()
    
    # Create vessel with nozzle
    vessel = Vessel(tag="V-101")
    vessel.add_nozzle("N1", role="overhead")
    cm.register(vessel)
    
    # Create OPC
    opc = OffPageConnector(
        tag="OPC-101",
        connector_type="process",
        service="overhead",
        drawing_from="PID-701",
        drawing_to="PID-702",
    )
    cm.register(opc)
    
    # Connect vessel to OPC
    cm.connect(vessel.get_port("N1"), opc.get_port("continuation"))
    
    # Check that vessel nozzle is connected (not UNRESOLVED)
    nozzle = vessel.get_port("N1")
    assert len(nozzle.connections) > 0, "Nozzle should have connections"
    assert nozzle.termination_state.name == "CONNECTED"
    
    # Check that OPC port is in OFF_PAGE state (valid termination)
    opc_port = opc.get_port("continuation")
    assert opc_port.termination_state.name == "OFF_PAGE"
    
    print(f"✓ V-101.N1 → OPC-101 connection valid (not dangling)")


def test_opc_validation():
    """Test OPC matching validation."""
    opc1 = OffPageConnector(
        tag="OPC-101",
        connector_type="process",
        service="feed",
        drawing_from="PID-101",
        drawing_to="PID-102",
        continuation_id="C1",
    )
    
    opc2 = OffPageConnector(
        tag="OPC-201",
        connector_type="process",
        service="feed",
        drawing_from="PID-102",
        drawing_to="PID-101",
        continuation_id="C2",
    )
    
    # These should match
    assert opc1.validate_match(opc2), "OPCs should match"
    
    # Create mismatched OPC
    opc3 = OffPageConnector(
        tag="OPC-301",
        connector_type="process",
        service="different_service",
        drawing_from="PID-102",
        drawing_to="PID-101",
    )
    
    assert not opc1.validate_match(opc3), "OPCs with different service should not match"
    
    print(f"✓ OPC validation works correctly")


if __name__ == "__main__":
    test_offpage_connector_creation()
    test_offpage_connection()
    test_opc_validation()
    print("\n✅ All Off-Page Connector tests passed!")
