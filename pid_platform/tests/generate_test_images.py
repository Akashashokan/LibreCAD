"""
Generate test DXF and convert to PNG images

Demonstrates complete CAD pipeline:
1. Create semantic model
2. Place components with CAD adapter
3. Route exact-port connections
4. Generate DXF file
5. Convert DXF → SVG → PNG
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from pid_platform.pid_model.equipment import Vessel, Pump, ManualValve
from pid_platform.pid_model.instruments import Transmitter, Controller, SignalType
from pid_platform.pid_model.base import PortRef
from pid_platform.connectivity.connections import ConnectionManager
from pid_platform.cad.adapter import SemanticCADAdapter
from pid_platform.cad.routing import ProcessRouter, SignalRouter
from pid_platform.renderers.dxf.renderer import DXFRenderer


def generate_vessel_valve_pump():
    """Generate V-101 → XV-101 → P-101 pipeline"""
    
    print("=" * 60)
    print("Generating Vessel → Valve → Pump Pipeline")
    print("=" * 60)
    
    # === SEMANTIC MODEL ===
    vessel = Vessel(tag="V-101")
    vessel.add_nozzle("N1", role="process_outlet", side="right")
    
    valve = ManualValve(tag="XV-101")
    
    pump = Pump(tag="P-101")
    
    # Connect
    cm = ConnectionManager()
    cm.connect(vessel.get_port("N1"), valve.get_port("process_in"))
    cm.connect(valve.get_port("process_out"), pump.get_port("suction"))
    
    print(f"✓ Created semantic model: V-101 → XV-101 → P-101")
    
    # === CAD ADAPTER ===
    adapter = SemanticCADAdapter()
    
    # Place components in a row
    vessel_rendered = adapter.place_component(vessel, (100, 200), rotation_deg=0, scale=1.0)
    valve_rendered = adapter.place_component(valve, (200, 200), rotation_deg=0, scale=1.0)
    pump_rendered = adapter.place_component(pump, (300, 200), rotation_deg=0, scale=1.0)
    
    print(f"✓ Placed {len(adapter.rendered_components)} components")
    
    # === ROUTING ===
    process_router = ProcessRouter(adapter)
    
    v101_n1_ref = PortRef("V-101", "N1")
    xv101_in_ref = PortRef("XV-101", "process_in")
    xv101_out_ref = PortRef("XV-101", "process_out")
    p101_suction_ref = PortRef("P-101", "suction")
    
    route1 = process_router.route(v101_n1_ref, xv101_in_ref)
    route2 = process_router.route(xv101_out_ref, p101_suction_ref)
    
    print(f"✓ Generated {2} process routes with exact port endpoints")
    
    # === RENDER TO DXF ===
    renderer = DXFRenderer(adapter)
    renderer.create_document(title="V-101 to P-101 Pipeline")
    
    # Render components
    for rendered in adapter.rendered_components.values():
        renderer.render_component(rendered)
    
    # Render routes
    renderer.render_process_route(route1)
    renderer.render_process_route(route2)
    
    # Save DXF
    output_dir = Path("/workspace/test_output/images")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    dxf_path = output_dir / "vessel_valve_pump.dxf"
    renderer.save(str(dxf_path))
    
    print(f"✓ Saved DXF: {dxf_path}")
    
    return dxf_path


def generate_control_loop():
    """Generate PT-101 → PIC-101 → PV-101 control loop"""
    
    print("\n" + "=" * 60)
    print("Generating Control Loop: PT-101 → PIC-101 → PV-101")
    print("=" * 60)
    
    # === SEMANTIC MODEL ===
    transmitter = Transmitter(tag="PT-101", measured_variable="pressure")
    controller = Controller(tag="PIC-101")
    valve = ManualValve(tag="PV-101")  # Using manual valve as placeholder
    
    # Connect signal chain
    cm = ConnectionManager()
    cm.connect(transmitter.get_port("signal_out"), controller.get_port("pv_in"))
    cm.connect(controller.get_port("control_out"), valve.get_port("actuator_signal"))
    
    print(f"✓ Created semantic model: PT-101 → PIC-101 → PV-101")
    
    # === CAD ADAPTER ===
    adapter = SemanticCADAdapter()
    
    # Place components
    tx_rendered = adapter.place_component(transmitter, (100, 100), rotation_deg=0, scale=1.0)
    ctrl_rendered = adapter.place_component(controller, (200, 100), rotation_deg=0, scale=1.0)
    valve_rendered = adapter.place_component(valve, (300, 100), rotation_deg=0, scale=1.0)
    
    print(f"✓ Placed {len(adapter.rendered_components)} components")
    
    # === ROUTING ===
    signal_router = SignalRouter(adapter)
    
    tx_signal_ref = PortRef("PT-101", "signal_out")
    ctrl_pv_ref = PortRef("PIC-101", "pv_in")
    ctrl_out_ref = PortRef("PIC-101", "control_out")
    valve_act_ref = PortRef("PV-101", "actuator_signal")
    
    route1 = signal_router.route(tx_signal_ref, ctrl_pv_ref, SignalType.ELECTRICAL_ANALOG)
    route2 = signal_router.route(ctrl_out_ref, valve_act_ref, SignalType.PNEUMATIC)
    
    print(f"✓ Generated {2} signal routes")
    
    # === RENDER TO DXF ===
    renderer = DXFRenderer(adapter)
    renderer.create_document(title="PT-101 Control Loop")
    
    # Render components
    for rendered in adapter.rendered_components.values():
        renderer.render_component(rendered)
    
    # Render routes
    renderer.render_signal_route(route1)
    renderer.render_signal_route(route2)
    
    # Save DXF
    output_dir = Path("/workspace/test_output/images")
    dxf_path = output_dir / "control_loop.dxf"
    renderer.save(str(dxf_path))
    
    print(f"✓ Saved DXF: {dxf_path}")
    
    return dxf_path


def convert_dxf_to_png(dxf_path: Path, png_path: Path):
    """Convert DXF to PNG via ezdxf and cairosvg"""
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib.pyplot as plt
    
    print(f"\nConverting {dxf_path.name} to PNG...")
    
    # Read DXF
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    
    # Create matplotlib figure
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111)
    
    # Setup renderer
    ctx = RenderContext(doc)
    ctx.set_current_layout(msp)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)
    
    # Configure axes
    ax.axis('equal')
    ax.axis('off')
    plt.tight_layout()
    
    # Save PNG
    plt.savefig(str(png_path), dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✓ Saved PNG: {png_path}")
    return png_path


if __name__ == "__main__":
    output_dir = Path("/workspace/test_output/images")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate test cases
    dxf1 = generate_vessel_valve_pump()
    png1 = output_dir / "vessel_valve_pump.png"
    convert_dxf_to_png(dxf1, png1)
    
    dxf2 = generate_control_loop()
    png2 = output_dir / "control_loop.png"
    convert_dxf_to_png(dxf2, png2)
    
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nGenerated files:")
    print(f"  - {png1}")
    print(f"  - {png2}")
    print(f"\nTo view images, open the PNG files in any image viewer.")
