# P&ID Approved Symbol Library Location Guide

## Overview

This document describes the location and organization of all approved P&ID symbol blocks used by the `pid-symbol-standard` skill. 

**CRITICAL RULE**: Every P&ID component MUST come from an approved block/symbol library. No renderer or generator may invent, approximate, or draw a substitute symbol using primitive CAD geometry.

---

## Block Library Locations

All approved DXF blocks are located in `/workspace/libreCAD_blocks/` organized by category:

### 1. ISA-5.1 Instrumentation Symbols
**Location**: `/workspace/libreCAD_blocks/ISO Instruments/`

| Block File | Description | ISA-5.1 Category |
|------------|-------------|------------------|
| `3_field-discrete-instrument.dxf` | Field-mounted instruments (no line) | Field/Local |
| `6_primary-accessible-discrete-instrument.dxf` | Panel-mounted instruments (single line) | Primary Accessible |
| `0_aux-accessible-discrete-instrument.dxf` | Auxiliary accessible instruments | Auxiliary Accessible |
| `4_field-dcs.dxf` | Field DCS/PLC instruments | Field DCS |
| `5_field-plc.dxf` | Field PLC instruments | Field PLC |
| `7_primary-accessible-dcs.dxf` | Primary accessible DCS | Primary DCS |
| `8_primary-accessible-plc.dxf` | Primary accessible PLC | Primary PLC |
| `1_aux-accessible-dcs.dxf` | Auxiliary accessible DCS | Auxiliary DCS |
| `2_aux-accessible-plc.dxf` | Auxiliary accessible PLC | Auxiliary PLC |
| `9_restriction-orifice.dxf` | Restriction orifice | Flow Element |
| `10_turbine.dxf` | Turbine meter | Flow Meter |
| `11_flow-nozzle.dxf` | Flow nozzle | Flow Element |
| `12_venturi.dxf` | Venturi meter | Flow Element |
| `13_rotameter.dxf` | Rotameter | Flow Meter |
| `14_volume-meter.dxf` | Volume meter | Flow Meter |
| `15_flow-element.dxf` | General flow element | Flow Element |

**Standards Compliance**: ANSI/ISA-5.1-2009

---

### 2. Valve Symbols
**Location**: `/workspace/libreCAD_blocks/ISO Valves/`

| Block File | Description |
|------------|-------------|
| `0_general-valve-no.dxf` | General valve (normally open) |
| `1_general-valve-nc.dxf` | General valve (normally closed) |
| `2_angle-valve.dxf` | Angle valve |
| `3_globe-valve-nc.dxf` | Globe valve (NC) |
| `4_globe-valve-no.dxf` | Globe valve (NO) |
| `5_ball-valve-no.dxf` | Ball valve (NO) |
| `6_ball-valve-nc.dxf` | Ball valve (NC) |
| `7_butterfly-valve.dxf` | Butterfly valve |
| `8_gate-valve-no.dxf` | Gate valve (NO) |
| `9_gate-valve-nc.dxf` | Gate valve (NC) |
| `10_angle-ball-valve.dxf` | Angle ball valve |
| `11_angle-globe-valve.dxf` | Angle globe valve |
| `12_3-way-valve.dxf` | 3-way valve |
| `13_3-way-ball-valve.dxf` | 3-way ball valve |
| `14_3-way-globe-valve.dxf` | 3-way globe valve |
| `15_check-valve.dxf` | Check valve |
| `16_breather-valve.dxf` | Breather valve |
| `17_swing-check-valve.dxf` | Swing check valve |
| `18_lift-check-valve.dxf` | Lift check valve |
| `19_safety-valve.dxf` | Safety valve |
| `20_angle-safety-valve.dxf` | Angle safety valve |
| `21_angle-spring-safety-valve.dxf` | Angle spring safety valve |
| `22_control-valve.dxf` | Control valve with actuator |
| `23_continuously-operated-valve.dxf` | Continuously operated valve |

---

### 3. Equipment Symbols (Project-Approved)
**Location**: `/workspace/libreCAD_blocks/ISO Equipments/`

| Block File | Description |
|------------|-------------|
| `0_tank-general-basin.dxf` | General tank/basin |
| `1_tank-floating-roof.dxf` | Floating roof tank |
| `2_vessel_general-column.dxf` | Column/tower |
| `10_vessel-full-tube-coil.dxf` | Vessel with full tube coil |
| `11_vessel-semi-tube-coil.dxf` | Vessel with semi tube coil |
| `12_vessel-jacketed.dxf` | Jacketed vessel |
| `13_storage-container.dxf` | Storage container |
| `14_storage-bag.dxf` | Storage bag |
| `15_storage-barrel-drum.dxf` | Barrel/drum |
| `16_storage-gas-cylinder.dxf` | Gas cylinder |
| `17_furnace-industrial.dxf` | Industrial furnace |
| `18_pump.dxf` | Pump (centrifugal/PD) |
| `19_compressor.dxf` | Compressor |
| `20_blower.dxf` | Blower |
| `21_heat-exchanger-general-1.dxf` | Heat exchanger (general) |
| `22_heat-exchanger-general-2.dxf` | Heat exchanger (alt) |
| `23_heat-exchanger-general-cooling-tower.dxf` | Cooling tower |
| `24-30_heat-exchanger-*.dxf` | Various heat exchanger types |

