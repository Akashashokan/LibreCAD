"""
P&ID Platform - Semantic Engineering Model

This package provides a semantic/netlist-driven P&ID engineering platform.
The P&ID is treated as an executable engineering model from which drawings
are rendered, rather than treating the drawing itself as the source of truth.

Architecture:
    pid_model/      - Semantic object definitions (Equipment, Nozzle, Valve, etc.)
    connectivity/   - Ports, connections, netlist, junctions
    validation/     - Schema, port, topology, and loop validators
    layout/         - Placement and routing (consumes semantic model)
    renderers/      - DXF backend (renders validated semantic model)
    symbols/        - CAD symbol library with semantic metadata
    standards/      - ISA rules and project-specific standards
    adapters/       - DEXPI compatibility and legacy YAML migration
    tests/          - Test fixtures and golden examples

Key Principles:
    1. Coordinates answer "where", not "what connects"
    2. Semantic model is authoritative; DXF is rendered output
    3. Validation happens before rendering
    4. AI authors engineering model, not drawing
    5. Deterministic software proves correctness
    6. Reusability over special-case code
"""

__version__ = "0.1.0"
