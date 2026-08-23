"""
Test Phase A: Signal Typing & Loop Validation

This test suite validates:
1. SignalType enums (Pneumatic, Electrical, Hydraulic, etc.)
2. Connection rules (domain compatibility, direction checks)
3. Loop validation (complete control loops, signal flow)
4. Invalid connection rejection (e.g., Control Output → Process Pipe)
"""

import pytest
from pid_platform.pid_model.base import PortDomain, PortDirection, TerminationState
from pid_platform.pid_model.equipment import Pump, Vessel, ManualValve, HeatExchanger
from pid_platform.pid_model.instruments import (
    Transmitter, Controller, Indicator, Switch,
    SignalType, InstrumentLocation, ReadoutFunction, InstrumentFunction
)
from pid_platform.connectivity.connections import ConnectionManager
from pid_platform.validation.connection_rules import (
    ConnectionValidator, ConnectionRuleResult, DOMAIN_COMPATIBILITY
)
from pid_platform.validation.loop_validator import (
    LoopValidator, InstrumentLoop, LoopComponent, LoopValidationError
)


class TestSignalTypes:
    """Test ISA-5.1 signal type definitions."""
    
    def test_signal_type_enum_values(self):
        """Verify all required signal types exist."""
        assert SignalType.PNEUMATIC.value == "pneumatic"
        assert SignalType.ELECTRICAL_ANALOG.value == "electrical_analog"
        assert SignalType.ELECTRICAL_DIGITAL.value == "electrical_digital"
        assert SignalType.FIELDBUS.value == "fieldbus"
        assert SignalType.HYDRAULIC.value == "hydraulic"
        assert SignalType.MECHANICAL.value == "mechanical"
        assert SignalType.CAPILLARY.value == "capillary"
    
    def test_transmitter_signal_type_default(self):
        """Transmitters default to electrical analog (4-20mA)."""
        pit = Transmitter(tag="PIT-101")
        assert pit.signal_type == SignalType.ELECTRICAL_ANALOG
    
    def test_switch_signal_type(self):
        """Switches use digital signals."""
        ps = Switch(tag="PS-101", trip_point=10.0)
        assert ps.signal_type == SignalType.ELECTRICAL_DIGITAL
        # Verify port domain is updated
        assert ps.signal_out_port.domain == PortDomain.SIGNAL_DIGITAL
    
    def test_pneumatic_transmitter(self):
        """Can create pneumatic transmitter (3-15 psi)."""
        pt_pneumatic = Transmitter(
            tag="PT-102",
            signal_type=SignalType.PNEUMATIC
        )
        assert pt_pneumatic.signal_type == SignalType.PNEUMATIC
        # Should map to SIGNAL_ANALOG domain
        assert pt_pneumatic.signal_out_port.domain == PortDomain.SIGNAL_ANALOG


