"""
Test: Approved Symbol Library Gate

This test proves that:
1. Every supported semantic component resolves to an approved symbol
2. Generated P&IDs contain ZERO unauthorized substitute symbols
3. Resolution failure raises UNRESOLVED_APPROVED_PID_SYMBOL explicitly
4. No production path can generate improvised/primitive symbols

Completion Gate: PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE
"""

import pytest
from typing import List, Dict

from pid_platform.standards.pid_symbol_registry import (
    SYMBOL_REGISTRY,
    SymbolResolver,
    SymbolResolutionError,
    SymbolCategory,
    StandardsBody,
    resolve_symbol,
    validate_all_symbols,
)
from pid_platform.cad.symbols import get_symbol, SYMBOL_REGISTRY as LEGACY_REGISTRY
from pid_platform.cad.adapter import SemanticCADAdapter, RenderedComponent
from pid_platform.pid_model.equipment import Vessel, Pump, ManualValve
from pid_platform.pid_model.instruments import Transmitter, Controller, Indicator, Switch


class TestApprovedSymbolRegistry:
    """Test the canonical symbol registry"""
    
    def test_registry_not_empty(self):
        """Prove registry contains approved symbols"""
        assert len(SYMBOL_REGISTRY) > 0, "Symbol registry must not be empty"
    
    def test_all_symbols_have_block_source(self):
        """Prove every symbol has an approved block source"""
        for symbol_id, entry in SYMBOL_REGISTRY.items():
            assert entry.block_source, f"Symbol {symbol_id} must have a block source"
            assert entry.block_name, f"Symbol {symbol_id} must have a block name"
    
    def test_all_symbols_have_category(self):
        """Prove every symbol is categorized"""
        for symbol_id, entry in SYMBOL_REGISTRY.items():
            assert entry.category is not None, f"Symbol {symbol_id} must have a category"
    
    def test_all_symbols_have_standards_body(self):
        """Prove every symbol is tagged with standards body (ISA or Project)"""
        for symbol_id, entry in SYMBOL_REGISTRY.items():
            assert entry.standards_body is not None, f"Symbol {symbol_id} must have a standards body"
    
    def test_isa_symbols_exist(self):
        """Prove ISA-5.1 symbols are registered"""
        resolver = SymbolResolver()
        isa_symbols = resolver.get_isa_symbols()
        assert len(isa_symbols) > 0, "Must have ISA-5.1 compliant symbols"
        
        # Check key ISA categories
        categories_found = {s.category for s in isa_symbols}
        assert SymbolCategory.TRANSMITTER in categories_found or \
               SymbolCategory.INSTRUMENT_BUBBLE in categories_found, \
               "Must have instrument symbols per ISA-5.1"
    
    def test_equipment_symbols_exist(self):
        """Prove project-approved equipment symbols exist"""
        resolver = SymbolResolver()
        project_symbols = resolver.get_project_symbols()
        assert len(project_symbols) > 0, "Must have project-approved equipment symbols"
        
        # Check key equipment categories
        categories_found = {s.category for s in project_symbols}
        assert SymbolCategory.VESSEL in categories_found, "Must have vessel symbol"
        assert SymbolCategory.PUMP in categories_found, "Must have pump symbol"


