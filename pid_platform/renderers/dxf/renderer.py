"""
DXF Renderer - Generates DXF files from semantic P&ID model

CRITICAL RULE: This renderer MUST use approved block inserts only.
No primitive geometry drawing is allowed for symbols.

Uses ezdxf library to create:
- Block inserts for equipment/instruments (from approved library)
- Polylines for process pipes (routing only, not symbols)
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
from pid_platform.standards.pid_symbol_registry import SymbolResolver, resolve_symbol


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
    """
    Renders semantic P&ID model to DXF using approved block inserts.
    
    CRITICAL: This renderer MUST insert approved blocks from the symbol registry.
    It must NOT draw primitive geometry (circles, lines, polylines) as substitutes
    for P&ID symbols. The only geometry drawn directly should be:
    - Process pipe routing (polylines connecting components)
    - Signal lines (styled lines connecting instruments)
    """
    
    def __init__(self, cad_adapter: SemanticCADAdapter, symbol_resolver: Optional[SymbolResolver] = None):
        self.adapter = cad_adapter
        self.symbol_resolver = symbol_resolver if symbol_resolver is not None else SymbolResolver()
        self.doc = None
        self.msp = None
        self.routes: List[RouteResult] = []
        
    def create_document(self, title: str = "P&ID"):
        """Create new DXF document with standard layers and blocks"""
        self.doc = ezdxf.new('R2010')
        self.doc.units = units.MM
        self.doc.header['$INSUNITS'] = 4  # Millimeters
        
        # Create layers
        self._create_layers()
        
        # Load/create blocks from approved library
        self._load_approved_blocks()
        
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
    
    def _load_approved_blocks(self):
        """
        Load all approved symbol blocks into the DXF document.
        
        In production, this would load actual DXF blocks from the approved library files.
        For now, we create minimal block definitions that reference the approved sources.
        """
        # Get all approved symbols
        all_symbols = self.symbol_resolver.get_all_approved_symbols()
        
        for symbol_id, entry in all_symbols.items():
            block_name = entry.block_name
            if block_name not in self.doc.blocks:
                # Create a block placeholder - in production this loads from entry.block_source
                # The block source file path is stored for verification/loading
                try:
                    block = self.doc.blocks.add(block_name)
                    # Store metadata about the block source for verification
                    block.set_dxf_attrib('comment', f"APPROVED_BLOCK:{entry.block_source}")
                except ValueError:
                    # Block already exists
                    pass
    
    def render_component(self, rendered: RenderedComponent):
        """
        Render a single component as an approved block insert.
        
        CRITICAL: This method MUST insert an approved block from the registry.
        It must NOT draw primitive geometry as a substitute symbol.
        """
        insert_point = (rendered.insertion_point.x, rendered.insertion_point.y)
        
        # Verify this component has an approved symbol
        if not rendered.approved_symbol_id:
            raise RuntimeError(
                f"Component {rendered.semantic_id} has no approved_symbol_id. "
                "All components must resolve to an approved symbol before rendering."
            )
        
        # Resolve to get block name
        try:
            entry = self.symbol_resolver.resolve(rendered.approved_symbol_id)
            block_name = entry.block_name
        except Exception as e:
            raise RuntimeError(
                f"Cannot render component {rendered.semantic_id}: "
                f"approved symbol '{rendered.approved_symbol_id}' not found in registry. "
                f"Error: {e}"
            )
        
        # Insert the approved block
        self.msp.add_blockref(
            block_name,
            insert_point,
            dxfattribs={
                'rotation': rendered.rotation_deg,
                'xscale': rendered.scale,
                'yscale': rendered.scale,
                'layer': INSTRUMENT_LAYER if 'INSTRUMENT' in block_name or 'TRANSMITTER' in block_name or 'CONTROLLER' in block_name else EQUIPMENT_LAYER,
            }
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
