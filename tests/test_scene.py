import json

from tunnel_scanner_core import (
    RingConfig,
    build_deformed_ring_mesh,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_closed_deformation,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.scene import (
    LabelPolicy,
    SceneMode,
    SceneObject,
    build_deformed_scene_package,
    build_nominal_scene_package,
)
from tunnel_scanner_core.scene_io import (
    read_scene_package_json,
    scene_package_from_dict,
    scene_package_to_dict,
    write_scene_package_json,
)


def _fixture(seed=5812):
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=seed)
    ring = build_ring_mesh(cfg, angles)
    prescribed = build_prescribed_joint_set(ring, sample_joint_config(seed=seed))
    deformation = sample_closed_deformation(cfg, angles, seed=seed)
    deformed = build_deformed_ring_mesh(ring, deformation)
    return cfg, angles, ring, prescribed, deformed


def test_nominal_scene_has_segments_and_prescribed_joints_only():
    _, _, ring, prescribed, _ = _fixture()
    package = build_nominal_scene_package(ring, prescribed, ring_id=12)

    assert package.mode is SceneMode.NOMINAL_WITH_PRESCRIBED_JOINTS
    assert package.label_policy is LabelPolicy.SEG2TUNNEL_LIKE
    assert len(package.objects) == 18  # 6 segments + 6 radial + 6 back collar
    assert len(package.objects_of_type("lining_segment")) == 6
    assert len(package.objects_of_type("prescribed_radial_joint")) == 6
    assert len(package.objects_of_type("prescribed_circumferential_joint")) == 6
    assert not package.objects_of_type("displacement_joint")


def test_scene_package_reuses_structural_indexes_for_repeated_queries():
    _, _, ring, prescribed, _ = _fixture()
    package = build_nominal_scene_package(ring, prescribed, ring_id=12)

    first = package.objects_of_type("lining_segment")
    second = package.objects_of_type("lining_segment")
    assert first is second
    assert len(first) == 6

    first_ring_ids = package.ring_ids
    second_ring_ids = package.ring_ids
    assert first_ring_ids is second_ring_ids
    assert first_ring_ids == (12,)


def test_deformed_scene_has_segments_and_displacement_joints_only():
    _, _, _, _, deformed = _fixture()
    package = build_deformed_scene_package(deformed, ring_id=12)

    assert package.mode is SceneMode.DEFORMED_WITH_DISPLACEMENT_JOINTS
    assert len(package.objects) == 12
    assert len(package.objects_of_type("lining_segment")) == 6
    assert len(package.objects_of_type("displacement_joint")) == 6
    assert not package.objects_of_type("prescribed_radial_joint")
    assert not package.objects_of_type("prescribed_circumferential_joint")


def test_seg2tunnel_like_labels_and_exact_blender_property_names():
    _, _, ring, prescribed, deformed = _fixture()
    for package in (
        build_nominal_scene_package(ring, prescribed, ring_id=7),
        build_deformed_scene_package(deformed, ring_id=7),
    ):
        segments = package.objects_of_type("lining_segment")
        assert [o.label_id for o in segments] == [1, 2, 3, 4, 5, 6]
        assert [o.segment_id for o in segments] == [0, 1, 2, 3, 4, 5]
        for obj in package.objects:
            props = obj.custom_properties
            assert props["labelID"] == obj.label_id
            assert props["ringID"] == 7
            assert props["instanceID"] == obj.instance_id
            assert props["objectType"] == obj.object_type
            assert props["semanticClass"] == obj.semantic_class
            if obj.object_type != "lining_segment":
                assert obj.label_id == 0


def test_instance_ids_and_names_are_stable_and_unique():
    _, _, ring, prescribed, _ = _fixture(seed=8)
    a = build_nominal_scene_package(ring, prescribed, ring_id=31)
    b = build_nominal_scene_package(ring, prescribed, ring_id=31)
    assert [o.name for o in a.objects] == [o.name for o in b.objects]
    assert [o.instance_id for o in a.objects] == [o.instance_id for o in b.objects]
    assert len({o.name for o in a.objects}) == len(a.objects)
    assert len({o.instance_id for o in a.objects}) == len(a.objects)
    assert min(o.instance_id for o in a.objects) == 31_000


