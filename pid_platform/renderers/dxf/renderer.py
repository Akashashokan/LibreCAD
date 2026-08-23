"""
DXF Renderer - Generates DXF files from semantic P&ID model

Uses ezdxf library to create:
- Block inserts for equipment/instruments
- Polylines for process pipes
- Styled lines for instrument signals
- Metadata for CAD ↔ Semantic verification
"""

import ezdxf
from ezdxf import units
from typing import List, Dict, Optional
from pid_platform.pid_model.instruments import SignalType
from pid_platform.pid_model.base import PortRef
from pid_platform.cad.adapter import SemanticCADAdapter, RenderedComponent, Point2D
from pid_platform.cad.routing import RouteResult, ProcessRouter, SignalRouter


# ISA-5.1 line styles for signal types
SIGNAL_LINE_STYLES = {
    SignalType.PNEUMATIC: {'layer': 'SIGNAL_PNEUMATIC', 'linetype': 'DASHDOT', 'color': 3},
    SignalType.ELECTRICAL_ANALOG: {'layer': 'SIGNAL_ELECTRICAL', 'linetype': 'CONTINUOUS', 'color': 4},
    SignalType.ELECTRICAL_DIGITAL: {'layer': 'SIGNAL_DIGITAL', 'linetype': 'CONTINUOUS', 'color': 4},
    SignalType.HYDRAULIC: {'layer': 'SIGNAL_HYDRAULIC', 'linetype': 'DASHED', 'color': 5},
    SignalType.MECHANICAL: {'layer': 'SIGNAL_MECHANICAL', 'linetype': 'PHANTOM', 'color': 6},
    SignalType.CAPILLARY: {'layer': 'SIGNAL_CAPILLARY', 'linetype': 'DASHED', 'color': 7},
}

PROCESS_LAYER = 'PROCESS_PIPING'
EQUIPMENT_LAYER = 'EQUIPMENT'
INSTRUMENT_LAYER = 'INSTRUMENTS'
JUNCTION_LAYER = 'JUNCTIONS'


