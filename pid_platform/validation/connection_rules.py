"""
Connection rules for P&ID semantic model.

Defines which port domains can connect to each other,
multiplicity rules, and direction constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from pid_platform.pid_model.base import Port, PortDomain, PortDirection

if TYPE_CHECKING:
    from pid_platform.pid_model.base import PortConnection


class ConnectionRuleResult(Enum):
    """Result of a connection rule check."""
    VALID = "valid"
    INVALID_DOMAIN = "invalid_domain"
    INVALID_DIRECTION = "invalid_direction"
    INVALID_MULTIPLICITY = "invalid_multiplicity"
    INVALID_TYPE = "invalid_type"


@dataclass
class ConnectionRuleViolation:
    """Represents a violation of connection rules."""
    rule_id: str
    message: str
    source_port: Port
    target_port: Port
    violation_type: ConnectionRuleResult
    
    def __repr__(self) -> str:
        return f"ConnectionRuleViolation({self.rule_id}: {self.message})"


# Define allowed domain connections
# Key: (source_domain, target_domain)
# Value: whether connection is allowed
ALLOWED_DOMAIN_CONNECTIONS: set[tuple[PortDomain, PortDomain]] = {
    # Process connections
    (PortDomain.PROCESS, PortDomain.PROCESS),
    (PortDomain.PROCESS, PortDomain.MEASUREMENT),  # Process tap
    (PortDomain.MEASUREMENT, PortDomain.PROCESS),  # Process tap (reverse)
    
    # Signal connections - analog signals
    (PortDomain.SIGNAL_ANALOG, PortDomain.SIGNAL_ANALOG),
    (PortDomain.SIGNAL_ANALOG, PortDomain.MEASUREMENT),  # Transmitter output
    (PortDomain.MEASUREMENT, PortDomain.SIGNAL_ANALOG),  # Transmitter input
    
    # Signal connections - digital signals
    (PortDomain.SIGNAL_DIGITAL, PortDomain.SIGNAL_DIGITAL),
    
    # Signal connections - communication
    (PortDomain.SIGNAL_COMMUNICATION, PortDomain.SIGNAL_COMMUNICATION),
    
    # Mechanical connections
    (PortDomain.MECHANICAL, PortDomain.MECHANICAL),
    
    # Electrical power
    (PortDomain.ELECTRICAL_POWER, PortDomain.ELECTRICAL_POWER),
    
    # Relief systems
    (PortDomain.RELIEF, PortDomain.RELIEF),
    (PortDomain.RELIEF, PortDomain.PROCESS),  # Relief to flare/atmosphere
}


# Domain compatibility matrix for more nuanced rules
DOMAIN_COMPATIBILITY: dict[PortDomain, set[PortDomain]] = {
    PortDomain.PROCESS: {PortDomain.PROCESS, PortDomain.MEASUREMENT},
    PortDomain.MEASUREMENT: {PortDomain.PROCESS, PortDomain.SIGNAL_ANALOG},
    PortDomain.SIGNAL_ANALOG: {PortDomain.SIGNAL_ANALOG, PortDomain.MEASUREMENT},
    PortDomain.SIGNAL_DIGITAL: {PortDomain.SIGNAL_DIGITAL},
    PortDomain.SIGNAL_COMMUNICATION: {PortDomain.SIGNAL_COMMUNICATION},
    PortDomain.MECHANICAL: {PortDomain.MECHANICAL},
    PortDomain.ELECTRICAL_POWER: {PortDomain.ELECTRICAL_POWER},
    PortDomain.RELIEF: {PortDomain.RELIEF, PortDomain.PROCESS},
    PortDomain.UTILITY: {PortDomain.PROCESS},  # Utilities connect to process
}


@dataclass
class ConnectionValidator:
    """
    Validates connections between ports based on ISA-5.1 rules.
    
    Checks:
    - Domain compatibility (process vs signal vs measurement)
    - Direction compatibility (inlet must connect to outlet)
    - Multiplicity (some ports allow only one connection)
    - Type-specific rules (e.g., control output cannot connect to process)
    """
    
    violations: list[ConnectionRuleViolation] = field(default_factory=list)
    
    def validate_connection(self, source: Port, target: Port) -> list[ConnectionRuleViolation]:
        """
        Validate a connection between two ports.
        
        Returns list of violations (empty if valid).
        """
        self.violations.clear()
        
        # Check domain compatibility
        domain_violation = self._check_domain_compatibility(source, target)
        if domain_violation:
            self.violations.append(domain_violation)
        
        # Check direction compatibility
        direction_violation = self._check_direction_compatibility(source, target)
        if direction_violation:
            self.violations.append(direction_violation)
        
        # Check multiplicity
        multiplicity_violation = self._check_multiplicity(source, target)
        if multiplicity_violation:
            self.violations.append(multiplicity_violation)
        
        return self.violations
    
    def _check_domain_compatibility(self, source: Port, target: Port) -> ConnectionRuleViolation | None:
        """Check if source and target domains are compatible."""
        allowed_targets = DOMAIN_COMPATIBILITY.get(source.domain, set())
        
        if target.domain not in allowed_targets:
            return ConnectionRuleViolation(
                rule_id="P003",
                message=f"{source.domain.value} cannot connect to {target.domain.value}",
                source_port=source,
                target_port=target,
                violation_type=ConnectionRuleResult.INVALID_DOMAIN,
            )
        
        return None
    
    def _check_direction_compatibility(self, source: Port, target: Port) -> ConnectionRuleViolation | None:
        """
        Check if port directions are compatible.
        
        Rules:
        - INLET should connect to OUTLET or BIDIRECTIONAL
        - OUTLET should connect to INLET or BIDIRECTIONAL
        - BIDIRECTIONAL can connect to anything
        """
        # If either is bidirectional, it's OK
        if source.direction == PortDirection.BIDIRECTIONAL or target.direction == PortDirection.BIDIRECTIONAL:
            return None
        
        # Both inlet or both outlet is invalid
        if source.direction == target.direction:
            return ConnectionRuleViolation(
                rule_id="P004",
                message=f"Incompatible directions: {source.direction.value} → {target.direction.value}",
                source_port=source,
                target_port=target,
                violation_type=ConnectionRuleResult.INVALID_DIRECTION,
            )
        
        return None
    
    def _check_multiplicity(self, source: Port, target: Port) -> ConnectionRuleViolation | None:
        """
        Check if connection violates multiplicity rules.
        
        Some ports should only have one connection (e.g., control outputs).
        This is a placeholder for future enhancement.
        """
        # For now, allow multiple connections
        # Future: could enforce single connection for certain port types
        return None
    
    def is_valid_connection(self, source: Port, target: Port) -> bool:
        """Quick check if connection is valid."""
        return len(self.validate_connection(source, target)) == 0


# Predefined connection type rules
CONNECTION_TYPE_RULES: dict[str, dict] = {
    "process_pipe": {
        "allowed_domains": {PortDomain.PROCESS},
        "description": "Process piping connection",
    },
    "instrument_signal": {
        "allowed_domains": {PortDomain.SIGNAL_ANALOG, PortDomain.SIGNAL_DIGITAL, PortDomain.SIGNAL_COMMUNICATION},
        "description": "Instrument signal connection",
    },
    "measurement_tap": {
        "allowed_domains": {PortDomain.MEASUREMENT, PortDomain.PROCESS},
        "description": "Process measurement connection",
    },
    "control_signal": {
        "allowed_domains": {PortDomain.SIGNAL_ANALOG, PortDomain.SIGNAL_DIGITAL},
        "description": "Control system signal",
    },
    "power_supply": {
        "allowed_domains": {PortDomain.ELECTRICAL_POWER},
        "description": "Electrical power connection",
    },
}
