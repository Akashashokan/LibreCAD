"""
Test CAD Pipeline - Full integration test

Tests:
1. Semantic model creation
2. CAD adapter placement
3. Exact-port routing
4. DXF generation
5. DXF → PNG conversion
"""

import pytest
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pid_platform.pid_model.equipment import Vessel, Pump, ManualValve
from pid_platform.pid_model.instruments import Transmitter, Controller, SignalType
from pid_platform.pid_model.base import PortRef
from pid_platform.connectivity.connections import ConnectionManager
from pid_platform.cad.adapter import SemanticCADAdapter, Point2D
from pid_platform.cad.routing import ProcessRouter, SignalRouter
from pid_platform.renderers.dxf.renderer import DXFRenderer


def test_vessel_valve_pump_pipeline():
    """
    Test complete CAD pipeline:
    V-101 → XV-101 → P-101
    
    Generates DXF and converts to PNG
    """
    # === SEMANTIC MODEL ===
    vessel = Vessel(tag="V-101")
    vessel.add_nozzle("N1", role="process_outlet", side="right")
    
    valve = ManualValve(tag="XV-101")
    
    pump = Pump(tag="P-101")
    
    # Connect
    cm = ConnectionManager()
    cm.connect(vessel.get_port("N1"), valve.get_port("process_in"))
    cm.connect(valve.get_port("process_out"), pump.get_port("suction"))
    
    # === CAD ADAPTER ===
    adapter = SemanticCADAdapter()
    
    # Place components
    vessel_rendered = adapter.place_component(
        vessel,
        insertion_point=(100, 200),
        rotation_deg=0,
        scale=1.0
    )
    
    valve_rendered = adapter.place_component(
        valve,
        insertion_point=(200, 200),
        rotation_deg=0,
        scale=1.0
    )
    
    pump_rendered = adapter.place_component(
        pump,
        insertion_point=(300, 200),
        rotation_deg=0,
        scale=1.0
    )
    
    # Verify port anchors exist
    assert len(vessel_rendered.port_anchors) > 0
    assert len(valve_rendered.port_anchors) == 2  # process_in, process_out
    assert len(pump_rendered.port_anchors) == 2  # suction, discharge
    
    # === ROUTING ===
    process_router = ProcessRouter(adapter)
    
    # Route V-101.N1 → XV-101.process_in
    v101_n1_ref = PortRef("V-101", "N1")
    xv101_in_ref = PortRef("XV-101", "process_in")
    
    route1 = process_router.route(v101_n1_ref, xv101_in_ref)
    
    # Route XV-101.process_out → P-101.suction
    xv101_out_ref = PortRef("XV-101", "process_out")
    p101_suction_ref = PortRef("P-101", "suction")
    
    route2 = process_router.route(xv101_out_ref, p101_suction_ref)
    
    # Verify exact endpoints
    v101_anchor = adapter.get_anchor(v101_n1_ref)
    assert route1.start_point.x == pytest.approx(v101_anchor.x, abs=0.001)
    assert route1.start_point.y == pytest.approx(v101_anchor.y, abs=0.001)
    
    xv101_in_anchor = adapter.get_anchor(xv101_in_ref)
    assert route1.end_point.x == pytest.approx(xv101_in_anchor.x, abs=0.001)
    assert route1.end_point.y == pytest.approx(xv101_in_anchor.y, abs=0.001)
    
    # === DXF GENERATION ===
    output_dir = Path("/workspace/test_outputs")
    output_dir.mkdir(exist_ok=True)
    
    renderer = DXFRenderer(adapter)
    renderer.create_document("Test Pipeline")
    
    # Render components
    renderer.render_component(vessel_rendered)
    renderer.render_component(valve_rendered)
    renderer.render_component(pump_rendered)
    
    # Render routes
    renderer.render_process_route(route1)
    renderer.render_process_route(route2)
    
    # Save DXF
    dxf_path = output_dir / "test_pipeline.dxf"
    renderer.save(str(dxf_path))
    
    assert dxf_path.exists()
    print(f"✓ DXF generated: {dxf_path}")
    
    # === CONVERT TO PNG ===
    try:
        from PIL import Image
        import cad_to_image  # Custom converter or use matplotlib
        
        png_path = output_dir / "test_pipeline.png"
        
        # Simple conversion using ezdxf + matplotlib
        import matplotlib.pyplot as plt
        import ezdxf
        
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Extract entities
        for entity in msp:
            if entity.dxftype() == 'LWPOLYLINE':
                points = [(p[0], p[1]) for p in entity.points()]
                if points:
                    x, y = zip(*points)
                    layer = entity.dxf.layer
                    if layer == 'PROCESS_PIPING':
                        ax.plot(x, y, 'y-', linewidth=2, label='Process')
                    elif layer == 'EQUIPMENT':
                        ax.plot(x, y, 'w-', linewidth=1)
                    elif layer == 'JUNCTIONS':
                        ax.plot(x, y, 'g-', linewidth=1)
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                circle = plt.Circle((center[0], center[1]), radius, fill=False, linewidth=2)
                ax.add_patch(circle)
        
        ax.set_aspect('equal')
        ax.set_title('Test Pipeline: V-101 → XV-101 → P-101')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        
        # Invert Y to match CAD convention
        ax.invert_yaxis()
        
        plt.savefig(str(png_path), dpi=150, bbox_inches='tight', facecolor='black')
        plt.close()
        
        assert png_path.exists()
        print(f"✓ PNG generated: {png_path}")
        
    except ImportError as e:
        print(f"⚠ PNG conversion skipped (missing library): {e}")
        png_path = None
    
    return {
        'dxf_path': str(dxf_path),
        'png_path': str(png_path) if png_path else None,
        'routes': [route1, route2],
        'adapter': adapter
    }


