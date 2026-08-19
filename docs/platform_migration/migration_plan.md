# P&ID Platform Migration Plan

## Executive Summary

This document outlines the migration from a coordinate-driven P&ID drawing generator to a semantic/netlist-driven P&ID engineering platform. The key architectural change is treating the P&ID as an **executable engineering model** from which drawings are rendered, rather than treating the drawing itself as the source of truth.

## Two-Phase Development Strategy

### Objective 1: Build the P&ID Platform (Foundation)
**Deliverable:** A semantic P&ID kernel with ISA CAD component library, netlist engine, verification system, and DXF backend.

**Success Criteria:**
- [ ] Every usable CAD symbol has semantic metadata
- [ ] Every fixed-port symbol has explicit local port anchors
- [ ] Equipment nozzles exist as semantic objects
- [ ] No connection is defined purely by coordinates
- [ ] Every process line has semantic source/target
- [ ] Every instrument connection has semantic source/target
- [ ] Every signal has semantic source/target and signal type
- [ ] Branches require explicit junction semantics
- [ ] Crossings are not interpreted as connections
- [ ] Intentional termini have typed termination objects
- [ ] Invalid port combinations are rejected
- [ ] Dangling objects are detected
- [ ] Complete instrument loops can be traced programmatically
- [ ] DXF process endpoints resolve exactly to semantic ports
- [ ] DXF signal endpoints resolve exactly to semantic ports
- [ ] Golden valid fixtures pass
- [ ] Golden corrupted fixtures fail
- [ ] Existing block library remains usable
- [ ] Existing LibreCAD rendering remains operational

### Objective 2: AI P&ID Engineering (Application)
**Deliverable:** AI engineering agent that authors semantic P&ID models from process requirements.

**Only begins after Objective 1 gate passes.**

## Repository Structure

```
/workspace/
├── docs/platform_migration/       # Migration documentation
│   ├── current_architecture.md    # Current state analysis
│   ├── cad_symbol_inventory.json  # CAD block inventory
│   ├── connectivity_gap_analysis.md
│   └── migration_plan.md          # This document
│
├── tools/pid/                     # Existing P&ID generation code
│   ├── pidlib/                    # Core library (to be refactored)
│   ├── yaml_pid/                  # YAML-driven renderer (to be refactored)
│   └── configs/                   # Deethanizer configuration
│
├── pid_platform/                  # NEW: Semantic P&ID platform
│   ├── standards/
│   │   ├── isa/
│   │   │   ├── identification_rules.yaml
│   │   │   ├── signal_types.yaml
│   │   │   ├── instrument_classes.yaml
│   │   │   └── symbol_catalog.yaml
│   │   └── project/
│   │       ├── tagging.yaml
│   │       ├── piping_rules.yaml
│   │       └── drafting_rules.yaml
│   │
│   ├── symbols/
│   │   ├── cad/                   # Canonical CAD blocks
│   │   │   ├── instruments/
│   │   │   ├── valves/
│   │   │   ├── equipment/
│   │   │   ├── fittings/
│   │   │   └── logic/
│   │   └── registry/              # Symbol metadata
│   │       ├── instruments/
│   │       ├── valves/
│   │       ├── equipment/
│   │       └── fittings/
│   │
│   ├── pid_model/                 # Semantic object model
│   │   ├── base.py
│   │   ├── equipment.py
│   │   ├── nozzle.py
│   │   ├── piping.py
│   │   ├── valve.py
│   │   ├── instrument.py
│   │   ├── signal.py
│   │   ├── logic.py
│   │   └── termination.py
│   │
│   ├── connectivity/
│   │   ├── ports.py
│   │   ├── connections.py
│   │   ├── netlist.py
│   │   ├── junctions.py
│   │   └── connection_rules.py
│   │
│   ├── validation/
│   │   ├── schema_validator.py
│   │   ├── port_validator.py
│   │   ├── topology_validator.py
│   │   ├── piping_validator.py
│   │   ├── instrument_validator.py
│   │   ├── loop_validator.py
│   │   └── cad_semantic_validator.py
│   │
│   ├── layout/
│   │   ├── placement.py
│   │   ├── nozzle_placement.py
│   │   ├── routing.py
│   │   └── annotation.py
│   │
│   ├── renderers/
│   │   └── dxf/
│   │       ├── block_loader.py
│   │       ├── equipment_renderer.py
│   │       ├── piping_renderer.py
│   │       ├── signal_renderer.py
│   │       └── renderer.py
│   │
│   ├── adapters/
│   │   ├── dexpi/                 # DEXPI compatibility layer
│   │   └── legacy_yaml/           # Migration from old YAML format
│   │
│   └── tests/
│       ├── symbols/
│       ├── connectivity/
│       ├── validation/
│       ├── rendering/
│       └── golden/
│
└── libreCAD_blocks/               # Existing CAD block library (read-only during migration)
```