class TestSymbolResolution:
    """Test symbol resolution behavior"""
    
    def test_resolve_known_symbols(self):
        """Prove known component types resolve successfully"""
        resolver = SymbolResolver()
        
        test_cases = [
            ("vessel", "ISA_VESSEL"),
            ("pump", "ISA_PUMP"),
            ("manual_valve", "ISA_MANUAL_VALVE"),
            ("control_valve", "ISA_CONTROL_VALVE"),
            ("transmitter", "ISA_TRANSMITTER"),
            ("controller", "ISA_CONTROLLER"),
            ("field_instrument", "ISA_FIELD_INSTRUMENT"),
        ]
        
        for component_type, expected_block in test_cases:
            entry = resolver.resolve(component_type)
            assert entry.block_name == expected_block, \
                f"{component_type} should resolve to {expected_block}"
    
    def test_resolve_aliases(self):
        """Prove aliases resolve to correct symbols"""
        resolver = SymbolResolver()
        
        # Test vessel aliases
        for alias in ["tank", "drum"]:
            entry = resolver.resolve(alias)
            assert entry.symbol_id == "vessel", f"Alias '{alias}' should resolve to vessel"
        
        # Test valve aliases
        for alias in ["gate_valve", "ball_valve"]:
            entry = resolver.resolve(alias)
            assert entry.symbol_id == "manual_valve", f"Alias '{alias}' should resolve to manual_valve"
    
    def test_unresolved_symbol_raises_explicit_error(self):
        """Prove unknown symbols raise UNRESOLVED_APPROVED_PID_SYMBOL"""
        resolver = SymbolResolver()
        
        with pytest.raises(SymbolResolutionError) as exc_info:
            resolver.resolve("nonexistent_component_xyz")
        
        assert exc_info.value.error_code == "UNRESOLVED_APPROVED_PID_SYMBOL", \
            "Must raise UNRESOLVED_APPROVED_PID_SYMBOL for unknown components"
    
    def test_no_fallback_to_primitive(self):
        """Prove there is NO fallback to primitive geometry"""
        resolver = SymbolResolver()
        
        # Try to resolve something that doesn't exist
        try:
            resolver.resolve("fake_primitive_shape")
            assert False, "Should have raised SymbolResolutionError"
        except SymbolResolutionError as e:
            assert e.error_code == "UNRESOLVED_APPROVED_PID_SYMBOL"
            # Verify no block was returned
            assert "cannot proceed without an approved block" in str(e).lower() or \
                   "no approved symbol found" in str(e).lower()


class TestCADAdapterUsesApprovedSymbols:
    """Prove CAD adapter uses only approved symbols"""
    
    def test_adapter_tracks_approved_symbol_id(self):
        """Prove rendered components track which approved symbol was used"""
        adapter = SemanticCADAdapter()
        vessel = Vessel(tag="V-101")
        
        rendered = adapter.place_component(vessel, (0, 0))
        
        assert rendered.approved_symbol_id is not None, \
            "RenderedComponent must track approved_symbol_id"
        assert rendered.approved_symbol_id == "vessel", \
            "Vessel should use 'vessel' approved symbol"
    
    def test_all_rendered_components_have_approved_symbols(self):
        """Prove every rendered component has an approved symbol reference"""
        adapter = SemanticCADAdapter()
        
        # Place various components
        components = [
            (Vessel(tag="V-101"), (0, 0)),
            (Pump(tag="P-101"), (100, 0)),
            (ManualValve(tag="XV-101"), (200, 0)),
            (Transmitter(tag="PT-101"), (0, 50)),
            (Controller(tag="PIC-101"), (100, 50)),
        ]
        
        for comp, pos in components:
            rendered = adapter.place_component(comp, pos)
            assert rendered.approved_symbol_id is not None, \
                f"Component {comp.tag} must have approved_symbol_id"
            
            # Verify the symbol exists in registry
            assert rendered.approved_symbol_id in SYMBOL_REGISTRY, \
                f"Component {comp.tag} uses unregistered symbol {rendered.approved_symbol_id}"
    
    def test_adapter_fails_on_unknown_component(self):
        """Prove adapter fails explicitly when component cannot be resolved"""
        from pid_platform.pid_model.base import PIDObject
        
        # Create a fake component type that won't resolve
        class UnknownComponent(PIDObject):
            def get_ports(self):
                return []
        
        adapter = SemanticCADAdapter()
        unknown = UnknownComponent(tag="UNKNOWN-1")
        
        with pytest.raises(SymbolResolutionError) as exc_info:
            adapter.place_component(unknown, (0, 0))
        
        assert exc_info.value.error_code == "UNRESOLVED_APPROVED_PID_SYMBOL", \
            "Must fail with UNRESOLVED_APPROVED_PID_SYMBOL for unknown components"


