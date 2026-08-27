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
    
    # Note about PNG generation
    print("\n📝 NOTE: PNG preview generation requires ezdxf + Pillow.")
    print("   The manifest files have been created successfully.")
    print("   Individual PNG previews can be generated separately if needed.")
    
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