## Development Sequence

### STEP 0: Existing Repository Audit ✓
**Status:** COMPLETE
- Documented current architecture
- Inventoried 684 CAD blocks
- Identified connectivity gaps

### STEP 1: Canonical CAD Symbol Library
**Task:** Create normalized CAD block library with qualification tests

**Actions:**
1. Copy required blocks from `libreCAD_blocks/` to `pid_platform/symbols/cad/`
2. Normalize each block:
   - Origin at insertion point
   - Entities on layer 0
   - Consistent scale (mm)
   - Remove extraneous geometry
3. Create block qualification script

**Deliverable:** `python -m pid_platform.symbols qualify symbols/cad`

### STEP 2: Symbol Metadata Registry
**Task:** Add semantic metadata to each CAD block

**Schema Example:**
```yaml
symbol_id: ISA_FIELD_INSTRUMENT
category: instrument
subclass: field_instrument

cad:
  file: instruments/field_instrument.dxf
  block_name: ISA_FIELD_INSTRUMENT
  insertion_origin: [0, 0]
  nominal_width: 12
  nominal_height: 12

ports:
  - id: process
    domain: process_measurement
    anchor: [0, -6]
    direction: south
  - id: signal
    domain: instrument_signal
    anchor: [6, 0]
    direction: east

standard:
  family: ISA-5.1
```

**Deliverable:** YAML metadata files for all canonical symbols

### STEP 3: PID Object Model
**Task:** Create semantic object classes independent of CAD

**Classes:**
- `PIDObject` (base)
- `Equipment` → `Vessel`, `Column`, `Pump`, `Compressor`, `HeatExchanger`
- `Nozzle`
- `PipingComponent` → `PipeSegment`, `ManualValve`, `CheckValve`, `ControlValve`, etc.
- `Instrument` → `Sensor`, `Transmitter`, `Indicator`, `Controller`, etc.
- `LogicFunction`
- `Junction`
- `OffPageConnector`

**Deliverable:** `pid_model/*.py` with Pydantic/dataclass definitions

### STEP 4: Port Model
**Task:** Define typed ports with domains and constraints

**Port Domains:**
- `ProcessPort` - fluid/gas flow
- `MeasurementPort` - process sensing
- `SignalPort` - instrument signals (electric, pneumatic, etc.)
- `MechanicalPort` - mechanical linkages
- `CommunicationPort` - data links

**Deliverable:** `connectivity/ports.py` with port type hierarchy

### STEP 5: Netlist + Connection API
**Task:** Build graph-based connectivity model

**API Example:**
```python
v101 = Vessel(tag="V-101")
n1 = v101.add_nozzle(name="N1", role="process_outlet")

xv101 = ManualValve(tag="XV-101")

connect(
    v101.port("N1"),
    xv101.port("process_in"),
)
```

**Deliverable:** `connectivity/netlist.py`, `connectivity/connections.py`

### STEP 6: Schema/Port Validation
**Task:** Validate object structure and port compatibility

**Rules:**
- ProcessPort → ProcessPort: ✓
- ProcessPort → SignalPort: ✗
- Transmitter.measurement_out → Controller.PV_in: ✓
- Transmitter.measurement_out → Valve.process_in: ✗

**Deliverable:** `validation/schema_validator.py`, `validation/port_validator.py`

### STEP 7: Piping Topology Validation
**Task:** Validate process network continuity

**Checks:**
- Loose/orphan pipes
- Unconnected nozzles
- Invalid branches
- Missing off-page connectors

**Deliverable:** `validation/piping_validator.py`, `validation/topology_validator.py`

### STEP 8: Instrumentation/Signal Validation
**Task:** Validate instrument loops and signal paths

**Checks:**
- Complete measurement loops (sensor → transmitter → controller)
- Complete control loops (controller → final element)
- Signal type consistency
- Direction validation

**Deliverable:** `validation/instrument_validator.py`, `validation/loop_validator.py`

