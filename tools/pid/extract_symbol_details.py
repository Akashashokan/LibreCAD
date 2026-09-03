#!/usr/bin/env python3
"""
Extract symbol details from DXF block files and generate a comprehensive JSON file.
This script analyzes all P&ID symbols used in the rendering system.
"""

import json
import math
from pathlib import Path
from typing import Any

import ezdxf


def extract_entity_details(entity) -> dict[str, Any]:
    """Extract detailed geometry information from a DXF entity."""
    dxftype = entity.dxftype()
    details = {"type": dxftype, "layer": str(entity.dxf.get("layer", "0"))}

    try:
        if dxftype == "LINE":
            details["start"] = {
                "x": float(entity.dxf.start.x),
                "y": float(entity.dxf.start.y),
                "z": float(entity.dxf.start.z),
            }
            details["end"] = {
                "x": float(entity.dxf.end.x),
                "y": float(entity.dxf.end.y),
                "z": float(entity.dxf.end.z),
            }
            details["length"] = math.sqrt(
                (entity.dxf.end.x - entity.dxf.start.x) ** 2
                + (entity.dxf.end.y - entity.dxf.start.y) ** 2
            )

        elif dxftype == "CIRCLE":
            details["center"] = {
                "x": float(entity.dxf.center.x),
                "y": float(entity.dxf.center.y),
                "z": float(entity.dxf.center.z),
            }
            details["radius"] = float(entity.dxf.radius)
            details["diameter"] = float(entity.dxf.radius) * 2

        elif dxftype == "ARC":
            details["center"] = {
                "x": float(entity.dxf.center.x),
                "y": float(entity.dxf.center.y),
                "z": float(entity.dxf.center.z),
            }
            details["radius"] = float(entity.dxf.radius)
            details["start_angle"] = float(entity.dxf.start_angle)
            details["end_angle"] = float(entity.dxf.end_angle)
            # Calculate arc length
            angle_span = abs(entity.dxf.end_angle - entity.dxf.start_angle)
            if angle_span > 180:
                angle_span = 360 - angle_span
            details["arc_length"] = math.radians(angle_span) * float(entity.dxf.radius)

        elif dxftype == "ELLIPSE":
            details["center"] = {
                "x": float(entity.dxf.center.x),
                "y": float(entity.dxf.center.y),
                "z": float(entity.dxf.center.z),
            }
            details["major_axis"] = {
                "x": float(entity.dxf.major_axis.x),
                "y": float(entity.dxf.major_axis.y),
            }
            details["ratio"] = float(entity.dxf.ratio)
            details["start_param"] = float(entity.dxf.start_param)
            details["end_param"] = float(entity.dxf.end_param)

        elif dxftype in ("LWPOLYLINE", "POLYLINE"):
            points = []
            if dxftype == "LWPOLYLINE":
                for point in entity.get_points():
                    points.append({"x": float(point[0]), "y": float(point[1])})
            else:
                for vertex in entity.vertices:
                    points.append(
                        {"x": float(vertex.dxf.location.x), "y": float(vertex.dxf.location.y)}
                    )
            details["points"] = points
            details["vertex_count"] = len(points)
            details["closed"] = bool(entity.closed)

        elif dxftype == "INSERT":
            details["block_name"] = str(entity.dxf.name)
            details["insert_point"] = {
                "x": float(entity.dxf.insert.x),
                "y": float(entity.dxf.insert.y),
                "z": float(entity.dxf.insert.z),
            }
            details["scale"] = {
                "x": float(entity.dxf.xscale),
                "y": float(entity.dxf.yscale),
                "z": float(entity.dxf.zscale),
            }
            details["rotation"] = float(entity.dxf.rotation)

        elif dxftype in ("TEXT", "MTEXT"):
            details["text"] = str(entity.dxf.text)
            details["insert_point"] = {
                "x": float(entity.dxf.insert.x),
                "y": float(entity.dxf.insert.y),
                "z": float(entity.dxf.insert.z),
            }
            details["height"] = float(entity.dxf.get("height", 1.0))
            if dxftype == "TEXT":
                details["rotation"] = float(entity.dxf.get("rotation", 0))

        elif dxftype == "POINT":
            details["location"] = {
                "x": float(entity.dxf.location.x),
                "y": float(entity.dxf.location.y),
                "z": float(entity.dxf.location.z),
            }

        elif dxftype == "SPLINE":
            control_points = []
            for point in entity.control_points:
                control_points.append({"x": float(point[0]), "y": float(point[1]), "z": float(point[2])})
            details["control_points"] = control_points
            details["degree"] = int(entity.dxf.degree)
            details["closed"] = bool(entity.closed)

        else:
            details["note"] = f"Entity type {dxftype} not fully detailed"

    except Exception as e:
        details["error"] = str(e)

    return details


