from __future__ import annotations

from pathlib import Path
import sys
import types

from tunnel_scanner_core import (
    RingConfig,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.blender_adapter import (
    _blender_custom_property_scalar,
    _blender_custom_property_value,
    _float32_vertex_key,
    _mesh_prototype_payload,
    _source_lining_boundary_vertex_keys,
    _source_lining_extrados_vertex_keys,
    build_scene_package_in_blender,
)
from tunnel_scanner_core.scene import build_nominal_scene_package


class _PropMixin:
    def __init__(self):
        self._props = {}

    def __setitem__(self, key, value):
        self._props[key] = value

    def __getitem__(self, key):
        return self._props[key]


class _LinkList(list):
    def link(self, item):
        if item not in self:
            self.append(item)


class _FakeMesh:
    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.faces = []
        self.validate_called = False
        self.update_called = False

    def from_pydata(self, vertices, edges, faces):
        self.vertices = list(vertices)
        self.faces = list(faces)

    def validate(self, verbose=False):
        self.validate_called = True
        return False

    def update(self, calc_edges=False):
        self.update_called = True


class _FakeObject(_PropMixin):
    def __init__(self, name, mesh):
        super().__init__()
        self.name = name
        self.data = mesh


class _FakeCollection(_PropMixin):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.children = _LinkList()
        self.objects = _LinkList()


class _Registry:
    def __init__(self, factory):
        self._items = {}
        self.factory = factory

    def get(self, name):
        return self._items.get(name)

    def new(self, name, *args):
        item = self.factory(name, *args)
        self._items[name] = item
        return item

    def remove(self, item, do_unlink=False):
        self._items.pop(item.name, None)

    def __iter__(self):
        return iter(self._items.values())


class _FakeUnitSettings:
    def __init__(self):
        self.system = "NONE"
        self.scale_length = 99.0
        self.length_unit = ""


class _FakeScene:
    def __init__(self):
        self.collection = _FakeCollection("SCENE_ROOT")
        self.unit_settings = _FakeUnitSettings()


class _FakeBpy(types.SimpleNamespace):
    def __init__(self):
        collections = _Registry(lambda name: _FakeCollection(name))
        meshes = _Registry(lambda name: _FakeMesh(name))
        objects = _Registry(lambda name, mesh: _FakeObject(name, mesh))
        super().__init__(
            data=types.SimpleNamespace(
                collections=collections,
                meshes=meshes,
                objects=objects,
            ),
            context=types.SimpleNamespace(scene=_FakeScene()),
        )


def _package():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=5812))
    return build_nominal_scene_package(ring, joints, ring_id=12)


def test_blender_adapter_builds_hierarchy_meshes_and_custom_props(monkeypatch):
    fake = _FakeBpy()
    monkeypatch.setitem(sys.modules, "bpy", fake)
    package = _package()

    result = build_scene_package_in_blender(package)
    assert result.root_collection_name == "TunnelScanner"
    assert len(result.object_names) == len(package.objects) == 18
    assert len(result.mesh_names) == 18

    root = fake.data.collections.get("TunnelScanner")
    assert root["sceneMode"] == package.mode.value
    assert root["labelPolicy"] == package.label_policy.value
    assert fake.context.scene.unit_settings.system == "METRIC"
    assert fake.context.scene.unit_settings.scale_length == 1.0
    assert fake.context.scene.unit_settings.length_unit == "METERS"

    first = fake.data.objects.get(package.objects[0].name)
    assert first is not None
    assert first["labelID"] == 1
    assert first["ringID"] == 12
    assert first["segmentID"] == 0
    assert first["objectType"] == "lining_segment"
    assert first.data.validate_called
    assert first.data.update_called

    # Qualified collection data-block names prevent identical short names from
    # being accidentally reused across different ring parents in future scenes.
    assert fake.data.collections.get("TunnelScanner::Ring_0012") is not None
    assert fake.data.collections.get("TunnelScanner::Ring_0012::Segments") is not None
    assert fake.data.collections.get("TunnelScanner::Ring_0012::Joints::PrescribedRadial") is not None