def test_collection_paths_separate_semantic_geometry_categories():
    _, _, ring, prescribed, deformed = _fixture()
    nominal = build_nominal_scene_package(ring, prescribed, ring_id=2)
    deformed_pkg = build_deformed_scene_package(deformed, ring_id=2)

    assert {o.collection_path[-1] for o in nominal.objects_of_type("lining_segment")} == {"Segments"}
    assert {o.collection_path[-1] for o in nominal.objects_of_type("prescribed_radial_joint")} == {"PrescribedRadial"}
    assert {o.collection_path[-1] for o in nominal.objects_of_type("prescribed_circumferential_joint")} == {"Circumferential_back"}
    assert {o.collection_path[-1] for o in deformed_pkg.objects_of_type("displacement_joint")} == {"Displacement"}


def test_scene_json_roundtrip_is_lossless(tmp_path):
    _, _, _, _, deformed = _fixture(seed=77)
    package = build_deformed_scene_package(deformed, ring_id=4)
    path = tmp_path / "scene.json"
    write_scene_package_json(package, path)
    loaded = read_scene_package_json(path)

    assert loaded == package
    data = json.loads(path.read_text())
    assert data["schema"] == "tunnel_scanner_scene"
    assert data["schemaVersion"] == 1
    assert data["objects"][0]["customProperties"]["labelID"] == 1
    assert data["objects"][0]["customProperties"]["ringID"] == 4


def test_compact_scene_json_roundtrip_omits_only_redundant_custom_properties(tmp_path):
    _, _, _, _, deformed = _fixture(seed=77)
    package = build_deformed_scene_package(deformed, ring_id=4)
    pretty_path = tmp_path / "scene_pretty.json"
    compact_path = tmp_path / "scene_compact.json"

    write_scene_package_json(package, pretty_path)
    write_scene_package_json(package, compact_path, compact=True)

    pretty_data = json.loads(pretty_path.read_text())
    compact_data = json.loads(compact_path.read_text())
    assert "customProperties" in pretty_data["objects"][0]
    assert "customProperties" not in compact_data["objects"][0]
    assert compact_path.stat().st_size < pretty_path.stat().st_size
    assert read_scene_package_json(compact_path) == package


def test_scene_dict_rejects_unknown_schema_version():
    _, _, _, _, deformed = _fixture()
    package = build_deformed_scene_package(deformed)
    data = scene_package_to_dict(package)
    data["schemaVersion"] = 999
    try:
        scene_package_from_dict(data)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown scene schema version must be rejected")


def test_scene_object_rejects_invalid_face_indices():
    try:
        SceneObject(
            name="bad",
            vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            faces=((0, 1, 3),),
            object_type="bad",
            ring_id=0,
            label_id=0,
            instance_id=0,
            semantic_class="bad",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid face index must be rejected")



def test_nominal_scene_can_include_stage6_bolt_boolean_tools():
    from tunnel_scanner_core.bolts import (
        BoltConfig,
        BoltLayoutType,
        BoltPerturbationConfig,
        build_bolt_set,
    )

    _, _, ring, prescribed, _ = _fixture()
    bolts = build_bolt_set(
        ring,
        BoltConfig(),
        BoltLayoutType.TYPE1_CENTERED,
        seed=5812,
        perturbation_config=BoltPerturbationConfig(sigma_m=0.0, sigma_fraction=0.0),
    )
    package = build_nominal_scene_package(ring, prescribed, ring_id=12, bolts=bolts)
    assert len(package.objects_of_type("bolt_pocket_cutter")) == 18
    assert len(package.objects_of_type("bolt_head")) == 18
    assert len(package.objects) == 54
    assert package.metadata["boltBooleanPipeline"]["stage"] == "6"
    assert package.metadata["boltBooleanPipeline"]["assemblies"] == 18

    segment_names = {o.name for o in package.objects_of_type("lining_segment")}
    for cutter in package.objects_of_type("bolt_pocket_cutter"):
        props = cutter.custom_properties
        assert props["labelID"] == 0
        assert props["booleanTarget"] in segment_names
        assert props["booleanOperation"] == "DIFFERENCE"
        assert props["removeAfterBoolean"] is True
    for head in package.objects_of_type("bolt_head"):
        props = head.custom_properties
        assert props["labelID"] == 0
        assert props["booleanTarget"] in segment_names
        assert props["cutTargetBeforeDisplay"] is True
