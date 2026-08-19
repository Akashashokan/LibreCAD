#!/usr/bin/env python3
"""Generate PNG previews of all valve DXF blocks - lines only for reliability."""
import ezdxf
from PIL import Image, ImageDraw
import os

VALVE_DIR = "/workspace/libreCAD_blocks/PIP Valves"
OUT = "/workspace/valve_images"
os.makedirs(OUT, exist_ok=True)

files = sorted([f for f in os.listdir(VALVE_DIR) if f.endswith('.dxf')])
print(f"Converting {len(files)} valve DXF files to PNG...\n")

ok = 0
for fn in files:
    path = os.path.join(VALVE_DIR, fn)
    try:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
        
        pts = []
        lines = []
        circles = []
        
        for e in msp:
            if e.dxftype() == 'LINE':
                s = (float(e.dxf.start[0]), float(e.dxf.start[1]))
                t = (float(e.dxf.end[0]), float(e.dxf.end[1]))
                pts.extend([s, t])
                lines.append((s, t))
            elif e.dxftype() == 'CIRCLE':
                c = (float(e.dxf.center[0]), float(e.dxf.center[1]))
                r = float(e.dxf.radius)
                pts.append((c[0]-r, c[1]-r))
                pts.append((c[0]+r, c[1]+r))
                circles.append((c, r))
        
        if not pts:
            print(f"{fn:45s} SKIP (no geometry)")
            continue
        
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        w, h = maxx-minx, maxy-miny
        pad = max(w,h)*0.25
        minx-=pad; maxx+=pad; miny-=pad; maxy+=pad
        w = maxx-minx; h = maxy-miny
        
        scale = 12
        iw, ih = int(w*scale)+40, int(h*scale)+40
        iw, ih = max(iw,150), max(ih,150)
        
        img = Image.new('RGB', (iw,ih), (255,255,255))
        d = ImageDraw.Draw(img)
        
        def xy(pt):
            x,y = pt
            return (int((x-minx)*scale)+20, int((maxy-y)*scale)+20)
        
        # Draw circles first (they're behind)
        for c, r in circles:
            bbox = [xy((c[0]-r, c[1]-r)), xy((c[0]+r, c[1]+r))]
            d.ellipse(bbox, outline=(0,0,0), width=2)
        
        # Draw lines
        for s, t in lines:
            d.line([xy(s), xy(t)], fill=(0,0,0), width=2)
        
        out = os.path.join(OUT, fn.replace('.dxf','.png'))
        img.save(out)
        print(f"{fn:45s} OK")
        ok += 1
        
    except Exception as ex:
        print(f"{fn:45s} ERROR: {ex}")

print(f"\nConverted {ok}/{len(files)} valves to {OUT}")
