#!/usr/bin/env python3
"""
Convert DXF valve blocks to PNG images for visualization.
"""

import ezdxf
from PIL import Image, ImageDraw
import os
import math

VALVE_DIR = "/workspace/libreCAD_blocks/PIP Valves"
OUTPUT_DIR = "/workspace/valve_images"

def dxf_to_png(dxf_path, output_path, scale=10, bg_color=(255, 255, 255), line_color=(0, 0, 0)):
    """Convert a DXF file to PNG image."""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # Collect all entities and find bounding box
        points = []
        entities = []
        
        for entity in msp:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                points.append((start[0], start[1]))
                points.append((end[0], end[1]))
                entities.append(('LINE', start, end))
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                points.append((center[0] - radius, center[1] - radius))
                points.append((center[0] + radius, center[1] + radius))
                entities.append(('CIRCLE', center, radius))
            elif entity.dxftype() == 'ARC':
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                points.append((center[0] - radius, center[1] - radius))
                points.append((center[0] + radius, center[1] + radius))
                entities.append(('ARC', center, radius, start_angle, end_angle))
            elif entity.dxftype() == 'TEXT' or entity.dxftype() == 'MTEXT':
                insert = entity.dxf.insert
                text = entity.plain_text() if hasattr(entity, 'plain_text') else str(entity.dxf.text)
                entities.append(('TEXT', insert, text))
        
        if not points:
            print(f"  No entities found in {dxf_path}")
            return False
        
        # Calculate bounding box
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Add padding
        padding = max(width, height) * 0.2
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Create image (flip Y axis for proper orientation)
        img_width = int(width * scale) + 40
        img_height = int(height * scale) + 40
        
        img = Image.new('RGB', (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        def transform(x, y):
            """Transform DXF coordinates to image coordinates."""
            px = int((x - min_x) * scale) + 20
            py = int((max_y - y) * scale) + 20  # Flip Y
            return (px, py)
        
        # Draw entities
        for entity in entities:
            if entity[0] == 'LINE':
                _, start, end = entity
                p1 = transform(start[0], start[1])
                p2 = transform(end[0], end[1])
                draw.line([p1, p2], fill=line_color, width=2)
            elif entity[0] == 'CIRCLE':
                _, center, radius = entity
                bbox = [
                    transform(center[0] - radius, center[1] - radius),
                    transform(center[0] + radius, center[1] + radius)
                ]
                draw.ellipse(bbox, outline=line_color, width=2)
            elif entity[0] == 'ARC':
                _, center, radius, start_angle, end_angle = entity
                bbox = [
                    transform(center[0] - radius, center[1] - radius),
                    transform(center[0] + radius, center[1] + radius)
                ]
                # Convert angles (DXF uses degrees, PIL uses radians from 3 o'clock)
                draw.arc(bbox, start=start_angle, end=end_angle, fill=line_color, width=2)
            elif entity[0] == 'TEXT':
                _, insert, text = entity
                pos = transform(insert[0], insert[1])
                draw.text(pos, str(text)[:20], fill=(0, 0, 128))
        
        img.save(output_path)
        return True
        
    except Exception as e:
        print(f"  Error converting {dxf_path}: {e}")
        return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    valve_files = sorted([f for f in os.listdir(VALVE_DIR) if f.endswith('.dxf')])
    
    print(f"Found {len(valve_files)} valve DXF files")
    
    converted = 0
    for filename in valve_files:
        dxf_path = os.path.join(VALVE_DIR, filename)
        output_filename = filename.replace('.dxf', '.png')
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        print(f"Converting {filename}...")
        if dxf_to_png(dxf_path, output_path, scale=15):
            converted += 1
    
    print(f"\nConverted {converted}/{len(valve_files)} valves to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
