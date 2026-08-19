#!/usr/bin/env python3
import ezdxf
from PIL import Image, ImageDraw
import os

VALVE_DIR = "/workspace/libreCAD_blocks/PIP Valves"
OUT = "/workspace/valve_images"
os.makedirs(OUT, exist_ok=True)

for fn in sorted(os.listdir(VALVE_DIR))[:10]:
    if not fn.endswith('.dxf'): continue
    path = os.path.join(VALVE_DIR, fn)
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    
    pts = []
    lines = []
    for e in msp:
        if e.dxftype() == 'LINE':
            s = (float(e.dxf.start[0]), float(e.dxf.start[1]))
            t = (float(e.dxf.end[0]), float(e.dxf.end[1]))
            pts.extend([s, t])
            lines.append((s, t))
    
    if not pts: continue
    
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w, h = maxx-minx, maxy-miny
    pad = max(w,h)*0.2
    minx-=pad; maxx+=pad; miny-=pad; maxy+=pad
    w = maxx-minx; h = maxy-miny
    
    scale = 15
    iw, ih = int(w*scale)+40, int(h*scale)+40
    
    img = Image.new('RGB', (iw,ih), (255,255,255))
    d = ImageDraw.Draw(img)
    
    def xy(pt):
        x,y = pt
        return (int((x-minx)*scale)+20, int((maxy-y)*scale)+20)
    
    for s,t in lines:
        d.line([xy(s), xy(t)], fill=(0,0,0), width=2)
    
    out = os.path.join(OUT, fn.replace('.dxf','.png'))
    img.save(out)
    print(f"{fn} -> {out}")

print("\nDone! Check /workspace/valve_images/")