---

### 4. P&ID Specific Symbols
**Location**: `/workspace/libreCAD_blocks/P&ID/`

Contains additional instrument and valve symbols for P&ID-specific use cases.

---

## Symbol Registry Mapping

The canonical symbol registry is defined in:
**`/workspace/pid_platform/standards/pid_symbol_registry.py`**

Key mappings:

### Instrumentation (ISA-5.1)
```python
"field_instrument" → "libreCAD_blocks/ISO Instruments/3_field-discrete-instrument.dxf"
"transmitter" → "libreCAD_blocks/ISO Instruments/3_field-discrete-instrument.dxf"
"panel_instrument" → "libreCAD_blocks/ISO Instruments/6_primary-accessible-discrete-instrument.dxf"
"controller" → "libreCAD_blocks/ISO Instruments/6_primary-accessible-discrete-instrument.dxf"
"indicator" → "libreCAD_blocks/ISO Instruments/6_primary-accessible-discrete-instrument.dxf"
"switch" → "libreCAD_blocks/ISO Instruments/3_field-discrete-instrument.dxf"
```

### Valves
```python
"manual_valve" → "libreCAD_blocks/ISO Valves/0_general-valve-no.dxf"
"control_valve" → "libreCAD_blocks/ISO Valves/22_control-valve.dxf"
"check_valve" → "libreCAD_blocks/ISO Valves/15_check-valve.dxf"
```

### Equipment (Project-Approved)
```python
"vessel" → "libreCAD_blocks/ISO Equipments/0_tank-general-basin.dxf"
"pump" → "libreCAD_blocks/ISO Equipments/18_pump.dxf"
"compressor" → "libreCAD_blocks/ISO Equipments/19_compressor.dxf"
"heat_exchanger" → "libreCAD_blocks/ISO Equipments/21_heat-exchanger-general-1.dxf"
```

### Junctions & Special
```python
"junction_tee" → "libreCAD_blocks/P&ID/junction-tee.dxf"
"junction_cross" → "libreCAD_blocks/P&ID/junction-cross.dxf"
"off_page_connector" → "libreCAD_blocks/P&ID/off-page-connector.dxf"
"termination_point" → "libreCAD_blocks/P&ID/termination-point.dxf"
```

---

## Usage

### Resolving Symbols Programmatically

```python
from pid_platform.standards.pid_symbol_registry import resolve_symbol, SymbolResolver

resolver = SymbolResolver()

# Resolve by component type
entry = resolver.resolve("vessel")
print(f"Block: {entry.block_name}")
print(f"Source: {entry.block_source}")
print(f"Ports: {entry.get_port_ids()}")

# Resolve by alias
entry = resolver.resolve("tank")  # Alias for vessel
```

### Using in DXF Renderer

```python
from pid_platform.cad.adapter import SemanticCADAdapter
from pid_platform.renderers.dxf.renderer import DXFRenderer

adapter = SemanticCADAdapter()
renderer = DXFRenderer(adapter)

# Place component (automatically resolves to approved symbol)
vessel = Vessel(tag="V-101")
rendered = adapter.place_component(vessel, (0, 0))

# Render as approved block insert
renderer.create_document()
renderer.render_component(rendered)
renderer.save("output.dxf")
```

---

## Error Handling

If a symbol cannot be resolved, the system raises:

```python
SymbolResolutionError: UNRESOLVED_APPROVED_PID_SYMBOL
```

**No fallback to primitive geometry occurs.** Generation fails explicitly.

---

## Verification

Run the completion gate test to verify all components use approved symbols:

```bash
cd /workspace
PYTHONPATH=/workspace:$PYTHONPATH python pid_platform/tests/test_approved_symbol_library.py
```

Expected output:
```
PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE: PASSED
  - Every component resolves to an approved block
  - Zero unauthorized substitute symbols
  - Explicit failure on unresolved symbols
  - No primitive geometry fallback paths
```

---

## Adding New Symbols

To add a new approved symbol:

1. Add the DXF block file to the appropriate directory under `/workspace/libreCAD_blocks/`
2. Register it in `SYMBOL_REGISTRY` in `/workspace/pid_platform/standards/pid_symbol_registry.py`:

```python
_register_symbol(SymbolEntry(
    symbol_id="new_symbol_id",
    category=SymbolCategory.YOUR_CATEGORY,
    standards_body=StandardsBody.ISA,  # or PROJECT
    block_name="YOUR_BLOCK_NAME",
    block_source="libreCAD_blocks/YOUR_PATH/your-block.dxf",
    nominal_width=20.0,
    nominal_height=20.0,
    port_definitions=frozenset({PROCESS_IN, PROCESS_OUT}),
    aliases=frozenset({"alias1", "alias2"})
))
```

3. Run the completion gate test to verify

---

## Standards References

- **ANSI/ISA-5.1-2009**: Instrumentation Symbols and Identification
- **Project-Approved Library**: Custom equipment symbols for vessels, pumps, compressors, exchangers

---

## File Statistics

- Total DXF blocks: ~684 files
- ISA Instruments: 16 files
- ISO Valves: 24 files  
- ISO Equipments: 105 files
- P&ID specific: Multiple files

All blocks are pre-approved and must be used exclusively—no runtime geometry generation permitted.