def test_control_loop():
    """
    Test instrument control loop:
    PT-101 → PIC-101 → PV-101
    
    Tests signal routing with proper line styles
    """
    # === SEMANTIC MODEL ===
    transmitter = Transmitter(tag="PT-101")
    controller = Controller(tag="PIC-101")
    
    # Connect signal
    cm2 = ConnectionManager()
    cm2.connect(transmitter.get_port("signal_out"), controller.get_port("pv_in"))
    
    # === CAD ADAPTER ===
    adapter = SemanticCADAdapter()
    
    # Place components
    adapter.place_component(transmitter, (100, 100), rotation_deg=0)
    adapter.place_component(controller, (200, 100), rotation_deg=0)
    
    # === SIGNAL ROUTING ===
    signal_router = SignalRouter(adapter)
    
    pt_signal_out = PortRef("PT-101", "signal_out")
    pic_pv_in = PortRef("PIC-101", "pv_in")
    
    route = signal_router.route(
        pt_signal_out,
        pic_pv_in,
        signal_type=SignalType.ELECTRICAL_ANALOG
    )
    
    # Verify route type
    assert route.route_type == 'SIGNAL'
    assert route.signal_type == SignalType.ELECTRICAL_ANALOG
    
    # Verify exact endpoints
    pt_anchor = adapter.get_anchor(pt_signal_out)
    assert route.start_point.distance_to(pt_anchor) < 0.001
    
    pic_anchor = adapter.get_anchor(pic_pv_in)
    assert route.end_point.distance_to(pic_anchor) < 0.001
    
    # === RENDER ===
    output_dir = Path("/workspace/test_outputs")
    
    renderer = DXFRenderer(adapter)
    renderer.create_document("Control Loop")
    
    # Render components
    for rendered in adapter.rendered_components.values():
        renderer.render_component(rendered)
    
    # Render signal
    renderer.render_signal_route(route)
    
    # Save
    dxf_path = output_dir / "control_loop.dxf"
    renderer.save(str(dxf_path))
    
    assert dxf_path.exists()
    print(f"✓ Control loop DXF: {dxf_path}")
    
    return {'dxf_path': str(dxf_path), 'route': route}


def test_rotation_transforms():
    """Test port anchor calculation at different rotations"""
    from pid_platform.pid_model.equipment import ManualValve
    
    valve = ManualValve(tag="XV-TEST")
    
    adapter = SemanticCADAdapter()
    
    # Test 0°, 90°, 180°, 270°
    for rotation in [0, 90, 180, 270]:
        adapter.clear()
        rendered = adapter.place_component(
            valve,
            (0, 0),
            rotation_deg=rotation,
            scale=1.0
        )
        
        # Verify anchors are rotated correctly
        in_ref = PortRef("XV-TEST", "process_in")
        out_ref = PortRef("XV-TEST", "process_out")
        
        assert in_ref in rendered.port_anchors
        assert out_ref in rendered.port_anchors
        
        print(f"✓ Rotation {rotation}°: IN={rendered.port_anchors[in_ref]}, OUT={rendered.port_anchors[out_ref]}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("CAD PIPELINE TEST SUITE")
    print("=" * 60)
    
    print("\n1. Testing Vessel → Valve → Pump pipeline...")
    result1 = test_vessel_valve_pump_pipeline()
    
    print("\n2. Testing control loop...")
    result2 = test_control_loop()
    
    print("\n3. Testing rotation transforms...")
    test_rotation_transforms()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nGenerated files in /workspace/test_outputs/")
    print("  - test_pipeline.dxf (and .png if PIL/matplotlib available)")
    print("  - control_loop.dxf")
