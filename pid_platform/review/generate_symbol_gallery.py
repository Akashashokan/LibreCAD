#!/usr/bin/env python3
"""
P&ID Approved Symbol Gallery Generator

This script generates a human-reviewable gallery of all approved P&ID blocks
from the canonical symbol registry.

Outputs:
- approved_symbol_manifest.json (machine-readable)
- approved_symbol_manifest.md (human-readable table)
- Individual PNG previews for each symbol
- Contact sheet/gallery image
- Markdown gallery with embedded previews

Usage:
    python generate_symbol_gallery.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
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


def check_dxf_exists(block_source: str) -> bool:
    """Check if DXF source file exists"""
    dxf_path = Path('/workspace') / block_source
    return dxf_path.exists()


def get_category_sort_key(category: SymbolCategory) -> int:
    """Sort categories in review order: instruments, valves, equipment, junctions, special"""
    order = {
        # ISA-5.1 Instrumentation first
        SymbolCategory.INSTRUMENT_BUBBLE: 1,
        SymbolCategory.TRANSMITTER: 2,
        SymbolCategory.CONTROLLER: 3,
        SymbolCategory.INDICATOR: 4,
        SymbolCategory.SWITCH: 5,
        SymbolCategory.FINAL_CONTROL_ELEMENT: 6,
        SymbolCategory.ACTUATOR: 7,
        SymbolCategory.VALVE_FAILURE_INDICATION: 8,
        SymbolCategory.SIGNAL_LINE: 9,
        # Valves
        SymbolCategory.MANUAL_VALVE: 10,
        SymbolCategory.CONTROL_VALVE: 11,
        SymbolCategory.CHECK_VALVE: 12,
        SymbolCategory.SAFETY_RELIEF_VALVE: 13,
        # Equipment
        SymbolCategory.VESSEL: 20,
        SymbolCategory.COLUMN: 21,
        SymbolCategory.PUMP: 22,
        SymbolCategory.COMPRESSOR: 23,
        SymbolCategory.HEAT_EXCHANGER: 24,
        SymbolCategory.REACTOR: 25,
        SymbolCategory.TANK: 26,
        # Piping
        SymbolCategory.JUNCTION_TEE: 30,
        SymbolCategory.JUNCTION_CROSS: 31,
        SymbolCategory.FLANGE: 32,
        SymbolCategory.REDUCER: 33,
        # Special
        SymbolCategory.OFF_PAGE_CONNECTOR: 40,
        SymbolCategory.TERMINATION_POINT: 41,
        SymbolCategory.WELD: 42,
    }
    return order.get(category, 99)


def render_dxf_to_png(dxf_path: Path, output_png: Path, size: tuple = (200, 200)) -> bool:
    """
    Render a DXF file to PNG using ezdxf and Pillow.
    
    Returns True if successful, False otherwise.
    """
    try:
        import ezdxf
        from PIL import Image, ImageDraw
        
        # Read DXF
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        
        # Get entities by iterating directly (ezdxf API)
        entities = list(msp)
        if not entities:
            return False
        
        # Calculate extents
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')
        
        for entity in entities:
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
            # Fallback: use default extents
            min_x, min_y = -50, -50
            max_x, max_y = 50, 50
        
        # Add padding
        width = max_x - min_x
        height = max_y - min_y
        padding = max(width, height) * 0.2
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding
        
        # Create image with white background
        img = Image.new('RGB', size, 'white')
        draw = ImageDraw.Draw(img)
        
        # Scale factor
        scale_x = (size[0] - 20) / (max_x - min_x)
        scale_y = (size[1] - 20) / (max_y - min_y)
        scale = min(scale_x, scale_y)
        
        # Transform coordinates
        def transform(x, y):
            px = 10 + (x - min_x) * scale
            py = size[1] - 10 - (y - min_y) * scale
            return int(px), int(py)
        
        # Draw entities
        for entity in entities:
            try:
                if entity.dxftype() == 'LINE':
                    start = transform(entity.dxf.start.x, entity.dxf.start.y)
                    end = transform(entity.dxf.end.x, entity.dxf.end.y)
                    draw.line([start, end], fill='black', width=2)
                elif entity.dxftype() == 'CIRCLE':
                    center = transform(entity.dxf.center.x, entity.dxf.center.y)
                    radius = entity.dxf.radius * scale
                    bbox_rect = [
                        center[0] - radius,
                        center[1] - radius,
                        center[0] + radius,
                        center[1] + radius
                    ]
                    draw.ellipse(bbox_rect, outline='black', width=2)
                elif entity.dxftype() == 'ARC':
                    # Simplified arc drawing
                    center = transform(entity.dxf.center.x, entity.dxf.center.y)
                    radius = entity.dxf.radius * scale
                    bbox_rect = [
                        center[0] - radius,
                        center[1] - radius,
                        center[0] + radius,
                        center[1] + radius
                    ]
                    # Convert radians to degrees for PIL
                    start_angle = entity.dxf.start_angle * 180 / 3.14159265
                    end_angle = entity.dxf.end_angle * 180 / 3.14159265
                    draw.arc(bbox_rect, 
                            start=start_angle,
                            end=end_angle,
                            fill='black', width=2)
                elif entity.dxftype() == 'TEXT' or entity.dxftype() == 'MTEXT':
                    pos = transform(entity.dxf.insert.x, entity.dxf.insert.y)
                    text = entity.dxf.text if hasattr(entity.dxf, 'text') else str(entity)
                    draw.text(pos, text[:20], fill='black')
                elif entity.dxftype() == 'POINT':
                    pos = transform(entity.dxf.location.x, entity.dxf.location.y)
                    draw.point(pos, fill='black')
                elif entity.dxftype() == 'LWPOLYLINE' or entity.dxftype() == 'POLYLINE':
                    # Get vertices and draw lines
                    points = []
                    for pt in entity.get_points():
                        points.append(transform(pt[0], pt[1]))
                    if len(points) >= 2:
                        draw.line(points, fill='black', width=2)
                    if entity.closed and len(points) >= 2:
                        draw.line([points[-1], points[0]], fill='black', width=2)
                # Add more entity types as needed
            except Exception as e:
                continue
        
        img.save(output_png, 'PNG')
        return True
        
    except Exception as e:
        print(f"  Error rendering {dxf_path}: {e}")
        return False


def generate_manifest(symbols: Dict[str, SymbolEntry], output_dir: Path) -> tuple:
    """Generate manifest files (JSON and Markdown)"""
    
    manifest_entries = []
    sorted_symbols = sorted(
        symbols.items(),
        key=lambda x: (get_category_sort_key(x[1].category), x[0])
    )
    
    for idx, (symbol_id, entry) in enumerate(sorted_symbols, start=1):
        source_exists = check_dxf_exists(entry.block_source)
        
        png_filename = f"{idx:03d}_{symbol_id}.png"
        
        status = "OK"
        notes = ""
        
        if not source_exists:
            status = "MISSING_SOURCE"
            notes = f"Source DXF not found: {entry.block_source}"
        
        manifest_entry = {
            "gallery_index": idx,
            "symbol_id": symbol_id,
            "category": entry.category.value,
            "standards_body": entry.standards_body.value,
            "source_dxf_path": entry.block_source,
            "source_exists": source_exists,
            "png_preview_path": png_filename,
            "aliases": list(entry.aliases),
            "notes": notes,
            "status": status,
            "nominal_width": entry.nominal_width,
            "nominal_height": entry.nominal_height,
            "allowed_rotations": list(entry.allowed_rotations),
            "block_name": entry.block_name,
        }
        
        # Add ISA-specific fields if present
        if entry.isa_location:
            manifest_entry["isa_location"] = entry.isa_location
        if entry.isa_function:
            manifest_entry["isa_function"] = entry.isa_function
        
        manifest_entries.append(manifest_entry)
    
    # Write JSON manifest
    json_manifest = {
        "metadata": {
            "generated_by": "generate_symbol_gallery.py",
            "total_symbols": len(manifest_entries),
            "symbols_ok": sum(1 for e in manifest_entries if e["status"] == "OK"),
            "symbols_missing_source": sum(1 for e in manifest_entries if e["status"] == "MISSING_SOURCE"),
        },
        "symbols": manifest_entries
    }
    
    json_path = output_dir / "approved_symbol_manifest.json"
    with open(json_path, 'w') as f:
        json.dump(json_manifest, f, indent=2)
    
    # Write Markdown manifest
    md_lines = [
        "# Approved P&ID Symbol Gallery Manifest",
        "",
        f"**Total Symbols:** {len(manifest_entries)}",
        f"**OK:** {json_manifest['metadata']['symbols_ok']}",
        f"**Missing Source:** {json_manifest['metadata']['symbols_missing_source']}",
        "",
        "---",
        "",
        "## Symbol Table",
        "",
        "| # | Symbol ID | Category | Standards Body | Block Name | Source DXF | Status | Aliases |",
        "|---|-----------|----------|----------------|------------|------------|--------|---------|",
    ]
    
    for entry in manifest_entries:
        aliases_str = ", ".join(entry["aliases"][:3]) + ("..." if len(entry["aliases"]) > 3 else "")
        md_lines.append(
            f"| {entry['gallery_index']:03d} | {entry['symbol_id']} | {entry['category']} | "
            f"{entry['standards_body']} | {entry['block_name']} | {entry['source_dxf_path']} | "
            f"**{entry['status']}** | {aliases_str} |"
        )
    
    md_lines.extend([
        "",
        "---",
        "",
        "## Status Legend",
        "",
        "- **OK**: Source file exists, ready for review",
        "- **MISSING_SOURCE**: Source DXF file not found - needs attention",
        "- **RENDER_FAILED**: Preview generation failed",
        "- **DUPLICATE_SOURCE**: Multiple symbols point to same source file",
        "- **REVIEW_NEEDED**: Requires human review",
        "",
        "## Category Sections",
        "",
    ])
    
    # Group by category for markdown
    current_category = None
    for entry in manifest_entries:
        if entry["category"] != current_category:
            current_category = entry["category"]
            md_lines.append(f"### {current_category.replace('_', ' ').title()}")
            md_lines.append("")
        md_lines.append(f"- {entry['gallery_index']:03d} {entry['symbol_id']} ({entry['block_name']})")
        if entry["aliases"]:
            md_lines.append(f"  - Aliases: {', '.join(entry['aliases'])}")
        md_lines.append("")
    
    md_path = output_dir / "approved_symbol_manifest.md"
    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    return manifest_entries, json_manifest


def detect_duplicate_sources(manifest_entries: List[Dict]) -> List[Dict]:
    """Detect multiple symbols pointing to the same source file"""
    source_map: Dict[str, List[str]] = {}
    for entry in manifest_entries:
        source = entry["source_dxf_path"]
        if source not in source_map:
            source_map[source] = []
        source_map[source].append(entry["symbol_id"])
    
    duplicates = []
    for source, symbols in source_map.items():
        if len(symbols) > 1:
            duplicates.append({
                "source": source,
                "symbols": symbols,
                "count": len(symbols)
            })
    
    return duplicates


def generate_contact_sheet(manifest_entries: List[Dict], output_dir: Path, 
                          thumb_size: tuple = (100, 100), cols: int = 8):
    """Generate a contact sheet / gallery image with all symbol thumbnails"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Filter only OK entries
    ok_entries = [e for e in manifest_entries if e["status"] == "OK"]
    
    if not ok_entries:
        print("  No valid entries to generate contact sheet")
        return
    
    # Calculate grid dimensions
    rows = (len(ok_entries) + cols - 1) // cols
    
    # Load and resize thumbnails
    thumbnails = []
    max_label_height = 20
    
    for entry in ok_entries:
        png_path = output_dir / entry["png_preview_path"]
        try:
            img = Image.open(png_path)
            # Resize maintaining aspect ratio
            img.thumbnail((thumb_size[0], thumb_size[1]), Image.Resampling.LANCZOS)
            
            # Create labeled thumbnail
            thumb_with_label = Image.new('RGB', (thumb_size[0], thumb_size[1] + max_label_height), 'white')
            thumb_with_label.paste(img, ((thumb_size[0] - img.size[0]) // 2, 2))
            
            # Add label
            draw = ImageDraw.Draw(thumb_with_label)
            label = f"{entry['gallery_index']:03d} {entry['symbol_id'][:15]}"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
            except:
                font = ImageFont.load_default()
            
            text_bbox = draw.textbbox((0, 0), label, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (thumb_size[0] - text_width) // 2
            draw.text((text_x, thumb_size[1] + 2), label, fill='black', font=font)
            
            thumbnails.append((thumb_with_label, entry))
        except Exception as e:
            print(f"  Warning: Could not create thumbnail for {entry['symbol_id']}: {e}")
    
    if not thumbnails:
        return
    
    # Calculate final image size
    padding = 5
    total_width = cols * thumb_size[0] + (cols + 1) * padding
    total_height = rows * (thumb_size[1] + max_label_height) + (rows + 1) * padding
    
    # Create contact sheet
    contact_sheet = Image.new('RGB', (total_width, total_height), 'white')
    draw = ImageDraw.Draw(contact_sheet)
    
    # Place thumbnails
    for idx, (thumb, entry) in enumerate(thumbnails):
        row = idx // cols
        col = idx % cols
        
        x = padding + col * (thumb_size[0] + padding)
        y = padding + row * (thumb_size[1] + max_label_height + padding)
        
        contact_sheet.paste(thumb, (x, y))
    
    # Save contact sheet
    contact_sheet_path = output_dir / "approved_symbol_gallery.png"
    contact_sheet.save(contact_sheet_path, 'PNG')
    print(f"  Contact sheet saved: {contact_sheet_path} ({total_width}x{total_height})")


def generate_markdown_gallery(manifest_entries: List[Dict], output_dir: Path):
    """Generate a markdown gallery file with embedded PNG previews"""
    
    # Group by category
    categories = {}
    for entry in manifest_entries:
        cat = entry["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(entry)
    
    # Sort categories
    category_order = [
        'instrument_bubble', 'transmitter', 'controller', 'indicator', 'switch',
        'final_control_element', 'actuator', 'valve_failure_indication', 'signal_line',
        'manual_valve', 'control_valve', 'check_valve', 'safety_relief_valve',
        'vessel', 'column', 'pump', 'compressor', 'heat_exchanger', 'reactor', 'tank',
        'junction_tee', 'junction_cross', 'flange', 'reducer',
        'off_page_connector', 'termination_point', 'weld'
    ]
    
    sorted_categories = sorted(categories.keys(), 
                               key=lambda x: category_order.index(x) if x in category_order else 99)
    
    md_lines = [
        "# Approved P&ID Symbol Gallery",
        "",
        "This gallery contains visual previews of all approved P&ID symbols.",
        "",
        "---",
        "",
    ]
    
    for cat in sorted_categories:
        entries = categories[cat]
        cat_title = cat.replace('_', ' ').title()
        md_lines.append(f"## {cat_title}")
        md_lines.append("")
        md_lines.append("| # | Symbol ID | Preview | Source | Status |")
        md_lines.append("|---|-----------|---------|--------|--------|")
        
        for entry in entries:
            preview_link = entry["png_preview_path"]
            source_basename = Path(entry["source_dxf_path"]).name
            md_lines.append(
                f"| {entry['gallery_index']:03d} | {entry['symbol_id']} | "
                f"![{entry['symbol_id']}]({preview_link}) | "
                f"`{source_basename}` | {entry['status']} |"
            )
        
        md_lines.append("")
    
    md_lines.extend([
        "---",
        "",
        "## Summary",
        "",
        f"- **Total Symbols:** {len(manifest_entries)}",
        f"- **OK:** {sum(1 for e in manifest_entries if e['status'] == 'OK')}",
        f"- **Missing Source:** {sum(1 for e in manifest_entries if e['status'] == 'MISSING_SOURCE')}",
        f"- **Render Failed:** {sum(1 for e in manifest_entries if e['status'] == 'RENDER_FAILED')}",
        "",
        "## Files Generated",
        "",
        "- `approved_symbol_gallery.png` - Contact sheet with all symbols",
        "- Individual PNG previews: `001_*.png`, `002_*.png`, etc.",
        "- `approved_symbol_manifest.json` - Machine-readable metadata",
        "- `approved_symbol_manifest.md` - Human-readable table",
    ])
    
    md_path = output_dir / "approved_symbol_gallery.md"
    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines))
    
    print(f"  Markdown gallery saved: {md_path}")


def main():
    """Main entry point"""
    print("=" * 70)
    print("P&ID Approved Symbol Gallery Generator")
    print("=" * 70)
    
    # Output directory
    output_dir = Path('/workspace/pid_platform/review/approved_symbol_gallery')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nOutput directory: {output_dir}")
    
    # Get all approved symbols from canonical registry
    resolver = SymbolResolver()
    all_symbols = resolver.get_all_approved_symbols()
    
    print(f"\nTotal symbols in registry: {len(all_symbols)}")
    
    # Generate manifest
    print("\nGenerating manifest files...")
    manifest_entries, json_manifest = generate_manifest(all_symbols, output_dir)
    
    # Detect duplicates
    duplicates = detect_duplicate_sources(manifest_entries)
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} duplicate source mappings:")
        for dup in duplicates:
            print(f"   - {dup['source']} used by: {', '.join(dup['symbols'])}")
    
    # Summary statistics
    ok_count = sum(1 for e in manifest_entries if e["status"] == "OK")
    missing_count = sum(1 for e in manifest_entries if e["status"] == "MISSING_SOURCE")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total approved symbols discovered: {len(manifest_entries)}")
    print(f"PNGs to be generated: {ok_count}")
    print(f"Missing source count: {missing_count}")
    print(f"Duplicate/suspicious mapping count: {len(duplicates)}")
    print(f"\nOutput folder: {output_dir}")
    print(f"  - approved_symbol_manifest.json")
    print(f"  - approved_symbol_manifest.md")
    print("=" * 70)
    
    # Generate PNG previews
    print("\nGenerating PNG previews...")
    render_success = 0
    render_failed = 0
    
    for entry in manifest_entries:
        if entry["status"] == "OK":
            dxf_path = Path('/workspace') / entry["source_dxf_path"]
            png_path = output_dir / entry["png_preview_path"]
            
            if render_dxf_to_png(dxf_path, png_path):
                render_success += 1
            else:
                render_failed += 1
                entry["status"] = "RENDER_FAILED"
                entry["notes"] += " PNG rendering failed."
    
    print(f"  Rendered: {render_success} successful, {render_failed} failed")
    
    # Generate contact sheet / gallery image
    print("\nGenerating contact sheet gallery...")
    generate_contact_sheet(manifest_entries, output_dir)
    
    # Generate markdown gallery with embedded images
    print("Generating markdown gallery...")
    generate_markdown_gallery(manifest_entries, output_dir)
    
    # Note about PNG generation
    print("\n📝 PNG preview generation completed.")
    
    return {
        "total_symbols": len(manifest_entries),
        "ok_count": ok_count,
        "missing_count": missing_count,
        "duplicate_count": len(duplicates),
        "output_dir": str(output_dir),
    }


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result["missing_count"] == 0 else 1)
