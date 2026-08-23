"""
DXF Router - Generates exact-port process and signal routes

Key principles:
- Routes accept semantic PortRef, not raw coordinates
- First vertex == source port anchor (exact)
- Last vertex == target port anchor (exact)
- Orthogonal routing with intermediate vertices
- Process and signal routing remain separate
"""

from typing import List, Tuple, Optional
from pid_platform.pid_model.base import PortRef
from pid_platform.pid_model.instruments import SignalType
from pid_platform.cad.adapter import SemanticCADAdapter, Point2D


class RouteResult:
    """Represents a generated route with provenance"""
    
    def __init__(
        self,
        source_port: PortRef,
        target_port: PortRef,
        vertices: List[Point2D],
        route_type: str,  # 'PROCESS' or 'SIGNAL'
        signal_type: Optional[SignalType] = None
    ):
        self.source_port = source_port
        self.target_port = target_port
        self.vertices = vertices
        self.route_type = route_type
        self.signal_type = signal_type
    
    @property
    def start_point(self) -> Point2D:
        return self.vertices[0]
    
    @property
    def end_point(self) -> Point2D:
        return self.vertices[-1]
    
    def to_dxf_points(self) -> List[Tuple[float, float]]:
        """Convert to DXF coordinate tuples"""
        return [(v.x, v.y) for v in self.vertices]


class ProcessRouter:
    """Routes process piping between semantic ports"""
    
    def __init__(self, cad_adapter: SemanticCADAdapter):
        self.adapter = cad_adapter
    
    def route(
        self,
        source_port: PortRef,
        target_port: PortRef,
        orthogonal: bool = True
    ) -> RouteResult:
        """
        Route process pipe between two semantic ports
        
        Args:
            source_port: Source port reference
            target_port: Target port reference
            orthogonal: Use orthogonal routing (default True)
            
        Returns:
            RouteResult with exact endpoints
        """
        # Get exact port anchors
        source_anchor = self.adapter.get_anchor(source_port)
        target_anchor = self.adapter.get_anchor(target_port)
        
        # Generate route
        if orthogonal:
            vertices = self._orthogonal_route(source_anchor, target_anchor)
        else:
            vertices = [source_anchor, target_anchor]
        
        return RouteResult(
            source_port=source_port,
            target_port=target_port,
            vertices=vertices,
            route_type='PROCESS'
        )
    
    def _orthogonal_route(self, start: Point2D, end: Point2D) -> List[Point2D]:
        """Generate orthogonal L-shaped or multi-segment route"""
        # Simple L-routing: horizontal then vertical
        mid_x = end.x
        mid_y = start.y
        
        # Check if direct line is already orthogonal
        if start.x == end.x or start.y == end.y:
            return [start, end]
        
        # Try simple L-route
        mid = Point2D(mid_x, mid_y)
        
        # Avoid zero-length segments
        if mid.distance_to(start) < 0.001 or mid.distance_to(end) < 0.001:
            # Use alternative midpoint
            mid = Point2D(start.x, end.y)
        
        return [start, mid, end]


class SignalRouter:
    """Routes instrument signals between semantic ports"""
    
    def __init__(self, cad_adapter: SemanticCADAdapter):
        self.adapter = cad_adapter
    
    def route(
        self,
        source_port: PortRef,
        target_port: PortRef,
        signal_type: SignalType,
        orthogonal: bool = True
    ) -> RouteResult:
        """
        Route instrument signal between two semantic ports
        
        Args:
            source_port: Source port reference
            target_port: Target port reference
            signal_type: Type of signal (determines line style)
            orthogonal: Use orthogonal routing (default True)
            
        Returns:
            RouteResult with exact endpoints
        """
        # Get exact port anchors
        source_anchor = self.adapter.get_anchor(source_port)
        target_anchor = self.adapter.get_anchor(target_port)
        
        # Generate route
        if orthogonal:
            vertices = self._orthogonal_route(source_anchor, target_anchor)
        else:
            vertices = [source_anchor, target_anchor]
        
        return RouteResult(
            source_port=source_port,
            target_port=target_port,
            vertices=vertices,
            route_type='SIGNAL',
            signal_type=signal_type
        )
    
    def _orthogonal_route(self, start: Point2D, end: Point2D) -> List[Point2D]:
        """Generate orthogonal routing for signals"""
        if start.x == end.x or start.y == end.y:
            return [start, end]
        
        # For signals, prefer vertical-first routing from instruments
        mid = Point2D(start.x, end.y)
        
        if mid.distance_to(start) < 0.001 or mid.distance_to(end) < 0.001:
            mid = Point2D(end.x, start.y)
        
        return [start, mid, end]
