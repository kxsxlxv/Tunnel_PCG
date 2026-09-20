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


def test_blender_import_script_compiles_without_blender_runtime():
    script = Path(__file__).resolve().parents[1] / "scripts" / "blender_import_scene.py"
    compile(script.read_text(encoding="utf-8"), str(script), "exec")



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
            n_rings=1,
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
