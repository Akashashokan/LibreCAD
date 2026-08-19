# Current Architecture Audit

## Overview
This document describes the current state of the P&ID CAD repository as preparation for migrating from a coordinate-driven drawing generator to a semantic/netlist-driven P&ID platform.

## Repository Structure

```
/workspace/tools/pid/
├── pidlib/                    # Core P&ID generation library
│   ├── validation.py          # Validation logic
│   ├── visual_validation.py   # Visual/geometric validation
│   ├── geometry.py            # Geometry calculations
│   ├── label_rules.py         # Label placement rules
│   ├── instrument_zones.py    # Instrument zone definitions
│   ├── cad_primitives.py      # CAD primitive operations
│   ├── drafting_standard.py   # Drafting standards
│   └── layers.py              # Layer definitions
│
├── yaml_pid/                  # YAML-driven P&ID generation
│   ├── models.py              # Data models (PortSpec, NozzleSpec, etc.)
│   ├── config_loader.py       # YAML configuration loading
│   ├── ports.py               # Port resolution logic
│   ├── scene.py               # Scene registry for tracking objects
│   ├── symbol_resolver.py     # CAD block resolution
│   ├── cad_primitives.py      # CAD operations
│   ├── grid.py                # Grid snapping utilities
│   ├── signal_routing.py      # Signal line routing
│   ├── engineering_validation.py  # Engineering completeness checks
│   ├── visual_validation.py   # Visual validation
│   ├── instrument_zones.py    # Instrument placement zones
│   ├── label_rules.py         # Annotation rules
│   └── render_deethanizer_from_yaml.py  # Main renderer
│
├── configs/deethanizer_U400/  # Deethanizer-specific configuration
│   ├── package.yaml           # Package metadata
│   ├── symbol_blocks.yaml     # Symbol-to-CAD-block mapping
│   ├── block_geometry.yaml    # Block dimensions and port locations
│   ├── equipment_placement_order.yaml
│   ├── nozzle_placement_order.yaml
│   ├── valve_placements.yaml
│   ├── route_main_process_line.yaml
│   ├── instrument_placements.yaml
│   ├── signal_routing.yaml
│   ├── sheet_layout_zones.yaml
│   └── labels_and_annotations.yaml
│
└── templates/                 # P&ID templates
```

## Module Responsibilities

### 1. DXF/Block Loading
**Location:** `yaml_pid/symbol_resolver.py`, `yaml_pid/cad_primitives.py`

Current behavior:
- Loads DXF blocks from file paths specified in `symbol_blocks.yaml`
- Uses LibreCAD block insertion mechanism
- Blocks are identified by file path and optional block name within file

### 2. Symbol Resolution
**Location:** `yaml_pid/symbol_resolver.py`

Current behavior:
- Maps semantic symbol keys (e.g., `deethanizer_column`) to candidate CAD blocks
- First matching candidate is used
- No semantic validation of block content

### 3. Equipment Drawing
**Location:** `yaml_pid/render_deethanizer_from_yaml.py`, `pidlib/`

Current behavior:
- Equipment placed using explicit coordinates from YAML
- Block geometry defines size but not semantic ports
- Nozzles drawn separately from equipment body

### 4. Nozzle Creation
**Location:** `yaml_pid/ports.py`, `block_geometry.yaml`

Current behavior:
- Nozzles defined with multiple points: `wall_point`, `stub_end`, `pipe_connection`
- Coordinates are relative to equipment origin
- **CONNECTIVITY IS COORDINATE-BASED**: Pipe endpoints must match nozzle connection points

### 5. Process Line Drawing
**Location:** `yaml_pid/render_deethanizer_from_yaml.py`, `yaml_pid/signal_routing.py`

Current behavior:
- Lines routed between coordinates
- Source and target references resolve to coordinates via `resolve_port()`
- **CRITICAL GAP**: Connectivity validated by geometric proximity, not object references

### 6. Valve Drawing
**Location:** `yaml_pid/render_deethanizer_from_yaml.py`

Current behavior:
- Valves placed on process lines
- Orientation determined by line direction
- Ports defined in `block_geometry.yaml` as simple offsets

### 7. Instrument Drawing
**Location:** `yaml_pid/render_deethanizer_from_yaml.py`, `yaml_pid/instrument_zones.py`

Current behavior:
- Instruments placed in predefined zones (field, DCS)
- Symbol type determines CAD block
- Signal connections drawn as separate polylines

### 8. Signal Drawing
**Location:** `yaml_pid/signal_routing.py`

Current behavior:
- Signal lines routed based on source/target references
- Signal type (electric, pneumatic) determines line style
- **CRITICAL GAP**: Signal connectivity validated geometrically

### 9. Placement
**Location:** `yaml_pid/render_deethanizer_from_yaml.py`, `yaml_pid/grid.py`

Current behavior:
- All placements use explicit XY coordinates
- Grid snapping applied for consistency
- No semantic constraints on placement

### 10. Routing
**Location:** `yaml_pid/signal_routing.py`, `pidlib/geometry.py`