### STEP 9: Minimal Semantic-Only Validation Rigs
**Task:** Create test fixtures without CAD rendering

**Fixtures:**
- Single pipe between vessels
- Valve between pipes
- Branch tee
- Pump suction/discharge
- PT measurement
- PID control loop
- Cascade loop
- SIS trip
- Off-page connection

**Deliverable:** `tests/golden/` with valid and corrupted versions

### STEP 10: Semantic → CAD Renderer Adapter
**Task:** Connect semantic model to existing CAD backend

**Mapping:**
```python
semantic_object.uuid → CAD_block.semantic_uuid
semantic_port.anchor → CAD_insertion + local_offset → world_coordinate
```

**Deliverable:** `renderers/dxf/renderer.py` consuming semantic model

### STEP 11: Exact-Port Pipe Routing
**Task:** Route pipes between exact semantic port coordinates

**Change from:**
```python
route_line(start=(230, 165), end=(385, 200))
```

**To:**
```python
route_line(
    source_port="V501.N2",
    target_port="E501.N1"
)
```

**Deliverable:** `layout/routing.py` with port-aware routing

### STEP 12: Exact-Port Signal Routing
**Task:** Route instrument signals between exact semantic port coordinates

**Deliverable:** `layout/routing.py` extended for signal lines

### STEP 13: CAD → Connectivity Verification
**Task:** Extract connectivity from rendered DXF and compare to semantic model

**Checks:**
- Block present with correct UUID
- Port anchor at expected coordinate
- Polyline endpoint matches port exactly
- Signal endpoint matches port exactly

**Deliverable:** `validation/cad_semantic_validator.py`

### STEP 14: Complete Objective-1 Qualification Suite
**Task:** Run all validation checks against golden fixtures

**Gate:** All 20 success criteria must pass

## Skills Required for Qwen Coder

### Skill 1: repo-orientation
- Repository architecture
- Authoritative folders
- Legacy folders
- Test commands

### Skill 2: isa-symbol-engineering
- ISA instrument families
- Tagging semantics
- Line/signal categories
- Final control elements
- Logic symbols

### Skill 3: cad-symbol-audit
- Inspect DXF block
- Calculate bounding box
- Inspect layers
- Find insertion origin
- Report issues

### Skill 4: cad-symbol-normalization
- Standardize origin
- Standardize layer 0
- Standardize naming
- Preserve geometry

### Skill 5: symbol-semanticization
- Create YAML metadata from DXF
- Define port anchors
- Map to ISA standard

### Skill 6: pid-object-model
- Equipment classes
- Nozzle definitions
- Valve types
- Instrument classes
- Connection rules

### Skill 7: pid-netlist
- Create graph
- Connect/disconnect ports
- Branch nets
- Trace connectivity

### Skill 8: port-type-checker
- Allowed connections
- Multiplicity
- Direction
- Domain validation

### Skill 9: piping-topology-validator
- Loose lines
- Dangling pipes
- Orphan valves
- Invalid branches

### Skill 10: instrument-loop-validator
- Process sensing connection
- Transmitter → controller
- Controller → final element
- Loop identity

### Skill 11: semantic-cad-renderer
- Consume semantic model
- Place CAD blocks
- Route lines to exact ports

### Skill 12: cad-connectivity-verifier
- Read DXF
- Extract connectivity
- Compare to semantic model

### Skill 13: golden-fixture-testing
- Maintain reference models
- Valid examples
- Corrupted examples

## Immediate Next Actions

1. **Create `pid_platform/` directory structure**
2. **Define symbol metadata schema** (YAML format)
3. **Build first semantic object model** (Equipment, Nozzle, Port)
4. **Create minimal netlist example** (V-101 → XV-101 → P-101)
5. **Write validation tests** for the minimal example
6. **Do NOT modify existing deethanizer generator yet**

## Key Principles

1. **Coordinates answer "where", not "what connects"**
2. **Semantic model is authoritative; DXF is rendered output**
3. **Validation happens before rendering**
4. **AI authors engineering model, not drawing**
5. **Deterministic software proves correctness**
6. **Reusability over special-case code**

## References

- ISA-5.1: Instrumentation Symbols and Identification
- DEXPI/PDEXPI: Data exchange standard for P&IDs
- pyDEXPI: Python implementation of DEXPI
- Electronic Design Automation (EDA) netlist concepts
- Compiler theory (AST → IR → backend)