def extract_block_details(dxf_path: Path) -> dict[str, Any]:
    """Extract all geometry details from a DXF file's block or modelspace."""
    result = {
        "file_path": str(dxf_path.absolute()),
        "file_name": dxf_path.name,
        "entities": [],
        "summary": {},
    }

    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        result["error"] = f"Failed to read DXF file: {str(e)}"
        return result

    # Check if there are blocks defined
    blocks_info = {}
    for block_name in doc.blocks:
        # block_name is already a BlockLayout object when iterating
        block = block_name if hasattr(block_name, 'name') else doc.blocks[block_name]
        name = block.name if hasattr(block, 'name') else str(block_name)
        entities = []
        for entity in block:
            entities.append(extract_entity_details(entity))

        blocks_info[name] = {
            "name": name,
            "entity_count": len(entities),
            "entities": entities,
        }

    result["blocks"] = blocks_info

    # Also check modelspace if no blocks or in addition to blocks
    modelspace_entities = []
    for entity in doc.modelspace():
        modelspace_entities.append(extract_entity_details(entity))

    result["modelspace"] = {
        "entity_count": len(modelspace_entities),
        "entities": modelspace_entities,
    }

    # Generate summary statistics
    entity_counts = {}
    layers_used = set()
    for block_name, block_data in blocks_info.items():
        for entity in block_data["entities"]:
            etype = entity.get("type", "UNKNOWN")
            entity_counts[etype] = entity_counts.get(etype, 0) + 1
            if "layer" in entity:
                layers_used.add(entity["layer"])

    for entity in modelspace_entities:
        etype = entity.get("type", "UNKNOWN")
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
        if "layer" in entity:
            layers_used.add(entity["layer"])

    result["summary"] = {
        "total_blocks": len(blocks_info),
        "block_names": list(blocks_info.keys()),
        "total_entities_in_blocks": sum(b["entity_count"] for b in blocks_info.values()),
        "modelspace_entity_count": len(modelspace_entities),
        "entity_type_counts": entity_counts,
        "layers_used": sorted(list(layers_used)),
    }

    return result


def collect_all_symbol_files(base_dir: Path) -> dict[str, list[Path]]:
    """Collect all DXF files organized by category."""
    categories = {
        "instruments": base_dir / "ISO Instruments",
        "valves": base_dir / "ISO Valves",
        "equipments": base_dir / "ISO Equipments",
        "piping": base_dir / "ISO Pipes and Signal Lines",
        "fittings": base_dir / "ISO Fittings",
    }

    result = {}
    for category, path in categories.items():
        if path.exists():
            result[category] = sorted(path.glob("*.dxf"))
        else:
            result[category] = []

    return result


def main():
    base_dir = Path("/workspace/libreCAD_blocks")
    output_file = Path("/workspace/tools/pid/symbol_details.json")

    print("Collecting symbol files...")
    symbol_files = collect_all_symbol_files(base_dir)

    all_symbols = {}

    for category, files in symbol_files.items():
        print(f"\nProcessing {category}: {len(files)} files")
        all_symbols[category] = {}

        for dxf_file in files:
            print(f"  Extracting: {dxf_file.name}")
            details = extract_block_details(dxf_file)
            symbol_key = dxf_file.stem  # filename without extension
            all_symbols[category][symbol_key] = details

    # Create final JSON structure
    output_data = {
        "metadata": {
            "description": "P&ID Symbol Details extracted from DXF block files",
            "base_directory": str(base_dir),
            "total_categories": len(all_symbols),
            "total_symbols": sum(len(symbols) for symbols in all_symbols.values()),
        },
        "symbols_by_category": all_symbols,
    }

    # Write to JSON file
    print(f"\nWriting JSON output to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nExtraction complete!")
    print(f"Total symbols processed: {output_data['metadata']['total_symbols']}")
    print(f"Output file: {output_file}")

    return output_data


if __name__ == "__main__":
    main()