Current behavior:
- Orthogonal routing with manual waypoints
- No automatic obstacle avoidance
- Route defined by start/end coordinates

### 11. Validation
**Location:** `yaml_pid/engineering_validation.py`, `yaml_pid/visual_validation.py`

Current behavior:
- Checks that required equipment/nozzles/valves/instruments are present
- Validates block imports succeeded
- **CRITICAL GAP**: No topology validation
- **CRITICAL GAP**: No port-type compatibility checking
- **CRITICAL GAP**: No loop completeness validation

### 12. YAML/Config Loading
**Location:** `yaml_pid/config_loader.py`, `yaml_pid/models.py`

Current behavior:
- Loads multiple YAML files into `PidConfig` dataclass
- Models are frozen dataclasses with typed fields
- Configuration drives all geometry and placement

## CAD Symbol Inventory

See: `cad_symbol_inventory.json` (generated separately)

## Connectivity Gap Analysis

### Critical Issues Identified

#### 1. Coordinate-Based Connectivity
**Problem:** Connections are defined by matching coordinates, not object references.

**Example from `block_geometry.yaml`:**
```yaml
nozzles:
  N1_feed_inlet:
    wall_point: [-28, 35]
    stub_end: [-44, 35]
    pipe_connection: [-52, 35]  # ← Coordinate defines connection
```

**Example from `ports.py`:**
```python
def resolve_port(registry: SceneRegistry, ref: object) -> Point | None:
    if isinstance(ref, str):
        key = ref.replace(...)
        return registry.ports.get(key)  # ← Returns coordinate, not port object
```

**Impact:** 
- Floating connections when coordinates don't match exactly
- No validation that connected ports are compatible
- Cannot trace connectivity without geometric analysis

#### 2. No Semantic Port Types
**Problem:** Ports have no type information beyond their name.

**Current model:**
```python
@dataclass(frozen=True)
class PortSpec:
    name: str
    offset: Point  # Only geometry, no type
```

**Missing:**
- Port domain (process, signal, measurement, mechanical)
- Allowed connection types
- Direction (inlet/outlet)
- Multiplicity constraints

#### 3. Lines Without Semantic Source/Target
**Problem:** Process lines and signal lines reference coordinates, not objects.

**Current pattern:**
```yaml
routes:
  - name: FEED_LINE
    from_ref: "UPSTREAM_OPC.feed_continuation.connection_point"
    to_ref: "T-501.N1_feed_inlet.connection_point"
```

**Issue:** The reference resolves to a coordinate tuple `(x, y)`. The semantic relationship "LINE connects EQUIPMENT.N1 to OPC" is lost after resolution.

#### 4. Nozzle/Piping Independence
**Problem:** Nozzle coordinates and piping endpoints are defined separately.

**Evidence:**
- Nozzles defined in `block_geometry.yaml` per equipment
- Piping routes defined in `route_*.yaml` with explicit coordinates
- No constraint that they must match except visual validation

#### 5. Missing Topology Validation
**Problem:** No validation that:
- Process networks are continuous
- Instrument loops are complete
- Signal paths reach intended destinations
- Branches are explicit junctions vs crossings

**Current validation only checks:**
- Equipment present ✓
- Nozzles drawn ✓
- Valves present ✓
- Instruments present ✓
- Blocks imported ✓

**Does NOT check:**
- ✗ Is V-501.N3 actually connected to T-501.N1?
- ✗ Does PIT-501.signal_out connect to PIC-501.PV_in?
- ✗ Is there a complete path from sensor to final control element?
- ✗ Are crossing lines mistakenly connected?

#### 6. Termination States Not Typed
**Problem:** Line endings are either "connected" or "dangling" based on geometry.

**Missing termination types:**
- OFF_PAGE (intentional continuation)
- CAPPED/PLUGGED
- OPEN_TO_ATMOSPHERE
- RESERVED/FUTURE
- INSTRUMENT_TAP

## Migration Requirements

### Phase 1: Semantic Model Foundation
1. Create typed port model with domains (process, signal, measurement, mechanical)
2. Define connection rules between port types
3. Build netlist data structure independent of CAD
4. Implement topology validation

### Phase 2: Symbol Library Enhancement
1. Add semantic metadata to all CAD blocks
2. Define port anchors with types, not just coordinates
3. Separate symbol geometry from instance nozzles
4. Create symbol qualification tests

### Phase 3: Renderer Refactoring
1. Make renderer consume semantic model, not coordinates
2. Resolve semantic ports to CAD coordinates deterministically
3. Enforce exact endpoint matching
4. Add CAD-vs-semantic verification

### Phase 4: Validation Engine
1. Port-type compatibility checker
2. Topology validator (piping continuity, loop completeness)
3. Junction vs crossing detector
4. Termination state validator

## Next Steps

1. Generate detailed CAD symbol inventory (`cad_symbol_inventory.json`)
2. Document all existing CAD blocks and their current usage
3. Identify which modules can be reused vs need rewriting
4. Create test fixtures for validation engine
5. Begin building semantic object model