class DXFRenderer:
    """Renders semantic P&ID model to DXF"""
    
    def __init__(self, cad_adapter: SemanticCADAdapter):
        self.adapter = cad_adapter
        self.doc = None
        self.msp = None
        self.routes: List[RouteResult] = []
        
    def create_document(self, title: str = "P&ID"):
        """Create new DXF document with standard layers"""
        self.doc = ezdxf.new('R2010')
        self.doc.units = units.MM
        self.doc.header['$INSUNITS'] = 4  # Millimeters
        
        # Create layers
        self._create_layers()
        
        self.msp = self.doc.modelspace()
        return self.doc
    
    def _create_layers(self):
        """Create standard layers with linetypes"""
        layers = [
            (EQUIPMENT_LAYER, 7),  # White
            (INSTRUMENT_LAYER, 1),  # Red
            (PROCESS_LAYER, 2),  # Yellow
            ('SIGNAL_PNEUMATIC', 3),  # Green
            ('SIGNAL_ELECTRICAL', 4),  # Cyan
            ('SIGNAL_DIGITAL', 4),  # Cyan
            ('SIGNAL_HYDRAULIC', 5),  # Blue
            ('SIGNAL_MECHANICAL', 6),  # Magenta
            ('SIGNAL_CAPILLARY', 7),  # White
            (JUNCTION_LAYER, 8),  # Gray
        ]
        
        for layer_name, color in layers:
            if layer_name not in self.doc.layers:
                self.doc.layers.add(layer_name, color=color)
        
        # Add linetypes if not present
        linetypes = ['DASHDOT', 'DASHED', 'PHANTOM']
        for lt in linetypes:
            if lt not in self.doc.linetypes:
                try:
                    self.doc.linetypes.add(lt)
                except:
                    pass
    
    def render_component(self, rendered: RenderedComponent):
        """Render a single component as block insert"""
        # For now, use simple shapes instead of blocks
        # In production, this would insert actual blocks
        
        insert_point = (rendered.insertion_point.x, rendered.insertion_point.y)
        
        # Draw placeholder based on type
        if 'VESSEL' in rendered.block_name:
            self._draw_vessel(insert_point, rendered.scale)
        elif 'PUMP' in rendered.block_name:
            self._draw_pump(insert_point, rendered.scale)
        elif 'VALVE' in rendered.block_name:
            self._draw_valve(insert_point, rendered.scale, 'CONTROL' in rendered.block_name)
        elif 'INSTRUMENT' in rendered.block_name or 'TRANSMITTER' in rendered.block_name or 'CONTROLLER' in rendered.block_name:
            self._draw_instrument(insert_point, rendered.scale)
        elif 'JUNCTION' in rendered.block_name:
            self._draw_junction(insert_point, rendered.block_name)
        elif 'OFF_PAGE' in rendered.block_name:
            self._draw_off_page_connector(insert_point, rendered.scale)
        elif 'TERMINATION' in rendered.block_name:
            self._draw_termination(insert_point, rendered.scale)
        
        # Optionally add port markers
        # self._draw_port_markers(rendered)
    
    def _draw_vessel(self, insert, scale):
        """Draw vessel symbol"""
        w = 20 * scale
        h = 30 * scale
        x, y = insert
        
        # Simple rectangle with dished ends
        self.msp.add_lwpolyline([
            (x - w/2, y - h/2),
            (x + w/2, y - h/2),
            (x + w/2, y + h/2),
            (x - w/2, y + h/2),
            (x - w/2, y - h/2),
        ], dxfattribs={'layer': EQUIPMENT_LAYER})
    
    def _draw_pump(self, insert, scale):
        """Draw pump symbol"""
        r = 15 * scale
        x, y = insert
        
        # Circle with discharge arrow
        self.msp.add_circle((x, y), r, dxfattribs={'layer': EQUIPMENT_LAYER})
        # Discharge triangle
        self.msp.add_lwpolyline([
            (x + r*0.5, y - r*0.5),
            (x + r*1.2, y),
            (x + r*0.5, y + r*0.5),
        ], dxfattribs={'layer': EQUIPMENT_LAYER})
    
    def _draw_valve(self, insert, scale, is_control=False):
        """Draw valve symbol"""
        s = 10 * scale
        x, y = insert
        
        # Bowtie shape
        self.msp.add_lwpolyline([
            (x - s, y - s),
            (x + s, y + s),
            (x + s, y - s),
            (x - s, y + s),
            (x - s, y - s),
        ], dxfattribs={'layer': EQUIPMENT_LAYER})
        
        if is_control:
            # Add actuator circle
            self.msp.add_circle((x, y + s*1.5), s*0.6, dxfattribs={'layer': INSTRUMENT_LAYER})
    
    def _draw_instrument(self, insert, scale):
        """Draw instrument bubble"""
        r = 6 * scale
        x, y = insert
        
        self.msp.add_circle((x, y), r, dxfattribs={'layer': INSTRUMENT_LAYER})
    
    def _draw_junction(self, insert, junction_type):
        """Draw junction symbol"""
        x, y = insert
        
        # Small filled circle for tee/cross
        self.msp.add_circle((x, y), 2, dxfattribs={'layer': JUNCTION_LAYER, 'fill': True})
    
    def _draw_off_page_connector(self, insert, scale):
        """Draw off-page connector"""
        x, y = insert
        s = 8 * scale
        
        # Pentagon shape
        self.msp.add_lwpolyline([
            (x, y + s),
            (x + s, y + s*0.5),
            (x + s, y - s*0.5),
            (x, y - s),
            (x - s, y - s*0.5),
            (x - s, y + s*0.5),
            (x, y + s),
        ], dxfattribs={'layer': EQUIPMENT_LAYER})
    
    def _draw_termination(self, insert, scale):
        """Draw termination point"""
        x, y = insert
        
        # Simple circle
        self.msp.add_circle((x, y), 5, dxfattribs={'layer': EQUIPMENT_LAYER})
    
    def _draw_port_markers(self, rendered: RenderedComponent):
        """Draw small markers at port anchors (for debugging)"""
        for port_ref, anchor in rendered.port_anchors.items():
            self.msp.add_circle(
                (anchor.x, anchor.y), 
                1.5,
                dxfattribs={'layer': JUNCTION_LAYER}
            )
    
    def render_process_route(self, route: RouteResult):
        """Render process pipe route"""
        points = route.to_dxf_points()
        
        if len(points) < 2:
            return
        
        self.msp.add_lwpolyline(
            points,
            dxfattribs={
                'layer': PROCESS_LAYER,
                'lineweight': 35,  # 0.35mm
            }
        )
        
        self.routes.append(route)
    
    def render_signal_route(self, route: RouteResult):
        """Render instrument signal route with appropriate style"""
        points = route.to_dxf_points()
        
        if len(points) < 2:
            return
        
        # Get style based on signal type
        style = SIGNAL_LINE_STYLES.get(
            route.signal_type,
            SIGNAL_LINE_STYLES[SignalType.ELECTRICAL_ANALOG]
        )
        
        self.msp.add_lwpolyline(
            points,
            dxfattribs={
                'layer': style['layer'],
                'linetype': style['linetype'],
                'color': style['color'],
            }
        )
        
        self.routes.append(route)
    
    def save(self, filename: str):
        """Save DXF document"""
        if self.doc:
            self.doc.saveas(filename)
    
    def get_routes(self) -> List[RouteResult]:
        """Get all rendered routes for verification"""
        return self.routes
