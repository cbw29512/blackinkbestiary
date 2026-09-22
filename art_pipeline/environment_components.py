from __future__ import annotations

try:
    from .environment_assembly import assembly_fingerprint, assemble_environment_palette, infer_overlays
    from .environment_component_catalog import component_catalog_errors, infer_contexts, load_component_catalog, load_overlay_registry
except ImportError:
    from environment_assembly import assembly_fingerprint, assemble_environment_palette, infer_overlays
    from environment_component_catalog import component_catalog_errors, infer_contexts, load_component_catalog, load_overlay_registry

__all__ = [
    "assembly_fingerprint",
    "assemble_environment_palette",
    "component_catalog_errors",
    "infer_contexts",
    "infer_overlays",
    "load_component_catalog",
    "load_overlay_registry",
]