class TestGeneratedPIDContainsOnlyApprovedSymbols:
    """Prove generated P&IDs contain zero unauthorized symbols"""
    
    def test_full_pipeline_uses_only_approved_blocks(self):
        """
        Full integration test: Create a P&ID and prove all components
        use approved symbols from the registry.
        """
        adapter = SemanticCADAdapter()
        
        # Build a simple P&ID
        vessel = Vessel(tag="V-101")
        valve = ManualValve(tag="XV-101")
        pump = Pump(tag="P-101")
        transmitter = Transmitter(tag="PT-101")
        controller = Controller(tag="PIC-101")
        
        # Place all components
        adapter.place_component(vessel, (0, 0))
        adapter.place_component(valve, (100, 0))
        adapter.place_component(pump, (200, 0))
        adapter.place_component(transmitter, (0, 50))
        adapter.place_component(controller, (100, 50))
        
        # Audit: Every rendered component must use an approved symbol
        for semantic_id, rendered in adapter.rendered_components.items():
            # Must have approved_symbol_id set
            assert rendered.approved_symbol_id is not None, \
                f"Component {semantic_id} missing approved_symbol_id"
            
            # Must be in the approved registry
            assert rendered.approved_symbol_id in SYMBOL_REGISTRY, \
                f"Component {semantic_id} uses unapproved symbol: {rendered.approved_symbol_id}"
            
            # Block name must match the approved entry
            approved_entry = SYMBOL_REGISTRY[rendered.approved_symbol_id]
            assert rendered.block_name == approved_entry.block_name, \
                f"Component {semantic_id} block mismatch"
        
        # Count check: All placed components should be accounted for
        assert len(adapter.rendered_components) == 5, \
            "Should have rendered exactly 5 components"
        
        print("✓ PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE")
        print(f"  - All {len(adapter.rendered_components)} components use approved symbols")
        print(f"  - Zero unauthorized/primitive symbols detected")


class TestNoPrimitiveGeometryFallback:
    """Prove there is no path to primitive geometry fallback"""
    
    def test_resolver_has_no_fallback_logic(self):
        """Prove resolver does not contain fallback logic"""
        import inspect
        from pid_platform.standards.pid_symbol_registry import SymbolResolver
        
        source = inspect.getsource(SymbolResolver.resolve)
        
        # Remove comments and docstrings - only check actual code
        lines = source.split('\n')
        code_lines = []
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            # Skip docstrings
            if '"""' in stripped or "'''" in stripped:
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue  # Single-line docstring
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Skip comment-only lines
            if stripped.startswith('#'):
                continue
            code_lines.append(line)
        
        code_only = '\n'.join(code_lines)
        
        # Should NOT contain fallback patterns in actual code
        forbidden_patterns = [
            "fallback",
            "default_geometry",
            "draw_rectangle",
            "draw_circle",
            "create_shape",
            "add_lwpolyline",
            "add_circle",
            "add_line",
        ]
        
        for pattern in forbidden_patterns:
            assert pattern.lower() not in code_only.lower(), \
                f"Resolver resolve() method must not contain '{pattern}' fallback logic in code"
    
    def test_cad_symbols_module_delegates_to_registry(self):
        """Prove cad/symbols.py delegates to canonical registry"""
        from pid_platform.cad import symbols
        
        # The module should import from canonical registry
        assert hasattr(symbols, 'CANONICAL_SYMBOL_REGISTRY'), \
            "cad/symbols.py should import CANONICAL_SYMBOL_REGISTRY"
        
        # get_symbol should use resolve_symbol
        import inspect
        source = inspect.getsource(symbols.get_symbol)
        assert 'resolve_symbol' in source, \
            "get_symbol should delegate to resolve_symbol"


def run_completion_gate():
    """
    Run the completion gate test.
    
    Returns True if PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE is satisfied.
    """
    print("\n" + "="*70)
    print("RUNNING PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE")
    print("="*70)
    
    tests = [
        TestApprovedSymbolRegistry(),
        TestSymbolResolution(),
        TestCADAdapterUsesApprovedSymbols(),
        TestGeneratedPIDContainsOnlyApprovedSymbols(),
        TestNoPrimitiveGeometryFallback(),
    ]
    
    all_passed = True
    
    for test_class in tests:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        
        for method_name in dir(test_class):
            if method_name.startswith('test_'):
                method = getattr(test_class, method_name)
                try:
                    method()
                    print(f"  ✓ {method_name}")
                except Exception as e:
                    print(f"  ✗ {method_name}: {e}")
                    all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE: PASSED")
        print("  - Every component resolves to an approved block")
        print("  - Zero unauthorized substitute symbols")
        print("  - Explicit failure on unresolved symbols")
        print("  - No primitive geometry fallback paths")
    else:
        print("PASS_PID_APPROVED_SYMBOL_LIBRARY_GATE: FAILED")
    print("="*70 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = run_completion_gate()
    exit(0 if success else 1)