def test_lining_boundary_vertex_keys_follow_curved_mesh_topology():
    package = _package()
    segment = next(
        obj for obj in package.objects if obj.object_type == "lining_segment"
    )
    props = segment.custom_properties
    nu = int(props["surfaceSubdivisions"])
    nv = int(props["surfaceLongitudinalSubdivisions"])

    front = _source_lining_boundary_vertex_keys(segment, "front")
    back = _source_lining_boundary_vertex_keys(segment, "back")
    start = _source_lining_boundary_vertex_keys(segment, "start")
    end = _source_lining_boundary_vertex_keys(segment, "end")

    assert len(front) == 2 * (nu + 1)
    assert len(back) == 2 * (nu + 1)
    assert len(start) == 2 * (nv + 1)
    assert len(end) == 2 * (nv + 1)
    assert front != back
    assert start != end

    dense_face_count = 2 * nu * nv
    cap_face_count = 2 * nu
    radial_faces = segment.faces[
        dense_face_count + cap_face_count:
    ]
    assert len(radial_faces) == 2 * nv
    for index, face in enumerate(radial_faces):
        keys = {
            _float32_vertex_key(segment.vertices[i])
            for i in face
        }
        boundary = start if index % 2 == 0 else end
        assert keys <= boundary


def test_lining_extrados_classifier_uses_curved_mesh_outer_vertex_topology():
    package = _package()
    segment = next(
        obj for obj in package.objects if obj.object_type == "lining_segment"
    )
    outer = _source_lining_extrados_vertex_keys(segment)
    props = segment.custom_properties
    nu = int(props["surfaceSubdivisions"])
    nv = int(props["surfaceLongitudinalSubdivisions"])

    assert len(outer) == (nu + 1) * (nv + 1)
    dense_faces = segment.faces[: 2 * nu * nv]
    for index, face in enumerate(dense_faces):
        keys = {_float32_vertex_key(segment.vertices[i]) for i in face}
        if index % 2 == 1:
            assert keys <= outer
        else:
            assert not keys <= outer

    # End caps and radial segment sides span both inner and outer layers,
    # so they must never be classified as hidden extrados.
    for face in segment.faces[2 * nu * nv :]:
        keys = {_float32_vertex_key(segment.vertices[i]) for i in face}
        assert not keys <= outer


def test_lining_extrados_float32_keys_match_blender_storage_precision():
    vertex = (1234.567890123, -0.123456789, 3.0500000001)
    # Blender mesh coordinates are 32-bit floats. Repacking the values after
    # an explicit float32 round-trip must therefore produce the same key.
    import struct

    rounded = struct.unpack("<fff", struct.pack("<fff", *vertex))
    assert _float32_vertex_key(vertex) == _float32_vertex_key(rounded)

def test_blender_import_script_compiles_without_blender_runtime():
    script = Path(__file__).resolve().parents[1] / "scripts" / "blender_import_scene.py"
    compile(script.read_text(encoding="utf-8"), str(script), "exec")



def test_visible_bolt_heads_only_package_keeps_pocket_boolean_plan():
    from tunnel_scanner_core.bolts import (
        BoltConfig,
        BoltLayoutType,
        BoltPerturbationConfig,
        build_bolt_set,
    )
    from tunnel_scanner_core.blender_adapter import plan_bolt_boolean_operations

    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=5812))
    bolts = build_bolt_set(
        ring,
        BoltConfig(),
        BoltLayoutType.TYPE1_CENTERED,
        seed=5812,
        perturbation_config=BoltPerturbationConfig(
            sigma_m=0.0,
            sigma_fraction=0.0,
        ),
    )
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=12,
        bolts=bolts,
        visible_bolt_heads_only=True,
    )
    heads = package.objects_of_type("bolt_head")
    cutters = package.objects_of_type("bolt_pocket_cutter")
    assert heads
    assert len(cutters) == len(heads)
    plan = plan_bolt_boolean_operations(package)
    assert len(plan) == len(cutters)
    assert all(op.tool_type == "bolt_pocket_cutter" for op in plan)
    assert all(op.remove_tool_after is True for op in plan)
    assert all(
        cutter.custom_properties["booleanParticipation"] is True
        and cutter.custom_properties["removeAfterBoolean"] is True
        and cutter.custom_properties["cutterPurpose"] == "visible_bolt_pocket_recess"
        for cutter in cutters
    )
    assert all(
        head.custom_properties["visibleHeadOnlyMode"] is True
        and head.custom_properties["hiddenBoltBodyOmitted"] is True
        and head.custom_properties["boltPocketRecessOmitted"] is False
        and head.custom_properties["boltPocketCutterPresent"] is True
        and head.custom_properties["hiddenEmbeddedHeadBottomCapOmitted"] is True
        and head.custom_properties["cutTargetBeforeDisplay"] is False
        and head.custom_properties["booleanParticipation"] is False
        and "booleanTarget" not in head.custom_properties
        for head in heads
    )


