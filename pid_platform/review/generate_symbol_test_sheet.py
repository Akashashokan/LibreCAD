#!/usr/bin/env python3
"""
P&ID Approved Symbol Test Sheet Generator

This script generates a single DXF page containing all approved P&ID blocks
with labels and port markers for human review.

Outputs:
- approved_symbol_test_sheet.dxf (single DXF with all symbols arranged in grid)
- approved_symbol_test_sheet.md (markdown documentation)

Usage:
    python generate_symbol_test_sheet.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict

# Add workspace to path
sys.path.insert(0, '/workspace')

from pid_platform.standards.pid_symbol_registry import (
    SYMBOL_REGISTRY,
    SymbolEntry,
    SymbolCategory,
    StandardsBody,
    SymbolResolver,
)


def get_category_sort_key(category: SymbolCategory) -> int:
    """Sort categories in review order: instruments, valves, equipment, junctions, special"""
    order = {
        SymbolCategory.INSTRUMENT_BUBBLE: 1,
        SymbolCategory.TRANSMITTER: 2,
        SymbolCategory.CONTROLLER: 3,
        SymbolCategory.INDICATOR: 4,
        SymbolCategory.SWITCH: 5,
        SymbolCategory.FINAL_CONTROL_ELEMENT: 6,
        SymbolCategory.ACTUATOR: 7,
        SymbolCategory.VALVE_FAILURE_INDICATION: 8,
        SymbolCategory.SIGNAL_LINE: 9,
        SymbolCategory.MANUAL_VALVE: 10,
        SymbolCategory.CONTROL_VALVE: 11,
        SymbolCategory.CHECK_VALVE: 12,
        SymbolCategory.SAFETY_RELIEF_VALVE: 13,
        SymbolCategory.VESSEL: 20,
        SymbolCategory.COLUMN: 21,
        SymbolCategory.PUMP: 22,
        SymbolCategory.COMPRESSOR: 23,
        SymbolCategory.HEAT_EXCHANGER: 24,
        SymbolCategory.REACTOR: 25,
        SymbolCategory.TANK: 26,
        SymbolCategory.JUNCTION_TEE: 30,
        SymbolCategory.JUNCTION_CROSS: 31,
        SymbolCategory.FLANGE: 32,
        SymbolCategory.REDUCER: 33,
        SymbolCategory.OFF_PAGE_CONNECTOR: 40,
        SymbolCategory.TERMINATION_POINT: 41,
        SymbolCategory.WELD: 42,
    }
    return order.get(category, 99)


def copy_entities_from_source(doc, source_path: Path, insert_x: float, insert_y: float,
                              scale: float = 1.0, rotation: float = 0.0) -> bool:
    """Copy entities from source DXF to target document at specified location"""
    try:
        import ezdxf
        from math import radians, cos, sin
        
        source_doc = ezdxf.readfile(str(source_path))
        source_msp = source_doc.modelspace()
        target_msp = doc.modelspace()
        
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for entity in source_msp:
            try:
                bbox = entity.bbox()
                if bbox is not None:
                    min_x = min(min_x, bbox.extmin.x)
                    min_y = min(min_y, bbox.extmin.y)
                    max_x = max(max_x, bbox.extmax.x)
                    max_y = max(max_y, bbox.extmax.y)
            except:
                continue
        
        if min_x == float('inf'):
            min_x, min_y = -50, -50
            max_x, max_y = 50, 50
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        for entity in source_msp:
            try:
                dxftype = entity.dxftype()
                
                if dxftype == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    
                    sx = (start.x - center_x) * scale
                    sy = (start.y - center_y) * scale
                    rsx = sx * cos(radians(rotation)) - sy * sin(radians(rotation))
                    rsy = sx * sin(radians(rotation)) + sy * cos(radians(rotation))
                    new_start = (insert_x + rsx, insert_y + rsy, start.z)
                    
                    ex = (end.x - center_x) * scale
                    ey = (end.y - center_y) * scale
                    rex = ex * cos(radians(rotation)) - ey * sin(radians(rotation))
                    rey = ex * sin(radians(rotation)) + ey * cos(radians(rotation))
                    new_end = (insert_x + rex, insert_y + rey, end.z)
                    
                    target_msp.add_line(new_start, new_end, dxfattribs=entity.dxfattribs())
                    
                elif dxftype == 'CIRCLE':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    
                    cx = (center.x - center_x) * scale
                    cy = (center.y - center_y) * scale
                    rcx = cx * cos(radians(rotation)) - cy * sin(radians(rotation))
                    rcy = cx * sin(radians(rotation)) + cy * cos(radians(rotation))
                    new_center = (insert_x + rcx, insert_y + rcy, center.z)
                    
                    target_msp.add_circle(new_center, radius * scale, dxfattribs=entity.dxfattribs())
                    
                elif dxftype == 'ARC':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    start_angle = entity.dxf.start_angle
                    end_angle = entity.dxf.end_angle
                    
                    cx = (center.x - center_x) * scale
                    cy = (center.y - center_y) * scale
                    rcx = cx * cos(radians(rotation)) - cy * sin(radians(rotation))
                    rcy = cx * sin(radians(rotation)) + cy * cos(radians(rotation))
                    new_center = (insert_x + rcx, insert_y + rcy, center.z)
                    
                    target_msp.add_arc(
                        new_center,
                        radius * scale,
                        start_angle + rotation,
                        end_angle + rotation,
                        dxfattribs=entity.dxfattribs()
                    )
                    
                elif dxftype == 'TEXT' or dxftype == 'MTEXT':
                    insert_pt = entity.dxf.insert
                    text = entity.dxf.text if hasattr(entity.dxf, 'text') else str(entity)
                    
                    ix = (insert_pt.x - center_x) * scale
                    iy = (insert_pt.y - center_y) * scale
                    rix = ix * cos(radians(rotation)) - iy * sin(radians(rotation))
                    riy = ix * sin(radians(rotation)) + iy * cos(radians(rotation))
                    new_insert = (insert_x + rix, insert_y + riy, insert_pt.z)
                    
                    if dxftype == 'TEXT':
                        target_msp.add_text(text, dxfattribs={
                            'insert': new_insert,
                            'height': entity.dxf.height * scale if hasattr(entity.dxf, 'height') else 2.5,
                            'rotation': entity.dxf.rotation + rotation if hasattr(entity.dxf, 'rotation') else rotation,
                        })
                    else:
                        target_msp.add_mtext(text, dxfattribs={'insert': new_insert})
                    
                elif dxftype == 'POINT':
                    location = entity.dxf.location
                    lx = (location.x - center_x) * scale
                    ly = (location.y - center_y) * scale
                    rlx = lx * cos(radians(rotation)) - ly * sin(radians(rotation))
                    rly = lx * sin(radians(rotation)) + ly * cos(radians(rotation))
                    new_location = (insert_x + rlx, insert_y + rly, location.z)
                    
                    target_msp.add_point(new_location, dxfattribs=entity.dxfattribs())
                    
                elif dxftype == 'LWPOLYLINE' or dxftype == 'POLYLINE':
                    points = []
                    for pt in entity.get_points():
                        px = (pt[0] - center_x) * scale
                        py = (pt[1] - center_y) * scale
                        rpx = px * cos(radians(rotation)) - py * sin(radians(rotation))
                        rpy = px * sin(radians(rotation)) + py * cos(radians(rotation))
                        points.append((insert_x + rpx, insert_y + rpy, pt[2] if len(pt) > 2 else 0.0))
                    
                    if len(points) >= 2:
                        if dxftype == 'LWPOLYLINE':
                            pline = target_msp.add_lwpolyline(points, dxfattribs=entity.dxfattribs())
                            if entity.closed:
                                pline.closed = True
                        else:
                            pline = target_msp.add_polyline(points, dxfattribs=entity.dxfattribs())
                            if entity.closed:
                                pline.close()
                    
            except Exception as e:
                continue
        
        return True
        
    except Exception as e:
        print(f"  Error copying entities from {source_path}: {e}")
        return False


def add_label_and_ports(doc, insert_x: float, insert_y: float, cell_width: float,
                        symbol_id: str, category: str, index: int, ports: Optional[Dict] = None):
    """Add label and port markers below a symbol"""
    try:
        msp = doc.modelspace()
        
        label_y = insert_y - 40
        label_text = f"{index:03d} - {symbol_id}"
        
        msp.add_text(label_text, dxfattribs={
            'insert': (insert_x, label_y),
            'height': 3,
            'rotation': 0,
        })
        
        cat_y = label_y - 5
        cat_text = category.replace('_', ' ').title()[:20]
        msp.add_text(cat_text, dxfattribs={
            'insert': (insert_x, cat_y),
            'height': 2,
            'rotation': 0,
        })
        
        if ports:
            port_y = cat_y - 5
            port_text = f"Ports: {len(ports)}"
            msp.add_text(port_text, dxfattribs={
                'insert': (insert_x, port_y),
                'height': 2,
                'rotation': 0,
            })
            
            for idx, (port_name, port_data) in enumerate(list(ports.items())[:4]):
                port_x = insert_x - 15 + idx * 10
                port_marker_y = port_y - 5
                msp.add_circle((port_x, port_marker_y), 1.5, dxfattribs={'color': 1})
        
        border_y_top = insert_y + 50
        border_y_bottom = label_y - 25
        
        msp.add_line((insert_x - cell_width/2, border_y_top),
                     (insert_x + cell_width/2, border_y_top),
                     dxfattribs={'color': 8})
        msp.add_line((insert_x - cell_width/2, border_y_bottom),
                     (insert_x + cell_width/2, border_y_bottom),
                     dxfattribs={'color': 8})
        msp.add_line((insert_x - cell_width/2, border_y_top),
                     (insert_x - cell_width/2, border_y_bottom),
                     dxfattribs={'color': 8})
        msp.add_line((insert_x + cell_width/2, border_y_top),
                     (insert_x + cell_width/2, border_y_bottom),
                     dxfattribs={'color': 8})
        
    except Exception as e:
        print(f"  Error adding label: {e}")


def generate_test_sheet(output_dir: Path):
    """Generate the main test sheet DXF with all symbols"""
    try:
        import ezdxf
    except ImportError:
        print("Error: ezdxf library required. Install with: pip install ezdxf")
        return None
    
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    doc.layers.add('SYMBOLS', color=0)
    doc.layers.add('LABELS', color=7)
    doc.layers.add('PORTS', color=1)
    doc.layers.add('BORDERS', color=8)
    
    sorted_symbols = sorted(
        SYMBOL_REGISTRY.items(),
        key=lambda x: (get_category_sort_key(x[1].category), x[0])
    )
    
    cols = 8
    cell_width = 120
    cell_height = 100
    h_spacing = 20
    v_spacing = 20
    
    num_symbols = len(sorted_symbols)
    rows = (num_symbols + cols - 1) // cols
    total_width = cols * cell_width + (cols + 1) * h_spacing
    total_height = rows * cell_height + (rows + 1) * v_spacing
    
    start_x = -total_width / 2 + h_spacing + cell_width / 2
    start_y = total_height / 2 - v_spacing - cell_height / 2
    
    print(f"Generating test sheet with {num_symbols} symbols...")
    print(f"Grid: {cols} columns x {rows} rows")
    print(f"Total size: {total_width} x {total_height}")
    
    success_count = 0
    fail_count = 0
    missing_count = 0
    
    for idx, (symbol_id, entry) in enumerate(sorted_symbols):
        row = idx // cols
        col = idx % cols
        
        insert_x = start_x + col * (cell_width + h_spacing)
        insert_y = start_y - row * (cell_height + v_spacing)
        
        dxf_path = Path('/workspace') / entry.block_source
        
        if not dxf_path.exists():
            print(f"  [{idx+1:03d}] MISSING: {symbol_id} - Source not found: {entry.block_source}")
            missing_count += 1
            
            msp.add_text("MISSING SOURCE", dxfattribs={
                'insert': (insert_x, insert_y),
                'height': 4,
                'rotation': 0,
                'color': 1
            })
        else:
            if copy_entities_from_source(doc, dxf_path, insert_x, insert_y, scale=1.0, rotation=0.0):
                success_count += 1
                print(f"  [{idx+1:03d}] OK: {symbol_id}")
            else:
                fail_count += 1
                print(f"  [{idx+1:03d}] FAILED: {symbol_id}")
                msp.add_text("RENDER FAILED", dxfattribs={
                    'insert': (insert_x, insert_y),
                    'height': 4,
                    'rotation': 0,
                    'color': 1
                })
        
        add_label_and_ports(
            doc, insert_x, insert_y, cell_width,
            symbol_id, entry.category.value, idx + 1,
            entry.connection_ports if hasattr(entry, 'connection_ports') else None
        )
    
    title_y = -total_height / 2 + 30
    msp.add_text("P&ID APPROVED SYMBOL TEST SHEET", dxfattribs={
        'insert': (0, title_y + 20),
        'height': 6,
        'rotation': 0,
    })
    
    msp.add_text(f"Total Symbols: {num_symbols} | OK: {success_count} | Failed: {fail_count} | Missing: {missing_count}", dxfattribs={
        'insert': (0, title_y + 10),
        'height': 4,
        'rotation': 0,
    })
    
    import datetime
    msp.add_text(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", dxfattribs={
        'insert': (0, title_y),
        'height': 3,
        'rotation': 0,
    })
    
    output_path = output_dir / "approved_symbol_test_sheet.dxf"
    doc.saveas(str(output_path))
    print(f"\nTest sheet saved: {output_path}")
    
    return {
        'path': str(output_path),
        'total_symbols': num_symbols,
        'success_count': success_count,
        'fail_count': fail_count,
        'missing_count': missing_count,
        'grid_cols': cols,
        'grid_rows': rows,
        'total_width': total_width,
        'total_height': total_height,
    }


def generate_markdown_documentation(stats: Dict, output_dir: Path):
    """Generate markdown documentation for the test sheet"""
    
    md_lines = [
        "# P&ID Approved Symbol Test Sheet",
        "",
        "## Overview",
        "",
        "This test sheet contains all approved P&ID symbols from the canonical symbol registry,",
        "arranged in a grid layout with labels and port markers for human review.",
        "",
        "## Statistics",
        "",
        f"- **Total Symbols:** {stats['total_symbols']}",
        f"- **Successfully Rendered:** {stats['success_count']}",
        f"- **Render Failures:** {stats['fail_count']}",
        f"- **Missing Sources:** {stats['missing_count']}",
        "",
        "## Layout",
        "",
        f"- **Grid:** {stats['grid_cols']} columns x {stats['grid_rows']} rows",
        f"- **Cell Size:** 120 x 100 drawing units",
        f"- **Total Sheet Size:** {stats['total_width']} x {stats['total_height']} drawing units",
        "",
        "## File Information",
        "",
        f"- **DXF File:** `{os.path.basename(stats['path'])}`",
        f"- **Format:** DXF R2010 (AutoCAD 2007)",
        "",
        "## Review Instructions",
        "",
        "1. Open the DXF file in any CAD viewer (AutoCAD, LibreCAD, QCAD, etc.)",
        "2. Verify each symbol renders correctly",
        "3. Check that labels match the expected symbol ID",
        "4. Verify port markers are present where applicable",
        "5. Note any symbols that appear incorrect or missing",
        "",
        "## Symbol Organization",
        "",
        "Symbols are arranged in the following order:",
        "",
        "1. **Instruments** (ISA-5.1 symbols)",
        "   - Instrument bubbles",
        "   - Transmitters",
        "   - Controllers",
        "   - Indicators",
        "   - Switches",
        "",
        "2. **Valves & Final Control Elements**",
        "   - Control valves",
        "   - Manual valves",
        "   - Check valves",
        "   - Safety relief valves",
        "",
        "3. **Equipment**",
        "   - Vessels and drums",
        "   - Pumps",
        "   - Compressors",
        "   - Heat exchangers",
        "",
        "4. **Piping Components**",
        "   - Junctions (tees, crosses)",
        "   - Flanges",
        "   - Reducers",
        "",
        "5. **Special Symbols**",
        "   - Off-page connectors",
        "   - Termination points",
        "   - Welds",
        "",
        "## Layers",
        "",
        "The DXF file contains the following layers:",
        "",
        "- **SYMBOLS**: Main symbol geometry (black)",
        "- **LABELS**: Symbol identification labels (white)",
        "- **PORTS**: Port markers (red)",
        "- **BORDERS**: Cell borders (gray)",
        "",
        "## Next Steps",
        "",
        "After reviewing this test sheet:",
        "",
        "1. Approve symbols that render correctly",
        "2. Flag any symbols that need correction",
        "3. Address missing source files",
        "4. Proceed to full P&ID generation testing",
        "",
        "---",
        "",
        "*Generated by generate_symbol_test_sheet.py*",
    ]
    
    md_path = output_dir / "approved_symbol_test_sheet.md"
    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"Documentation saved: {md_path}")


def main():
    """Main entry point"""
    output_dir = Path('/workspace/pid_platform/review/approved_symbol_gallery')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("P&ID Approved Symbol Test Sheet Generator")
    print("=" * 60)
    print()
    
    stats = generate_test_sheet(output_dir)
    
    if stats:
        generate_markdown_documentation(stats, output_dir)
        
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total symbols processed: {stats['total_symbols']}")
        print(f"Successfully rendered: {stats['success_count']}")
        print(f"Render failures: {stats['fail_count']}")
        print(f"Missing sources: {stats['missing_count']}")
        print()
        print(f"Output DXF: {stats['path']}")
        print(f"Output MD: {output_dir / 'approved_symbol_test_sheet.md'}")
        print()
        print("Review the generated DXF file to verify all approved symbols.")
    else:
        print("Failed to generate test sheet")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
