import json
import sys
sys.path.insert(0, '/workspace')

from pid_platform.standards.pid_symbol_registry import SYMBOL_REGISTRY
from ezdxf import readfile
from pathlib import Path

def get_dxf_path(block_name):
    block_map = {
        'PIP_FIELD_INSTRUMENT': 'instruments.dxf',
        'PIP_MAIN_INSTRUMENT': 'instruments.dxf',
        'PIP_SHARED_INSTRUMENT': 'instruments.dxf',
        'PIP_PC_LINK': 'instruments.dxf',
        'PIP_BINARY_SIGNAL': 'instruments.dxf',
        'PIP_CAPILLARY': 'instruments.dxf',
        'PIP_ELECTRIC_SIGNAL': 'instruments.dxf',
        'PIP_PNEU_SIGNAL': 'instruments.dxf',
        'PIP_HYD_SIGNAL': 'instruments.dxf',
        'PIP_SOFTWARE_FUNC': 'instruments.dxf',
        'PIP_COMMON_DISPLAY': 'instruments.dxf',
        'PIP_ACCESSORY': 'instruments.dxf',
        'PIP_VALVE_MANUAL': 'valves.dxf',
        'PIP_VALVE_CONTROL': 'valves.dxf',
        'PIP_VALVE_SOLENOID': 'valves.dxf',
        'PIP_VALVE_DIAPHRAGM': 'valves.dxf',
        'PIP_VALVE_PINCH': 'valves.dxf',
        'PIP_VALVE_SLIDE': 'valves.dxf',
        'PIP_VALVE_ROTARY': 'valves.dxf',
        'PIP_VALVE_CHECK': 'valves.dxf',
        'PIP_VALVE_RELIEF': 'valves.dxf',
        'PIP_VALVE_BREAKER': 'valves.dxf',
        'PIP_EQUIPMENT': 'equipment.dxf',
        'PIP_PUMP': 'equipment.dxf',
        'PIP_COMPRESSOR': 'equipment.dxf',
        'PIP_TURBINE': 'equipment.dxf',
        'PIP_HEAT_EXCHANGER': 'equipment.dxf',
        'PIP_TOWER': 'equipment.dxf',
        'PIP_VESSEL': 'equipment.dxf',
        'PIP_REACTOR': 'equipment.dxf',
        'PIP_DRYER': 'equipment.dxf',
        'PIP_FILTER': 'equipment.dxf',
        'PIP_PIPE': 'piping.dxf',
        'PIP_PIPE_HIDDEN': 'piping.dxf',
        'PIP_PIPE_INSULATED': 'piping.dxf',
        'PIP_PIPE_TRACED': 'piping.dxf',
        'PIP_PIPE_SLEEVED': 'piping.dxf',
        'PIP_PIPE_EXPANSION': 'piping.dxf',
        'PIP_FLANGE_WN': 'fittings.dxf',
        'PIP_FLANGE_SO': 'fittings.dxf',
        'PIP_FLANGE_BLIND': 'fittings.dxf',
        'PIP_FLANGE_LJ': 'fittings.dxf',
        'PIP_FLANGE_SW': 'fittings.dxf',
        'PIP_FLANGE_THREADED': 'fittings.dxf',
        'PIP_ELBO_90': 'fittings.dxf',
        'PIP_ELBO_45': 'fittings.dxf',
        'PIP_TEE': 'fittings.dxf',
        'PIP_CROSS': 'fittings.dxf',
        'PIP_REDUCER_CONC': 'fittings.dxf',
        'PIP_REDUCER_ECC': 'fittings.dxf',
        'PIP_CAP': 'fittings.dxf',
        'PIP_UNION': 'fittings.dxf',
        'PIP_NIPPLE': 'fittings.dxf',
        'PIP_OLET': 'fittings.dxf',
        'PIP_STRAINER': 'fittings.dxf',
        'PIP_SIGHT_GLASS': 'fittings.dxf',
        'PIP_SPARG': 'fittings.dxf',
        'PIP_STATIC_MIXER': 'fittings.dxf',
    }
    base_path = Path('/workspace/pid_platform/cad/blocks')
    if block_name in block_map:
        return base_path / block_map[block_name]
    return None