def test_production_pocket_boolean_batches_group_three_cutters_per_segment():
    from tunnel_scanner_core.bolts import (
        BoltConfig,
        BoltLayoutType,
        BoltPerturbationConfig,
        build_bolt_set,
    )
    from tunnel_scanner_core.blender_adapter import (
        plan_bolt_boolean_batches,
        plan_bolt_boolean_operations,
    )

    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(
        ring,
        sample_joint_config(seed=5812),
    )
    bolts = build_bolt_set(
        ring,
        BoltConfig(),
        BoltLayoutType.TYPE1_CENTERED,
        seed=5812,
        perturbation_config=BoltPerturbationConfig(
            sigma_m=0.0,
            sigma_fraction=0.0,
        ),
    )
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=12,
        bolts=bolts,
        visible_bolt_heads_only=True,
    )
    operations = plan_bolt_boolean_operations(package)
    batches = plan_bolt_boolean_batches(package)

    assert len(operations) == 18
    assert len(batches) == 6
    assert all(len(batch) == 3 for batch in batches)
    assert all(
        len({op.target_name for op in batch}) == 1
        for batch in batches
    )
    assert {
        op.tool_name
        for batch in batches
        for op in batch
    } == {op.tool_name for op in operations}


def test_debug_head_boolean_mode_is_never_reordered_by_batch_planner():
    from tunnel_scanner_core.bolts import (
        BoltConfig,
        BoltLayoutType,
        BoltPerturbationConfig,
        build_bolt_set,
    )
    from tunnel_scanner_core.blender_adapter import (
        plan_bolt_boolean_batches,
        plan_bolt_boolean_operations,
    )

    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=5812))
    joints = build_prescribed_joint_set(
        ring,
        sample_joint_config(seed=5812),
    )
    bolts = build_bolt_set(
        ring,
        BoltConfig(),
        BoltLayoutType.TYPE1_CENTERED,
        seed=5812,
        perturbation_config=BoltPerturbationConfig(
            sigma_m=0.0,
            sigma_fraction=0.0,
        ),
    )
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=12,
        bolts=bolts,
        visible_bolt_heads_only=False,
    )
    operations = plan_bolt_boolean_operations(package)
    batches = plan_bolt_boolean_batches(package)

    assert len(operations) == 36
    assert len(batches) == len(operations)
    assert all(len(batch) == 1 for batch in batches)
    assert [batch[0] for batch in batches] == list(operations)


def test_stage6_boolean_plan_orders_pocket_before_head_for_each_bolt():
    from tunnel_scanner_core.bolts import (
        BoltConfig,
        BoltLayoutType,
        BoltPerturbationConfig,
        build_bolt_set,
    )
    from tunnel_scanner_core.blender_adapter import plan_bolt_boolean_operations

    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=5812))
    bolts = build_bolt_set(
        ring,
        BoltConfig(),
        BoltLayoutType.TYPE1_CENTERED,
        seed=5812,
        perturbation_config=BoltPerturbationConfig(sigma_m=0.0, sigma_fraction=0.0),
    )
    package = build_nominal_scene_package(ring, joints, ring_id=12, bolts=bolts)
    plan = plan_bolt_boolean_operations(package)
    assert len(plan) == 36
    for i in range(0, len(plan), 2):
        pocket, head = plan[i : i + 2]
        assert pocket.bolt_index == head.bolt_index
        assert pocket.target_name == head.target_name
        assert pocket.tool_type == "bolt_pocket_cutter"
        assert pocket.remove_tool_after is True
        assert head.tool_type == "bolt_head"
        assert head.remove_tool_after is False


