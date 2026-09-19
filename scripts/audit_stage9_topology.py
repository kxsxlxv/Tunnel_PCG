from __future__ import annotations

import json
from pathlib import Path

from tunnel_scanner_core import (
    LabelPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_production_tunnel,
    build_procedural_nominal_tunnel,
    finalize_production_render_scene,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage9_topology_audit.json"


def pair_breakdown(scene, audit):
    types = {obj.name: obj.object_type for obj in scene.objects}
    counts = {}
    for group in audit.duplicate_face_groups:
        group_types = tuple(sorted(types[name] for name, _ in group.occurrences))
        key = " | ".join(group_types)
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    cfg = TunnelAssemblyConfig(
        n_rings=5,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
    )
    stage8 = build_procedural_nominal_tunnel(
        assembly_config=cfg,
        include_bolts=False,
        include_ancillary=True,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=123,
    )
    audit8 = audit_exact_coincident_faces(stage8.scene)

    stage9 = build_production_tunnel(
        assembly_config=cfg,
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(namespace="topology-audit"),
        seed=123,
    )
    audit9_all = audit_exact_coincident_faces(stage9.scene)
    audit9_infra = audit_exact_coincident_faces(
        stage9.scene,
        object_filter=lambda obj: obj.object_type.startswith("production_"),
    )
    assert audit9_infra.duplicate_group_count == 0
    # Default Stage-9 source omits Stage-4 outer joint solids. Exact polygon
    # matching may under-count radial boundaries when neighbouring segments use
    # different longitudinal subdivisions, so only require that all remaining
    # duplicates are lining-to-lining and that finalization removes them.
    assert audit9_all.duplicate_group_count > 0
    assert set(pair_breakdown(stage9.scene, audit9_all)) == {
        "lining_segment | lining_segment"
    }

    finalized = finalize_production_render_scene(stage9.scene)
    audit9_final = audit_exact_coincident_faces(finalized)
    assert audit9_final.duplicate_group_count == 0

    result = {
        "stage": 9,
        "stage8": {
            "allDuplicateGroups": audit8.duplicate_group_count,
            "allDuplicateOccurrences": audit8.duplicate_face_occurrence_count,
            "pairBreakdown": pair_breakdown(stage8.scene, audit8),
        },
        "stage9Source": {
            "allDuplicateGroups": audit9_all.duplicate_group_count,
            "allDuplicateOccurrences": audit9_all.duplicate_face_occurrence_count,
            "pairBreakdown": pair_breakdown(stage9.scene, audit9_all),
            "productionInfrastructureDuplicateGroups": audit9_infra.duplicate_group_count,
            "prescribedOuterJointSolidsPresent": False,
        },
        "stage9Finalized": {
            "allDuplicateGroups": audit9_final.duplicate_group_count,
            "allDuplicateOccurrences": audit9_final.duplicate_face_occurrence_count,
            "pairBreakdown": pair_breakdown(finalized, audit9_final),
            "liningCapFacesRemoved": finalized.metadata[
                "productionLiningCapStrip"
            ]["removedFaces"],
            "segmentBoundaryFacesRemoved": finalized.metadata[
                "productionSegmentBoundaryStrip"
            ]["facesRemoved"],
            "segmentBoundaryCleanupTessellationIndependent": finalized.metadata[
                "productionSegmentBoundaryStrip"
            ]["tessellationIndependent"],
        },
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
