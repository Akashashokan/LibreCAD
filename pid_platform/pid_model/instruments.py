"""
Instrument models for P&ID semantic representation following ISA-5.1.

Instruments are classified by:
- Function (indicate, record, control, transmit, switch, analyze)
- Location (field-mounted, control room, local panel)
- Signal type (pneumatic, electrical, digital, fieldbus)

ISA-5.1 Symbol Types:
- Circle/bubble: Field-mounted instruments
- Square with circle: Shared display/control (DCS/PLC)
- Hexagon: Computer function
- Diamond: Logic function
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .base import PIDObject, Port, PortConnection, PortDomain, PortDirection
from .equipment import Equipment

if TYPE_CHECKING:
    from .base import InternalContinuity


class InstrumentLocation(Enum):
    """
    ISA-5.1 instrument location codes.
    
    Determines the symbol shape and accessibility.
    """
    FIELD_MOUNTED = "field"  # Circle - accessible in field
    LOCAL_PANEL = "local_panel"  # Circle with horizontal line - local panel
    CONTROL_ROOM = "control_room"  # Circle inside square - DCS/PLC display
    LOCAL_CONTROL_ROOM = "local_control_room"  # Circle with double line - local DCS
    COMPUTER_FUNCTION = "computer"  # Hexagon - computer function
    LOGIC_FUNCTION = "logic"  # Diamond - logic/safety function


class InstrumentFunction(Enum):
    """
    ISA-5.1 first-letter identifiers.
    
    First letter of instrument tag identifies measured/initiating variable.
    """
    A = "A", "Analyzer"
    C = "C", "Conductivity"
    E = "E", "Voltage/Electrical"
    F = "F", "Flow"
    G = "G", "Dimension/Position"
    H = "H", "Manual"
    I = "I", "Current"
    K = "K", "Time/Frequency"
    L = "L", "Level"
    M = "M", "Moisture/Humidity"
    N = "N", "User-defined"
    O = "O", "User-defined"
    P = "P", "Pressure/Vacuum"
    Q = "Q", "Quantity/Integration"
    R = "R", "Radiation/Nuclear"
    S = "S", "Speed/Frequency"
    T = "T", "Temperature"
    U = "U", "Multivariable"
    V = "V", "Vibration/Mechanical Analysis"
    W = "W", "Weight/Force"
    X = "X", "Unclassified"
    Y = "Y", "Event/State/Presence"
    Z = "Z", "Position/Dimension"


class ReadoutFunction(Enum):
    """
    ISA-5.1 suffix letters for readout/passive functions.
    
    Second+ letters identify readout, passive, or output functions.
    """
    I = "I", "Indicate"
    R = "R", "Record"
    C = "C", "Control"
    T = "T", "Transmit"
    S = "S", "Switch"
    K = "K", "Control Station"
    Q = "Q", "Integrate/Totalize"
    E = "E", "Primary Element"
    Y = "Y", "Compute/Convert"
    V = "V", "Valve/Damper"


class SignalType(Enum):
    """
    ISA-5.1 signal line types.
    
    Defines the physical nature of instrument signals.
    """
    PNEUMATIC = "pneumatic"  # 3-15 psi air signal
    ELECTRICAL_ANALOG = "electrical_analog"  # 4-20mA DC
    ELECTRICAL_DIGITAL = "electrical_digital"  # Discrete on/off
    FIELDBUS = "fieldbus"  # Foundation Fieldbus, Profibus
    COMMUNICATION_LINK = "communication_link"  # Ethernet, serial
    HYDRAULIC = "hydraulic"  # Hydraulic signal
    MECHANICAL = "mechanical"  # Mechanical linkage
    CAPILLARY = "capillary"  # Capillary tubing (filled system)
    SOFT_LINK = "soft_link"  # Data link in DCS/software
    UNSPECIFIED = "unspecified"


@dataclass
class Instrument(PIDObject):
    """
    Base class for all ISA-5.1 instruments.
    
    Instruments expose:
    - Process connection (measurement tap, sensing line)
    - Signal output (to controller, indicator, etc.)
    - Optional power supply
    - Optional configuration port
    
    Attributes:
        tag: ISA tag (e.g., PIT-101, FIC-501)
        location: Mounting location per ISA-5.1
        function: Primary measurement function
        readout: Readout/output functions
        signal_type: Output signal type
        measured_variable: What is being measured
        engineering_units: Units of measurement
        range_min: Lower range limit
        range_max: Upper range limit
    """
    location: InstrumentLocation = InstrumentLocation.FIELD_MOUNTED
    function: InstrumentFunction | None = None
    readout: list[ReadoutFunction] = field(default_factory=list)
    signal_type: SignalType = SignalType.ELECTRICAL_ANALOG
    measured_variable: str = ""
    engineering_units: str = ""
    range_min: float | None = None
    range_max: float | None = None
    
    # Standard instrument ports
    process_port: Port | None = None
    signal_out_port: Port | None = None
    power_port: Port | None = None
    
    def __post_init__(self):
        """Create standard instrument ports."""
        # Process sensing connection (goes to process tap or impulse line)
        self.process_port = Port(
            id="process_in",
            domain=PortDomain.MEASUREMENT,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(0.0, -6.0),
            direction_hint="south",
        )
        
        # Signal output (goes to controller, indicator, etc.)
        self.signal_out_port = Port(
            id="signal_out",
            domain=self._get_signal_domain(),
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(6.0, 0.0),
            direction_hint="east",
        )
        
        # Optional power supply (for active transmitters)
        if self._requires_power():
            self.power_port = Port(
                id="power_in",
                domain=PortDomain.ELECTRICAL_POWER,
                direction=PortDirection.INLET,
                parent=self,
                local_anchor=(-6.0, 0.0),
                direction_hint="west",
            )
    
    def _get_signal_domain(self) -> PortDomain:
        """Map signal type to port domain."""
        signal_domain_map = {
            SignalType.PNEUMATIC: PortDomain.SIGNAL_ANALOG,
            SignalType.ELECTRICAL_ANALOG: PortDomain.SIGNAL_ANALOG,
            SignalType.ELECTRICAL_DIGITAL: PortDomain.SIGNAL_DIGITAL,
            SignalType.HYDRAULIC: PortDomain.SIGNAL_ANALOG,
            SignalType.MECHANICAL: PortDomain.MECHANICAL,
            SignalType.FIELDBUS: PortDomain.SIGNAL_COMMUNICATION,
            SignalType.COMMUNICATION_LINK: PortDomain.SIGNAL_COMMUNICATION,
        }
        return signal_domain_map.get(self.signal_type, PortDomain.SIGNAL_ANALOG)
    
    def _requires_power(self) -> bool:
        """Check if instrument requires external power."""
        # Active transmitters need power; passive devices don't
        return self.signal_type in [
            SignalType.ELECTRICAL_ANALOG,
            SignalType.ELECTRICAL_DIGITAL,
            SignalType.FIELDBUS,
            SignalType.COMMUNICATION_LINK,
        ]
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Base instrument has measurement-to-signal continuity.
        
        The instrument senses a process variable and generates a corresponding signal.
        """
        from .base import InternalContinuity
        
        continuities = []
        
        # If we have both process and signal ports, there's measurement continuity
        if self.process_port and self.signal_out_port:
            continuities.append(
                InternalContinuity(
                    owner=self,
                    from_port_id="process_in",
                    to_port_id="signal_out",
                    continuity_type="signal",
                    condition=None,
                    bidirectional=False,
                )
            )
        
        return continuities
    
    def get_tag_components(self) -> dict[str, str]:
        """
        Parse ISA tag into components.
        
        Example: PIT-101 → {
            'first_letter': 'P',
            'suffix_letters': 'IT',
            'loop_number': '101'
        }
        """
        if not self.tag:
            return {}
        
        # Split tag into letters and numbers
        parts = self.tag.split("-")
        if len(parts) != 2:
            return {"full_tag": self.tag}
        
        letters = parts[0]
        loop_num = parts[1]
        
        return {
            "first_letter": letters[0] if letters else "",
            "suffix_letters": letters[1:] if len(letters) > 1 else "",
            "loop_number": loop_num,
            "full_tag": self.tag,
        }