def test_blender_custom_property_scalar_preserves_large_ids_losslessly():
    assert _blender_custom_property_scalar(True) is True
    assert _blender_custom_property_scalar(2**31 - 1) == 2**31 - 1
    assert _blender_custom_property_scalar(-(2**31)) == -(2**31)
    assert _blender_custom_property_scalar(2**31) == str(2**31)
    assert _blender_custom_property_scalar(-(2**31) - 1) == str(-(2**31) - 1)
    assert _blender_custom_property_scalar(2**63 - 1) == str(2**63 - 1)


def test_blender_custom_property_value_serializes_structured_metadata_as_json():
    assert _blender_custom_property_value([0.54, 0.62, 0.1]) == (
        "[0.54,0.62,0.1]"
    )
    assert _blender_custom_property_value((0.54, 0.62, 0.1)) == (
        "[0.54,0.62,0.1]"
    )
    assert _blender_custom_property_value(
        {"z": 0.16, "x": -1.45}
    ) == '{"x":-1.45,"z":0.16}'


def test_stage10_structured_contact_metadata_is_blender_safe_after_json_roundtrip(
    monkeypatch,
):
    from tunnel_scanner_core import (
        ProductionConfig,
        TunnelAssemblyConfig,
        build_production_tunnel,
        load_stage10_initial_moscow_profile,
        scene_package_from_dict,
        scene_package_to_dict,
    )

    fake = _FakeBpy()
    monkeypatch.setitem(sys.modules, "bpy", fake)
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="blender-stage10-structured-props",
            moscow_profile=profile,
            moscow_stage="10.4",
        ),
        seed=5812,
    )
    roundtripped = scene_package_from_dict(scene_package_to_dict(build.scene))

    build_scene_package_in_blender(
        roundtripped,
        apply_bolt_booleans=False,
        strip_internal_lining_caps=False,
        strip_coincident_lining_interfaces=False,
    )
    bracket = roundtripped.objects_of_type(
        "production_contact_rail_bracket"
    )[0]
    blender_obj = fake.data.objects.get(bracket.name)
    assert blender_obj is not None
    assert blender_obj["resourceEnvelopeM"] == "[0.54,0.62,0.1]"


def test_stage10_blender_adapter_reuses_periodic_mesh_datablocks(monkeypatch):
    from tunnel_scanner_core import (
        ProductionConfig,
        TunnelAssemblyConfig,
        build_production_tunnel,
        load_stage10_initial_moscow_profile,
    )

    fake = _FakeBpy()
    monkeypatch.setitem(sys.modules, "bpy", fake)
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="blender-stage10-prototype-reuse",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )

    result = build_scene_package_in_blender(
        build.scene,
        apply_bolt_booleans=False,
        reuse_mesh_prototypes=True,
    )
    blocks = build.scene.objects_of_type("production_lvt_block")
    assert len(blocks) >= 2
    first_scene, second_scene = blocks[:2]
    assert (
        first_scene.custom_properties["meshPrototypeKey"]
        == second_scene.custom_properties["meshPrototypeKey"]
    )

    first = fake.data.objects.get(first_scene.name)
    second = fake.data.objects.get(second_scene.name)
    assert first is not None
    assert second is not None
    assert first.data is second.data
    assert tuple(first.location) != tuple(second.location)

    for scene_object, blender_object in (
        (first_scene, first),
        (second_scene, second),
    ):
        for local_vertex, expected_world in zip(
            blender_object.data.vertices,
            scene_object.vertices,
        ):
            actual_world = tuple(
                float(local_vertex[index]) + float(blender_object.location[index])
                for index in range(3)
            )
            assert all(
                abs(actual - expected) <= 2e-12
                for actual, expected in zip(actual_world, expected_world)
            )

    assert result.mesh_prototype_count > 0
    assert result.mesh_prototype_instance_count > result.mesh_prototype_count
    assert result.shared_mesh_data_blocks_saved == (
        result.mesh_prototype_instance_count - result.mesh_prototype_count
    )

    root = fake.data.collections.get("TunnelScanner")
    assert root["meshPrototypeReuseEnabled"] is True
    assert root["meshPrototypeCount"] == result.mesh_prototype_count
    assert root["sharedMeshDataBlocksSaved"] == result.shared_mesh_data_blocks_saved


