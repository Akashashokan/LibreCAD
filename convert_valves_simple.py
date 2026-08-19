#!/usr/bin/env python3
"""
Simple robust DXF to PNG converter for valve blocks.
Skips problematic entities and focuses on core geometry.
"""

import ezdxf
from PIL import Image, ImageDraw
import os
import math

VALVE_DIR = "/workspace/libreCAD_blocks/PIP Valves"
OUTPUT_DIR = "/workspace/valve_images"

def dxf_to_png(dxf_path, output_path, scale=12, bg_color=(255, 255, 255), line_color=(0, 0, 0)):
    """Convert a DXF file to PNG image."""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # First pass: collect all points for bounding box
        all_points = []
        simple_entities = []
        
        for entity in msp:
            dxftype = entity.dxftype()
            
            if dxftype == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                all_points.extend([start[:2], end[:2]])
                simple_entities.append(('LINE', start[:2], end[:2]))
                
            elif dxftype == 'CIRCLE':
                center = entity.dxf.center[:2]
                radius = entity.dxf.radius
                all_points.append((center[0] - radius, center[1] - radius))
                all_points.append((center[0] + radius, center[1] + radius))
                simple_entities.append(('CIRCLE', center, radius))
                
            elif dxftype == 'ARC':
                # Store but don't rely on for bbox
                center = entity.dxf.center[:2]
                radius = entity.dxf.radius
                start_angle = math.degrees(float(entity.dxf.start_angle))
                end_angle = math.degrees(float(entity.dxf.end_angle))
                all_points.append((center[0] - radius, center[1] - radius))
                all_points.append((center[0] + radius, center[1] + radius))
                simple_entities.append(('ARC', center, radius, start_angle, end_angle))
                
            elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
                points = [p[:2] for p in entity.get_points()]
                all_points.extend(points)
                simple_entities.append(('POLYLINE', points))
        
        if not all_points:
            print(f"  No geometry found")
            return False
        
        # Calculate bounding box
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width < 0.01 or height < 0.01:
            print(f"  Too small")
            return False
        
        # Add 20% padding
        pad = max(width, height) * 0.2
        min_x -= pad
        max_x += pad
        min_y -= pad
        max_y += pad
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Create image
        img_w = max(int(width * scale) + 40, 120)
        img_h = max(int(height * scale) + 40, 120)
        
        img = Image.new('RGB', (img_w, img_h), bg_color)
        draw = ImageDraw.Draw(img)
        
        def to_img(x, y):
            px = int((x - min_x) * scale) + 20
            py = int((max_y - y) * scale) + 20
            return (px, py)
        
        # Draw entities
        for ent in simple_entities:
            if ent[0] == 'LINE':
                _, s, e = ent
                draw.line([to_img(*s), to_img(*e)], fill=line_color, width=2)
            
            elif ent[0] == 'CIRCLE':
                _, c, r = ent
                bbox = [to_img(c[0]-r, c[1]-r), to_img(c[0]+r, c[1]+r)]
                draw.ellipse(bbox, outline=line_color, width=2)
            
            elif ent[0] == 'ARC':
                _, c, r, sa, ea = ent
                try:
                    bbox = [to_img(c[0]-r, c[1]-r), to_img(c[0]+r, c[1]+r)]
                    x0, y0 = bbox[0]
                    x1, y1 = bbox[1]
                    if x0 > x1: x0, x1 = x1, x0
                    if y0 > y1: y0, y1 = y1, y0
                    draw.arc([(x0,y0), (x1,y1)], start=sa, end=ea, fill=line_color, width=2)
                except:
                    pass  # Skip problematic arcs
            
            elif ent[0] == 'POLYLINE':
                _, pts = ent
                img_pts = [to_img(*p) for p in pts]
                if len(img_pts) > 1:
                    draw.line(img_pts, fill=line_color, width=2)
        
        img.save(output_path)
        return True
        
    except Exception as e:
        print(f"  Error: {e}")
        return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    files = sorted([f for f in os.listdir(VALVE_DIR) if f.endswith('.dxf')])
    print(f"Found {len(files)} valve DXF files\n")
    
    ok = 0
    for fn in files:
        src = os.path.join(VALVE_DIR, fn)
        dst = os.path.join(OUTPUT_DIR, fn.replace('.dxf', '.png'))
        print(f"{fn[:40]:40s} ", end='')
        if dxf_to_png(src, dst):
            print("OK")
            ok += 1
        else:
            print("SKIP")
    
    print(f"\nConverted {ok}/{len(files)} valves to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