@dataclass
class Transmitter(Instrument):
    """
    Transmitter - measures process variable and sends signal.
    
    Examples:
    - PIT: Pressure Indicator Transmitter
    - FIT: Flow Indicator Transmitter
    - TIT: Temperature Indicator Transmitter
    - LIT: Level Indicator Transmitter
    """
    def __post_init__(self):
        super().__post_init__()
        # Transmitters typically have one process input and one signal output
    
    def get_ports(self) -> list[Port]:
        """Return all transmitter ports."""
        ports = []
        if self.process_port:
            ports.append(self.process_port)
        if self.signal_out_port:
            ports.append(self.signal_out_port)
        if self.power_port:
            ports.append(self.power_port)
        return ports


@dataclass
class Controller(Instrument):
    """
    Controller - receives measurement, compares to setpoint, outputs control signal.
    
    Examples:
    - PIC: Pressure Indicator Controller
    - FIC: Flow Indicator Controller
    - TIC: Temperature Indicator Controller
    - LIC: Level Indicator Controller
    
    Controllers have:
    - PV input (process variable from transmitter)
    - SP input (setpoint - may be internal or external)
    - Control output (to valve, damper, etc.)
    """
    controller_type: str = "PID"  # PID, PI, PD, on/off
    action: str = "direct"  # direct or reverse acting
    
    pv_port: Port | None = None
    sp_port: Port | None = None
    control_out_port: Port | None = None
    
    def __post_init__(self):
        # Don't call super().__post_init__() - controllers have different ports
        
        # PV input (from transmitter)
        self.pv_port = Port(
            id="pv_in",
            domain=self._get_signal_domain(),
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-6.0, 0.0),
            direction_hint="west",
        )
        
        # SP input (optional - may be internal)
        self.sp_port = Port(
            id="sp_in",
            domain=PortDomain.SIGNAL_ANALOG,  # Setpoint is typically analog
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(0.0, -6.0),
            direction_hint="south",
        )
        
        # Control output (to final control element)
        self.control_out_port = Port(
            id="control_out",
            domain=self._get_signal_domain(),
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(6.0, 0.0),
            direction_hint="east",
        )
    
    def get_ports(self) -> list[Port]:
        """Return all controller ports."""
        ports = []
        if self.pv_port:
            ports.append(self.pv_port)
        if self.sp_port:
            ports.append(self.sp_port)
        if self.control_out_port:
            ports.append(self.control_out_port)
        return ports
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Controller has internal signal flow: PV + SP → Control Output
        
        This represents the control algorithm inside the controller.
        """
        from .base import InternalContinuity
        
        continuities = [
            # PV contributes to control calculation
            InternalContinuity(
                owner=self,
                from_port_id="pv_in",
                to_port_id="control_out",
                continuity_type="signal",
                condition=None,
                bidirectional=False,
            ),
        ]
        
        # If SP is external, it also contributes
        if self.sp_port:
            continuities.append(
                InternalContinuity(
                    owner=self,
                    from_port_id="sp_in",
                    to_port_id="control_out",
                    continuity_type="signal",
                    condition=None,
                    bidirectional=False,
                )
            )
        
        return continuities


@dataclass
class Indicator(Instrument):
    """
    Local indicator - displays process variable locally.
    
    Examples:
    - PI: Pressure Indicator
    - FI: Flow Indicator
    - TI: Temperature Indicator
    - LI: Level Indicator
    
    Indicators typically mount locally on equipment or piping.
    """
    def __post_init__(self):
        super().__post_init__()
        # Indicators may not need signal output if purely local
        # For simplicity, we still create signal_out_port
    
    def get_ports(self) -> list[Port]:
        """Return all indicator ports."""
        ports = []
        if self.process_port:
            ports.append(self.process_port)
        if self.signal_out_port:
            ports.append(self.signal_out_port)
        if self.power_port:
            ports.append(self.power_port)
        return ports


@dataclass
class Switch(Instrument):
    """
    Process switch - discrete on/off based on process condition.
    
    Examples:
    - PS: Pressure Switch
    - FS: Flow Switch
    - LS: Level Switch
    - TS: Temperature Switch
    
    Switches provide discrete output for alarms, interlocks, or sequencing.
    """
    trip_point: float | None = None
    trip_action: str = "open_on_rise"  # open_on_rise, close_on_rise
    reset_point: float | None = None
    
    def __post_init__(self):
        super().__post_init__()
        # Switches have discrete signal output
        self.signal_type = SignalType.ELECTRICAL_DIGITAL
        if self.signal_out_port:
            self.signal_out_port.domain = PortDomain.SIGNAL_DIGITAL
    
    def get_ports(self) -> list[Port]:
        """Return all switch ports."""
        ports = []
        if self.process_port:
            ports.append(self.process_port)
        if self.signal_out_port:
            ports.append(self.signal_out_port)
        if self.power_port:
            ports.append(self.power_port)
        return ports


@dataclass
class Analyzer(Instrument):
    """
    Process analyzer - measures chemical/composition properties.
    
    Examples:
    - AE: Analytical Element (primary sensor)
    - AT: Analyzer Transmitter
    - AI: Analyzer Indicator
    - AC: Analyzer Controller
    
    Analyzers often have sample conditioning systems.
    """
    analyzer_type: str = ""  # pH, conductivity, oxygen, chromatograph, etc.
    sample_conditioning: bool = False
    
    sample_in_port: Port | None = None
    sample_out_port: Port | None = None
    vent_port: Port | None = None
    
    def __post_init__(self):
        # Analyzers have sample flow connections instead of simple process tap
        self.sample_in_port = Port(
            id="sample_in",
            domain=PortDomain.PROCESS,  # Sample is actual process fluid
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-12.0, -6.0),
            direction_hint="south",
        )
        
        self.sample_out_port = Port(
            id="sample_out",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(12.0, -6.0),
            direction_hint="south",
        )
        
        self.vent_port = Port(
            id="vent",
            domain=PortDomain.RELIEF,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(0.0, 6.0),
            direction_hint="north",
        )
        
        # Still have signal output
        self.signal_out_port = Port(
            id="signal_out",
            domain=self._get_signal_domain(),
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(6.0, 0.0),
            direction_hint="east",
        )
    
    def get_ports(self) -> list[Port]:
        """Return all analyzer ports."""
        ports = []
        if self.sample_in_port:
            ports.append(self.sample_in_port)
        if self.sample_out_port:
            ports.append(self.sample_out_port)
        if self.vent_port:
            ports.append(self.vent_port)
        if self.signal_out_port:
            ports.append(self.signal_out_port)
        if self.power_port:
            ports.append(self.power_port)
        return ports
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """Analyzer has sample flow path and measurement signal path."""
        from .base import InternalContinuity
        
        return [
            # Sample flows through analyzer
            InternalContinuity(
                owner=self,
                from_port_id="sample_in",
                to_port_id="sample_out",
                continuity_type="process",
                condition=None,
                bidirectional=False,
            ),
            # Measurement generates signal
            InternalContinuity(
                owner=self,
                from_port_id="sample_in",
                to_port_id="signal_out",
                continuity_type="signal",
                condition=None,
                bidirectional=False,
            ),
        ]


@dataclass
class ControlValve(Equipment):
    """
    Final control element - control valve with actuator.
    
    ISA-5.1 distinguishes control valves from manual valves:
    - Process body (valve itself)
    - Actuator (pneumatic, electric, hydraulic)
    - Positioner (optional)
    - Solenoid (optional for on/off service)
    
    Tag examples:
    - FV: Flow Valve (controlled by FIC)
    - PV: Pressure Valve (controlled by PIC)
    - TV: Temperature Valve (controlled by TIC)
    - LV: Level Valve (controlled by LIC)
    """
    equipment_type: str = "control_valve"
    valve_type: str = "globe"
    actuator_type: str = "pneumatic"
    fail_position: str = "fail_close"  # fail_close, fail_open, fail_locked
    
    process_in_port: Port | None = None
    process_out_port: Port | None = None
    actuator_signal_port: Port | None = None
    positioner_feedback_port: Port | None = None
    
    def __post_init__(self):
        # Process connections
        self.process_in_port = Port(
            id="process_in",
            domain=PortDomain.PROCESS,
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(-12.0, 0.0),
            direction_hint="west",
        )
        
        self.process_out_port = Port(
            id="process_out",
            domain=PortDomain.PROCESS,
            direction=PortDirection.OUTLET,
            parent=self,
            local_anchor=(12.0, 0.0),
            direction_hint="east",
        )
        
        # Actuator signal (from controller or positioner)
        self.actuator_signal_port = Port(
            id="actuator_signal_in",
            domain=self._get_actuator_signal_domain(),
            direction=PortDirection.INLET,
            parent=self,
            local_anchor=(0.0, 12.0),
            direction_hint="north",
        )
        
        # Optional positioner feedback
        if self.actuator_type in ["pneumatic", "electric"]:
            self.positioner_feedback_port = Port(
                id="positioner_feedback",
                domain=PortDomain.SIGNAL_ANALOG,
                direction=PortDirection.OUTLET,
                parent=self,
                local_anchor=(0.0, -12.0),
                direction_hint="south",
            )
    
    def _get_actuator_signal_domain(self) -> PortDomain:
        """Map actuator type to signal domain."""
        if self.actuator_type == "pneumatic":
            return PortDomain.SIGNAL_ANALOG
        elif self.actuator_type == "electric":
            return PortDomain.SIGNAL_DIGITAL
        elif self.actuator_type == "hydraulic":
            return PortDomain.SIGNAL_ANALOG
        else:
            return PortDomain.SIGNAL_ANALOG
    
    def get_ports(self) -> list[Port]:
        """Return all control valve ports."""
        # Add ports to fixed_ports dict so they can be found by get_port()
        self.fixed_ports["process_in"] = self.process_in_port
        self.fixed_ports["process_out"] = self.process_out_port
        self.fixed_ports["actuator_signal_in"] = self.actuator_signal_port
        if self.positioner_feedback_port:
            self.fixed_ports["positioner_feedback"] = self.positioner_feedback_port
        
        ports = [self.process_in_port, self.process_out_port, self.actuator_signal_port]
        if self.positioner_feedback_port:
            ports.append(self.positioner_feedback_port)
        return ports
    
    def get_internal_continuities(self) -> list['InternalContinuity']:
        """
        Control valve has:
        1. Process continuity (in → out, modulated by actuator)
        2. Signal-to-mechanical conversion (actuator signal → valve position)
        """
        from .base import InternalContinuity
        
        continuities = [
            # Process flow (modulated but always present)
            InternalContinuity(
                owner=self,
                from_port_id="process_in",
                to_port_id="process_out",
                continuity_type="process",
                condition=None,
                bidirectional=True,
            ),
            # Actuator signal controls valve position
            InternalContinuity(
                owner=self,
                from_port_id="actuator_signal_in",
                to_port_id="process_out",
                continuity_type="signal",
                condition=None,
                bidirectional=False,
            ),
        ]
        
        if self.positioner_feedback_port:
            continuities.append(
                InternalContinuity(
                    owner=self,
                    from_port_id="process_out",
                    to_port_id="positioner_feedback",
                    continuity_type="signal",
                    condition=None,
                    bidirectional=False,
                )
            )
        
        return continuities


# Import for type hints
from .equipment import Equipment  # noqa: E402
