"""
Instrument loop validation following ISA-5.1.

Validates that instrumentation loops are complete and correctly structured:
- Sensor/Transmitter → Controller → Final Control Element
- Signal types match throughout the loop
- No broken connections in the loop path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pid_platform.pid_model.base import Port, PIDObject
    from pid_platform.connectivity.connections import ConnectionManager


class LoopValidationStatus(Enum):
    """Status of loop validation."""
    VALID = "valid"
    INCOMPLETE = "incomplete"
    INVALID_SIGNAL_TYPE = "invalid_signal_type"
    MISSING_COMPONENT = "missing_component"
    BROKEN_CONNECTION = "broken_connection"
    WRONG_COMPONENT_TYPE = "wrong_component_type"


@dataclass
class LoopComponent:
    """Represents a component in an instrument loop."""
    object_ref: 'PIDObject'
    role: str  # sensor, transmitter, controller, final_element, indicator, switch
    port_in: str | None = None
    port_out: str | None = None
    
    def __repr__(self) -> str:
        return f"{self.object_ref.tag} ({self.role})"


@dataclass
class LoopValidationError:
    """Represents a validation error in an instrument loop."""
    error_id: str
    message: str
    loop_id: str | None = None
    component_tag: str | None = None
    
    def __repr__(self) -> str:
        return f"LoopValidationError({self.error_id}: {self.message})"


@dataclass
class InstrumentLoop:
    """
    Represents a complete instrument loop.
    
    A typical loop consists of:
    1. Primary element/sensor (process connection)
    2. Transmitter (converts to signal)
    3. Controller/Indicator (processes signal)
    4. Final control element (valve, damper, etc.)
    
    Attributes:
        loop_id: ISA loop number (e.g., "P-101", "FIC-501")
        components: Ordered list of components in signal flow
        signal_type: Expected signal type throughout loop
        variable: Process variable being measured/controlled
    """
    loop_id: str
    components: list[LoopComponent] = field(default_factory=list)
    signal_type: str = ""  # pneumatic, electrical_analog, etc.
    variable: str = ""  # pressure, flow, temperature, level
    
    def add_component(
        self,
        obj: 'PIDObject',
        role: str,
        port_in: str | None = None,
        port_out: str | None = None,
    ) -> None:
        """Add a component to the loop."""
        self.components.append(
            LoopComponent(
                object_ref=obj,
                role=role,
                port_in=port_in,
                port_out=port_out,
            )
        )
    
    def get_component_by_role(self, role: str) -> LoopComponent | None:
        """Get component by its role."""
        for comp in self.components:
            if comp.role == role:
                return comp
        return None
    
    def validate_structure(self) -> list[LoopValidationError]:
        """
        Validate loop structure.
        
        Required components depend on loop type:
        - Control loop: sensor/transmitter + controller + final element
        - Indication loop: sensor/transmitter + indicator
        - Switch/Alarm loop: sensor/switch + alarm device
        
        Returns list of errors (empty if valid).
        """
        errors = []
        
        # Check minimum components based on loop type
        roles = [c.role for c in self.components]
        
        # Every loop needs at least a sensor or transmitter
        if not any(r in ["sensor", "transmitter", "primary_element"] for r in roles):
            errors.append(
                LoopValidationError(
                    error_id="L001",
                    message="Loop missing sensor/transmitter",
                    loop_id=self.loop_id,
                )
            )
        
        # Control loops need controller and final element
        if "controller" in roles:
            if not any(r in ["final_element", "control_valve"] for r in roles):
                errors.append(
                    LoopValidationError(
                        error_id="L002",
                        message="Control loop missing final control element",
                        loop_id=self.loop_id,
                        component_tag="controller",
                    )
                )
        
        # Check signal flow continuity
        for i in range(len(self.components) - 1):
            current = self.components[i]
            next_comp = self.components[i + 1]
            
            # Verify output of current connects to input of next
            if current.port_out is None and next_comp.port_in is not None:
                errors.append(
                    LoopValidationError(
                        error_id="L003",
                        message=f"Broken signal path: {current.object_ref.tag} has no output",
                        loop_id=self.loop_id,
                        component_tag=current.object_ref.tag,
                    )
                )
        
        return errors


@dataclass
class LoopValidator:
    """
    Validates instrument loops according to ISA-5.1.
    
    Usage:
        validator = LoopValidator(connection_manager)
        loops = validator.identify_loops()
        for loop in loops:
            errors = validator.validate_loop(loop)
    """
    
    connection_manager: 'ConnectionManager'
    errors: list[LoopValidationError] = field(default_factory=list)
    
    def identify_loops(self) -> list[InstrumentLoop]:
        """
        Identify all instrument loops in the model.
        
        Strategy:
        1. Find all transmitters/sensors (loop starting points)
        2. Trace signal path through controllers to final elements
        3. Group into loops based on loop numbers/tags
        
        Returns list of identified loops.
        """
        loops = []
        
        # This is a placeholder - full implementation requires
        # traversing the connection graph to find loop paths
        # For now, return empty list
        
        # TODO: Implement graph traversal to identify loops
        # Start from transmitters, follow signal connections,
        # end at final control elements
        
        return loops
    
    def validate_loop(self, loop: InstrumentLoop) -> list[LoopValidationError]:
        """
        Validate a single instrument loop.
        
        Checks:
        - Structural completeness
        - Signal type consistency
        - Connection continuity
        
        Returns list of errors (empty if valid).
        """
        self.errors.clear()
        
        # Check structure
        structural_errors = loop.validate_structure()
        self.errors.extend(structural_errors)
        
        # Check signal type consistency
        signal_errors = self._check_signal_consistency(loop)
        self.errors.extend(signal_errors)
        
        # Check connection continuity
        continuity_errors = self._check_connection_continuity(loop)
        self.errors.extend(continuity_errors)
        
        return self.errors
    
    def _check_signal_consistency(self, loop: InstrumentLoop) -> list[LoopValidationError]:
        """Check that signal types are consistent throughout the loop."""
        errors = []
        
        # TODO: Implement signal type checking
        # For example: pneumatic transmitter should not connect to
        # electric controller without an I/P converter
        
        return errors
    
    def _check_connection_continuity(self, loop: InstrumentLoop) -> list[LoopValidationError]:
        """Check that all connections in the loop are valid."""
        errors = []
        
        # TODO: Implement connection continuity check
        # Verify each component's output port is actually connected
        # to the next component's input port
        
        return errors
    
    def validate_all_loops(self) -> dict[str, list[LoopValidationError]]:
        """
        Validate all loops in the model.
        
        Returns dict mapping loop_id to list of errors.
        """
        loops = self.identify_loops()
        results = {}
        
        for loop in loops:
            errors = self.validate_loop(loop)
            if errors:
                results[loop.loop_id] = errors
        
        return results


# Common loop patterns for validation
LOOP_PATTERNS: dict[str, list[str]] = {
    "indication": ["sensor", "transmitter", "indicator"],
    "control": ["sensor", "transmitter", "controller", "final_element"],
    "switch_alarm": ["sensor", "switch", "alarm"],
    "cascade_control": [
        "sensor", "transmitter", 
        "master_controller", "slave_controller", 
        "final_element"
    ],
    "ratio_control": [
        "sensor_1", "transmitter_1",
        "sensor_2", "transmitter_2",
        "ratio_controller", "final_element"
    ],
}
