"""
CAD Symbol Definitions - Backwards Compatibility Layer

This module now wraps the canonical symbol registry from 
pid_platform.standards.pid_symbol_registry.

DEPRECATED: Direct symbol definitions have been moved to the canonical registry.
Use SymbolResolver from pid_platform.standards.pid_symbol_registry instead.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# Import from canonical registry
from pid_platform.standards.pid_symbol_registry import (
    SYMBOL_REGISTRY as CANONICAL_SYMBOL_REGISTRY,
    SymbolEntry,
    SymbolResolver,
    resolve_symbol,
    SymbolResolutionError,
    PortDefinition,
)
from pid_platform.pid_model.base import PortRef, PortDomain


@dataclass(frozen=True)
class PortAnchor:
    """Block-local anchor for a semantic port"""
    port_ref: PortRef
    x: float
    y: float
    domain: PortDomain


@dataclass
class SymbolDefinition:
    """CAD symbol definition with port anchors - backwards compatible wrapper"""
    symbol_id: str
    block_name: str
    anchors: List[PortAnchor]
    nominal_width: float = 20.0
    nominal_height: float = 20.0
    allowed_rotations: List[int] = field(default_factory=lambda: [0, 90, 180, 270])
    uniform_scale: bool = True


def _convert_canonical_to_legacy(entry: SymbolEntry) -> SymbolDefinition:
    """Convert canonical SymbolEntry to legacy SymbolDefinition for backwards compatibility"""
    # Default anchors based on common patterns
    anchors = []
    
    # Add standard port anchors based on port definitions
    anchor_positions = {
        ("PROCESS", "IN"): (-10.0, 0.0),
        ("PROCESS", "OUT"): (10.0, 0.0),
        ("SIGNAL_ANALOG", "OUT"): (6.0, 0.0),
        ("SIGNAL_ANALOG", "IN"): (-6.0, 0.0),
        ("MEASUREMENT", "IN"): (0.0, -6.0),
        ("SIGNAL_DIGITAL", "OUT"): (6.0, 0.0),
    }
    
    for port_def in entry.port_definitions:
        key = (port_def.domain, port_def.direction)
        if key in anchor_positions:
            x, y = anchor_positions[key]
            anchors.append(PortAnchor(
                port_ref=PortRef("TEMPLATE", port_def.port_id),
                x=x,
                y=y,
                domain=PortDomain(port_def.domain) if port_def.domain in [d.value for d in PortDomain] else PortDomain.PROCESS
            ))
    
    return SymbolDefinition(
        symbol_id=entry.symbol_id,
        block_name=entry.block_name,
        anchors=anchors,
        nominal_width=entry.nominal_width,
        nominal_height=entry.nominal_height,
        allowed_rotations=list(entry.allowed_rotations),
        uniform_scale=entry.uniform_scale_only
    )


# Build legacy SYMBOL_REGISTRY from canonical registry for backwards compatibility
SYMBOL_REGISTRY: Dict[str, SymbolDefinition] = {}

for symbol_id, entry in CANONICAL_SYMBOL_REGISTRY.items():
    try:
        SYMBOL_REGISTRY[symbol_id] = _convert_canonical_to_legacy(entry)
    except Exception:
        # Skip entries that can't be converted (e.g., duplicate aliases)
        pass


def get_symbol(symbol_id: str) -> SymbolDefinition:
    """Retrieve symbol definition by ID - uses canonical registry"""
    try:
        entry = resolve_symbol(symbol_id)
        return _convert_canonical_to_legacy(entry)
    except SymbolResolutionError as e:
        raise ValueError(f"Symbol '{symbol_id}' not found in approved registry: {e}")