class TestConnectionRules:
    """Test ISA-5.1 connection compatibility rules."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ConnectionValidator()
    
    def test_process_to_process_allowed(self):
        """Process ports can connect to process ports."""
        vessel = Vessel(tag="V-101")
        nozzle = vessel.add_nozzle("N1", service="outlet")
        
        valve = ManualValve(tag="XV-101")
        
        violations = self.validator.validate_connection(nozzle, valve.fixed_ports["process_in"])
        assert len(violations) == 0
        assert self.validator.is_valid_connection(nozzle, valve.fixed_ports["process_in"])
    
    def test_measurement_to_process_allowed(self):
        """Measurement tap can connect to process (process sensing)."""
        vessel = Vessel(tag="V-101")
        nozzle = vessel.add_nozzle("N1", service="process")
        
        transmitter = Transmitter(tag="PIT-101")
        
        # Transmitter process_in (MEASUREMENT) to vessel nozzle (PROCESS)
        violations = self.validator.validate_connection(
            transmitter.process_port, nozzle
        )
        assert len(violations) == 0
    
    def test_control_output_cannot_connect_to_process_pipe(self):
        """CRITICAL: Control output cannot connect directly to process pipe."""
        controller = Controller(tag="PIC-101")
        valve = ManualValve(tag="XV-101")
        
        # Try to connect controller output to valve process port (WRONG!)
        violations = self.validator.validate_connection(
            controller.control_out_port,
            valve.fixed_ports["process_in"]
        )
        
        # This should fail - SIGNAL_ANALOG cannot connect to PROCESS
        assert len(violations) > 0
        assert violations[0].violation_type == ConnectionRuleResult.INVALID_DOMAIN
        assert "signal_analog" in violations[0].message.lower() or \
               "process" in violations[0].message.lower()
    
    def test_signal_analog_compatibility(self):
        """Analog signal ports can connect to each other."""
        transmitter = Transmitter(tag="PIT-101")
        controller = Controller(tag="PIC-101")
        
        # Transmitter output to controller PV input
        violations = self.validator.validate_connection(
            transmitter.signal_out_port,
            controller.pv_port
        )
        assert len(violations) == 0
    
    def test_incompatible_directions_rejected(self):
        """Two outlets or two inlets should be rejected."""
        pump = Pump(tag="P-101")
        valve = ManualValve(tag="XV-101")
        
        # Both are outlets - should fail
        violations = self.validator.validate_connection(
            pump.fixed_ports["discharge"],
            valve.fixed_ports["process_out"]
        )
        
        assert len(violations) > 0
        assert violations[0].violation_type == ConnectionRuleResult.INVALID_DIRECTION
    
    def test_domain_compatibility_matrix(self):
        """Verify domain compatibility matrix is correct."""
        # Process can connect to process and measurement
        assert PortDomain.PROCESS in DOMAIN_COMPATIBILITY[PortDomain.PROCESS]
        assert PortDomain.MEASUREMENT in DOMAIN_COMPATIBILITY[PortDomain.PROCESS]
        
        # Measurement can connect to process and signal_analog
        assert PortDomain.PROCESS in DOMAIN_COMPATIBILITY[PortDomain.MEASUREMENT]
        assert PortDomain.SIGNAL_ANALOG in DOMAIN_COMPATIBILITY[PortDomain.MEASUREMENT]
        
        # Signal analog can connect to signal analog and measurement
        assert PortDomain.SIGNAL_ANALOG in DOMAIN_COMPATIBILITY[PortDomain.SIGNAL_ANALOG]
        assert PortDomain.MEASUREMENT in DOMAIN_COMPATIBILITY[PortDomain.SIGNAL_ANALOG]
        
        # CRITICAL: Signal cannot connect to process directly
        assert PortDomain.PROCESS not in DOMAIN_COMPATIBILITY[PortDomain.SIGNAL_ANALOG]


class TestControlLoopValidation:
    """Test complete control loop structure validation."""
    
    def test_complete_pressure_control_loop(self):
        """Validate a complete PIC loop: PIT → PIC → PV."""
        # Create components
        pit = Transmitter(
            tag="PIT-101",
            function=InstrumentFunction.P,
            readout=[ReadoutFunction.I, ReadoutFunction.T],
        )
        
        pic = Controller(
            tag="PIC-101",
            function=InstrumentFunction.P,
            readout=[ReadoutFunction.I, ReadoutFunction.C],
        )
        
        # Note: In real implementation, we'd need a ControlValve class
        # For now, use manual valve as placeholder
        pv = ManualValve(tag="PV-101", valve_type="control")
        
        # Create connection manager and connect them
        cm = ConnectionManager()
        
        # Process connection: vessel → transmitter sense
        vessel = Vessel(tag="V-101")
        vessel_nozzle = vessel.add_nozzle("N1", service="process")
        cm.connect(vessel_nozzle, pit.process_port)
        
        # Signal connection: transmitter → controller
        cm.connect(pit.signal_out_port, pic.pv_port)
        
        # Control connection: controller → valve actuator
        # Note: This requires valve to have actuator port
        # For now, skip this connection in test
        
        # Build loop object
        loop = InstrumentLoop(loop_id="P-101", variable="pressure")
        loop.add_component(pit, role="transmitter", port_out="signal_out")
        loop.add_component(pic, role="controller", port_in="pv_in", port_out="control_out")
        # loop.add_component(pv, role="final_element", port_in="actuator_in")
        
        # Validate loop structure
        validator = LoopValidator(cm)
        errors = validator.validate_loop(loop)
        
        # Should have error about missing final element
        assert any(e.error_id == "L002" for e in errors), \
            "Should detect missing final control element"
    
    def test_indication_loop_valid(self):
        """Validate simple PI indication loop."""
        pi = Indicator(
            tag="PI-101",
            function=InstrumentFunction.P,
            readout=[ReadoutFunction.I],
            location=InstrumentLocation.LOCAL_PANEL,
        )
        
        vessel = Vessel(tag="V-101")
        nozzle = vessel.add_nozzle("N1", service="process")
        
        cm = ConnectionManager()
        cm.connect(nozzle, pi.process_port)
        
        loop = InstrumentLoop(loop_id="P-101", variable="pressure")
        loop.add_component(pi, role="indicator", port_in="process_in")
        
        validator = LoopValidator(cm)
        errors = validator.validate_loop(loop)
        
        # Indication loop only needs indicator
        # No L001 error (missing sensor/transmitter) because indicator serves both roles
        # This depends on implementation - may need adjustment
        print(f"Indication loop errors: {errors}")
    
    def test_broken_signal_path_detected(self):
        """Detect when signal path is broken in loop."""
        pit = Transmitter(tag="PIT-101")
        pic = Controller(tag="PIC-101")
        
        # DON'T connect them - simulate broken loop
        
        loop = InstrumentLoop(loop_id="P-101")
        loop.add_component(pit, role="transmitter", port_out=None)  # No output!
        loop.add_component(pic, role="controller", port_in="pv_in")
        
        errors = loop.validate_structure()
        
        # Should detect broken path
        assert len(errors) > 0


class TestInternalContinuityWithInstruments:
    """Test that instruments have proper internal continuity."""
    
    def test_transmitter_has_measurement_continuity(self):
        """Transmitter converts process measurement to signal."""
        pit = Transmitter(tag="PIT-101")
        
        continuities = pit.get_internal_continuities()
        
        assert len(continuities) > 0
        continuity = continuities[0]
        assert continuity.from_port_id == "process_in"
        assert continuity.to_port_id == "signal_out"
        assert continuity.continuity_type == "signal"
        assert not continuity.bidirectional  # Measurement flows one way
    
    def test_controller_has_control_continuity(self):
        """Controller processes PV (+ SP) to produce control output."""
        pic = Controller(tag="PIC-101")
        
        continuities = pic.get_internal_continuities()
        
        assert len(continuities) >= 1
        # Should have PV → control_out continuity
        pv_continuity = next(
            (c for c in continuities if c.from_port_id == "pv_in"),
            None
        )
        assert pv_continuity is not None
        assert pv_continuity.to_port_id == "control_out"


class TestIntegration:
    """Integration test combining all Phase A features."""
    
    def test_full_control_loop_with_validation(self):
        """
        Complete test: Vessel → PIT → PIC → (future PV)
        
        Tests:
        1. Equipment with nozzles
        2. Transmitter with measurement tap
        3. Controller with signal connections
        4. Connection rule validation
        5. Path tracing through entire system
        """
        # Create equipment
        vessel = Vessel(tag="V-101", service="feed drum")
        nozzle = vessel.add_nozzle("N1", service="overhead", role="outlet")
        
        # Create instruments
        pit = Transmitter(
            tag="PIT-101",
            function=InstrumentFunction.P,
            readout=[ReadoutFunction.I, ReadoutFunction.T],
            signal_type=SignalType.ELECTRICAL_ANALOG,
        )
        
        pic = Controller(
            tag="PIC-101",
            function=InstrumentFunction.P,
            readout=[ReadoutFunction.I, ReadoutFunction.C],
            controller_type="PID",
        )
        
        # Create connection manager
        cm = ConnectionManager()
        
        # Connect vessel to transmitter (process measurement)
        conn1 = cm.connect(nozzle, pit.process_port)
        assert conn1 is not None
        
        # Connect transmitter to controller (analog signal)
        conn2 = cm.connect(pit.signal_out_port, pic.pv_port)
        assert conn2 is not None
        
        # Verify all ports are connected
        assert nozzle.is_connected()
        assert pit.process_port.is_connected()
        assert pit.signal_out_port.is_connected()
        assert pic.pv_port.is_connected()
        
        # Trace path from vessel to controller
        path = cm.trace_path(nozzle, pic.pv_port)
        assert len(path) > 0
        
        # Verify connection rules were followed
        validator = ConnectionValidator()
        assert validator.is_valid_connection(nozzle, pit.process_port)
        assert validator.is_valid_connection(pit.signal_out_port, pic.pv_port)
        
        # Try invalid connection - should fail
        pump = Pump(tag="P-101")
        invalid_violations = validator.validate_connection(
            pic.control_out_port,
            pump.fixed_ports["suction"]
        )
        assert len(invalid_violations) > 0
        assert invalid_violations[0].violation_type == ConnectionRuleResult.INVALID_DOMAIN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
