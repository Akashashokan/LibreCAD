"""
Semantic CAD Adapter

Maps semantic P&ID model to CAD representation:
- Semantic component → CAD block
- Semantic PortRef → block-local anchor → global CAD coordinate
- Creates RenderedComponent registry with exact port anchors
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pid_platform.pid_model.base import PortRef, PortDomain, PIDObject
from pid_platform.connectivity.connections import ConnectionManager
from pid_platform.cad.symbols import SymbolDefinition, get_symbol, PortAnchor


@dataclass(frozen=True)
class Point2D:
    """Immutable 2D point"""
    x: float
    y: float
    
    def __add__(self, other: 'Point2D') -> 'Point2D':
        return Point2D(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: 'Point2D') -> 'Point2D':
        return Point2D(self.x - other.x, self.y - other.y)
    
    def distance_to(self, other: 'Point2D') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx*dx + dy*dy)


@dataclass
class RenderedComponent:
    """CAD representation of a semantic component"""
    semantic_id: str
    block_name: str
    insertion_point: Point2D
    rotation_deg: float = 0.0
    scale: float = 1.0
    bounding_box: Optional[Tuple[Point2D, Point2D]] = None
    port_anchors: Dict[PortRef, Point2D] = field(default_factory=dict)
    
    def get_anchor(self, port_ref: PortRef) -> Point2D:
        """Get global CAD anchor for a semantic port"""
        if port_ref not in self.port_anchors:
            raise KeyError(f"Port {port_ref} not found in rendered component {self.semantic_id}")
        return self.port_anchors[port_ref]


class SemanticCADAdapter:
    """
    Adapts semantic P&ID model to CAD representation
    
    Responsible for:
    - Mapping semantic components to CAD blocks
    - Computing global port anchors from local anchors + placement
    - Maintaining rendered component registry
    """
    
    def __init__(self):
        self.rendered_components: Dict[str, RenderedComponent] = {}
    
    def place_component(
        self,
        semantic_object: PIDObject,
        insertion_point: Tuple[float, float],
        rotation_deg: float = 0.0,
        scale: float = 1.0,
        symbol_id: Optional[str] = None
    ) -> RenderedComponent:
        """
        Place a semantic component in CAD space
        
        Args:
            semantic_object: The semantic equipment/instrument/component
            insertion_point: Global CAD coordinates (x, y)
            rotation_deg: Rotation in degrees (0, 90, 180, 270)
            scale: Uniform scale factor
            symbol_id: Optional override for symbol selection
            
        Returns:
            RenderedComponent with computed port anchors
        """
        # Determine symbol ID from object type if not specified
        if symbol_id is None:
            symbol_id = self._infer_symbol_id(semantic_object)
        
        # Get symbol definition
        symbol_def = get_symbol(symbol_id)
        
        # Create insertion point
        insert = Point2D(insertion_point[0], insertion_point[1])
        
        # Compute port anchors
        port_anchors = self._compute_port_anchors(
            semantic_object=semantic_object,
            symbol_def=symbol_def,
            insertion_point=insert,
            rotation_deg=rotation_deg,
            scale=scale
        )
        
        # Create rendered component
        rendered = RenderedComponent(
            semantic_id=semantic_object.tag if hasattr(semantic_object, 'tag') else str(id(semantic_object)),
            block_name=symbol_def.block_name,
            insertion_point=insert,
            rotation_deg=rotation_deg,
            scale=scale,
            port_anchors=port_anchors
        )
        
        # Register
        self.rendered_components[rendered.semantic_id] = rendered
        
        return rendered
    
    def _infer_symbol_id(self, obj: PIDObject) -> str:
        """Infer symbol ID from semantic object type"""
        class_name = obj.__class__.__name__.lower()
        
        # Map class names to symbol IDs
        mapping = {
            'vessel': 'vessel',
            'pump': 'pump',
            'manualvalve': 'manual_valve',
            'controlvalve': 'control_valve',
            'transmitter': 'transmitter',
            'controller': 'controller',
            'indicator': 'indicator',
            'switch': 'switch',
            'junction': 'junction_tee' if getattr(obj, 'junction_type', None) == 'TEE' else 'junction_cross',
            'offpageconnector': 'off_page_connector',
            'terminationpoint': 'termination_point',
        }
        
        return mapping.get(class_name, 'field_instrument')
    
    def _compute_port_anchors(
        self,
        semantic_object: PIDObject,
        symbol_def: SymbolDefinition,
        insertion_point: Point2D,
        rotation_deg: float,
        scale: float
    ) -> Dict[PortRef, Point2D]:
        """
        Compute global CAD anchors for all semantic ports
        
        Transforms:
          local anchor → scale → rotate → translate → global anchor
        """
        anchors = {}
        
        # Get semantic ports from object
        ports = semantic_object.get_ports() if hasattr(semantic_object, 'get_ports') else []
        
        # Build map of port_id → PortRef
        port_refs = {port.id: PortRef(semantic_object.tag if hasattr(semantic_object, 'tag') else str(id(semantic_object)), port.id) 
                     for port in ports}
        
        # Transform each symbol anchor
        for symbol_anchor in symbol_def.anchors:
            # Find matching semantic port
            if symbol_anchor.port_ref.port_id not in port_refs:
                continue
            
            port_ref = port_refs[symbol_anchor.port_ref.port_id]
            
            # Apply scale
            scaled_x = symbol_anchor.x * scale
            scaled_y = symbol_anchor.y * scale
            
            # Apply rotation (counter-clockwise)
            rad = math.radians(rotation_deg)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            
            rotated_x = scaled_x * cos_r - scaled_y * sin_r
            rotated_y = scaled_x * sin_r + scaled_y * cos_r
            
            # Apply translation
            global_x = insertion_point.x + rotated_x
            global_y = insertion_point.y + rotated_y
            
            anchors[port_ref] = Point2D(global_x, global_y)
        
        # Special handling for vessels with dynamic nozzles
        if hasattr(semantic_object, 'nozzles'):
            for nozzle_name, nozzle in semantic_object.nozzles.items():
                # Compute nozzle position based on side and relative position
                nozzle_ref = PortRef(semantic_object.tag if hasattr(semantic_object, 'tag') else str(id(semantic_object)), nozzle.id)
                if nozzle_ref not in anchors:
                    # Default nozzle positions based on side
                    side = getattr(nozzle, 'side', 'left')
                    if side == 'left':
                        anchors[nozzle_ref] = Point2D(insertion_point.x - 20*scale, insertion_point.y)
                    elif side == 'right':
                        anchors[nozzle_ref] = Point2D(insertion_point.x + 20*scale, insertion_point.y)
                    elif side == 'top':
                        anchors[nozzle_ref] = Point2D(insertion_point.x, insertion_point.y + 30*scale)
                    elif side == 'bottom':
                        anchors[nozzle_ref] = Point2D(insertion_point.x, insertion_point.y - 30*scale)
        
        return anchors
    
    def get_rendered(self, semantic_id: str) -> RenderedComponent:
        """Retrieve rendered component by semantic ID"""
        if semantic_id not in self.rendered_components:
            raise KeyError(f"Rendered component {semantic_id} not found")
        return self.rendered_components[semantic_id]
    
    def get_anchor(self, port_ref: PortRef) -> Point2D:
        """Get global CAD anchor for a semantic port reference"""
        component = self.get_rendered(port_ref.owner_uuid)
        return component.get_anchor(port_ref)
    
    def clear(self):
        """Clear all rendered components"""
        self.rendered_components.clear()