def test_blender_adapter_reuses_prototype_datablocks_across_chunk_calls(
    monkeypatch,
):
    from tunnel_scanner_core import (
        ChunkBoundaryPolicy,
        ProductionConfig,
        TunnelAssemblyConfig,
        build_chunk_scene_packages,
        build_production_tunnel,
        load_stage10_initial_moscow_profile,
    )

    fake = _FakeBpy()
    monkeypatch.setitem(sys.modules, "bpy", fake)
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="blender-stage10-cross-chunk-prototype-reuse",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )
    chunks = build_chunk_scene_packages(
        build,
        chunk_length_m=2.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        localize_coordinates=False,
    )
    assert len(chunks) >= 2

    cache = {}
    first_result = build_scene_package_in_blender(
        chunks[0],
        apply_bolt_booleans=False,
        reuse_mesh_prototypes=True,
        mesh_prototype_cache=cache,
    )
    second_result = build_scene_package_in_blender(
        chunks[1],
        clear_existing_root=False,
        apply_bolt_booleans=False,
        reuse_mesh_prototypes=True,
        mesh_prototype_cache=cache,
    )

    first_blocks = chunks[0].objects_of_type("production_lvt_block")
    second_blocks = chunks[1].objects_of_type("production_lvt_block")
    assert first_blocks
    assert second_blocks
    key = first_blocks[0].custom_properties["meshPrototypeKey"]
    assert any(
        block.custom_properties["meshPrototypeKey"] == key
        for block in second_blocks
    )
    first_obj = fake.data.objects.get(first_blocks[0].name)
    second_scene = next(
        block
        for block in second_blocks
        if block.custom_properties["meshPrototypeKey"] == key
    )
    second_obj = fake.data.objects.get(second_scene.name)
    assert first_obj is not None
    assert second_obj is not None
    assert first_obj.data is second_obj.data
    assert key in cache
    assert first_result.mesh_prototype_count > 0
    assert second_result.mesh_prototype_instance_count > 0

    root = fake.data.collections.get("TunnelScanner")
    assert root["meshPrototypeCount"] == len(cache)


def test_mesh_prototype_payload_preserves_local_geometry_after_chunk_localization():
    from tunnel_scanner_core import (
        ChunkBoundaryPolicy,
        ProductionConfig,
        TunnelAssemblyConfig,
        build_chunk_scene_packages,
        build_production_tunnel,
        load_stage10_initial_moscow_profile,
    )

    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="blender-stage10-localized-prototype",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )
    chunks = build_chunk_scene_packages(
        build,
        chunk_length_m=2.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        localize_coordinates=True,
    )
    prototype_object = next(
        obj
        for package in chunks
        for obj in package.objects
        if obj.object_type == "production_lvt_block"
    )
    payload = _mesh_prototype_payload(prototype_object)
    assert payload is not None
    _key, transform, local_vertices = payload
    for local_vertex, expected in zip(local_vertices, prototype_object.vertices):
        x, y, z = local_vertex
        reconstructed = (
            transform[0] * x + transform[1] * y + transform[2] * z + transform[3],
            transform[4] * x + transform[5] * y + transform[6] * z + transform[7],
            transform[8] * x + transform[9] * y + transform[10] * z + transform[11],
        )
        assert all(
            abs(actual - target) <= 2e-12
            for actual, target in zip(reconstructed, expected)
        )


def test_stage9_blender_adapter_serializes_63bit_persistent_ids_as_decimal_strings(
    monkeypatch,
):
    from tunnel_scanner_core import (
        ProductionConfig,
        TunnelAssemblyConfig,
        build_production_tunnel,
    )

    fake = _FakeBpy()
    monkeypatch.setitem(sys.modules, "bpy", fake)
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
        ),
        include_bolts=False,
        production_config=ProductionConfig(namespace="blender-id-test"),
        seed=5812,
    )

    build_scene_package_in_blender(
        build.scene,
        apply_bolt_booleans=False,
    )
    source = build.scene.objects[0]
    blender_obj = fake.data.objects.get(source.name)
    assert blender_obj is not None

    encoded = blender_obj["persistentInstanceID"]
    assert isinstance(encoded, str)
    assert int(encoded) == source.custom_properties["persistentInstanceID"]
    assert int(blender_obj["instanceID"]) == source.instance_id
    assert int(blender_obj["tunnelInstanceID"]) == source.custom_properties[
        "tunnelInstanceID"
    ]