def extract_block_geometry(dxf_path, block_name):
    if not dxf_path or not dxf_path.exists():
        return {"error": f"DXF file not found: {dxf_path}"}
    try:
        doc = readfile(str(dxf_path))
        blocks = doc.blocks
        if block_name not in blocks:
            return {"error": f"Block {block_name} not found in {dxf_path}"}
        block = blocks[block_name]
        geometry = {
            "block_name": block_name,
            "base_point": list(block.base_point),
            "entities": []
        }
        for entity in block:
            entity_data = {
                "type": entity.dxftype(),
                "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else None,
                "color": entity.dxf.color if hasattr(entity.dxf, 'color') else None,
                "linetype": entity.dxf.linetype if hasattr(entity.dxf, 'linetype') else None,
            }
            if entity.dxftype() == 'LINE':
                entity_data.update({"start": list(entity.dxf.start), "end": list(entity.dxf.end)})
            elif entity.dxftype() == 'CIRCLE':
                entity_data.update({"center": list(entity.dxf.center), "radius": entity.dxf.radius})
            elif entity.dxftype() == 'ARC':
                entity_data.update({"center": list(entity.dxf.center), "radius": entity.dxf.radius, "start_angle": entity.dxf.start_angle, "end_angle": entity.dxf.end_angle})
            elif entity.dxftype() == 'ELLIPSE':
                entity_data.update({"center": list(entity.dxf.center), "major_axis": list(entity.dxf.major_axis), "ratio": entity.dxf.ratio, "start_param": entity.dxf.start_param, "end_param": entity.dxf.end_param})
            elif entity.dxftype() == 'LWPOLYLINE':
                points = [list(pt) for pt in entity.get_points()]
                entity_data.update({"points": points, "closed": entity.closed})
            elif entity.dxftype() == 'POLYLINE':
                points = [list(vtx.dxf.location) for vtx in entity.vertices]
                entity_data.update({"points": points, "closed": entity.is_closed})
            elif entity.dxftype() == 'INSERT':
                entity_data.update({"block_name": entity.dxf.name, "insert": list(entity.dxf.insert), "scale": list(entity.dxf.scale), "rotation": entity.dxf.rotation})
            elif entity.dxftype() in ('TEXT', 'MTEXT'):
                entity_data.update({"text": entity.dxf.text, "insert": list(entity.dxf.insert), "height": entity.dxf.height, "rotation": entity.dxf.rotation})
            elif entity.dxftype() == 'POINT':
                entity_data.update({"location": list(entity.dxf.location)})
            elif entity.dxftype() == 'SPLINE':
                control_points = [list(pt) for pt in entity.control_points]
                fit_points = [list(pt) for pt in entity.fit_points] if entity.has_fit_points else []
                entity_data.update({"control_points": control_points, "fit_points": fit_points, "degree": entity.dxf.degree})
            geometry["entities"].append(entity_data)
        return geometry
    except Exception as e:
        return {"error": str(e)}

full_library = {"metadata": {"description": "Complete P&ID Symbol Library with Full Geometric Construction Data", "standards": "ISA-5.1 compliant", "total_symbols": len(SYMBOL_REGISTRY)}, "symbols": []}
processed_blocks = set()

for symbol_id, symbol_data in SYMBOL_REGISTRY.items():
    block_name = symbol_data.block_name
    if block_name not in processed_blocks:
        dxf_path = get_dxf_path(block_name)
        geometry_data = extract_block_geometry(dxf_path, block_name)
        block_entry = {"block_name": block_name, "dxf_source": str(dxf_path) if dxf_path else None, "used_by_symbols": [], "geometry": geometry_data}
        processed_blocks.add(block_name)
    else:
        for entry in full_library["symbols"]:
            if entry["block_name"] == block_name:
                block_entry = entry
                break
    ports_list = [{"port_id": port.port_id, "domain": port.domain, "direction": port.direction, "description": port.description} for port in symbol_data.port_definitions]
    block_entry["used_by_symbols"].append({"symbol_id": symbol_id, "category": str(symbol_data.category), "ports": ports_list})
    if not any(b["block_name"] == block_name for b in full_library["symbols"]):
        full_library["symbols"].append(block_entry)

output_path = '/workspace/full_pid_symbol_geometry.json'
with open(output_path, 'w') as f:
    json.dump(full_library, f, indent=2)

print(f"Created {output_path}")
print(f"Total unique blocks: {len(processed_blocks)}")
print(f"Total symbol references: {len(SYMBOL_REGISTRY)}")
import os
file_size = os.path.getsize(output_path)
print(f"File size: {file_size / 1024:.2f} KB ({file_size / (1024*1024):.2f} MB)")
