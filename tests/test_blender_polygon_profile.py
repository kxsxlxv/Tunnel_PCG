from scripts import blender_profile_stage10 as profiler

from tunnel_scanner_core.scene import (
    LabelPolicy,
    SceneMode,
    SceneObject,
    ScenePackage,
)


def _obj(
    name: str,
    *,
    object_type: str,
    instance_id: int,
    prototype_key: str | None = None,
) -> SceneObject:
    extra = {}
    if prototype_key is not None:
        extra["meshPrototypeKey"] = prototype_key
    return SceneObject(
        name=name,
        vertices=(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        faces=((0, 1, 2, 3),),
        object_type=object_type,
        ring_id=0,
        label_id=0,
        instance_id=instance_id,
        semantic_class="test",
        extra_properties=extra,
    )


def test_scene_package_polygon_profile_separates_logical_and_unique_mesh_cost():
    package = ScenePackage(
        name="profile-test",
        mode=SceneMode.NOMINAL_WITH_PRESCRIBED_JOINTS,
        label_policy=LabelPolicy.STSD_COARSE,
        objects=(
            _obj(
                "PROTO_A",
                object_type="production_repeat",
                instance_id=1,
                prototype_key="repeat-v1",
            ),
            _obj(
                "PROTO_B",
                object_type="production_repeat",
                instance_id=2,
                prototype_key="repeat-v1",
            ),
            _obj(
                "UNIQUE",
                object_type="lining_segment",
                instance_id=3,
            ),
        ),
    )

    profile = profiler._profile_scene_package(package)
    totals = profile["totals"]
    repeated = profile["byObjectType"]["production_repeat"]

    assert totals["objects"] == 3
    assert totals["logicalVertices"] == 12
    assert totals["logicalPolygons"] == 3
    assert totals["logicalTriangles"] == 6
    assert totals["uniqueMeshDataBlocks"] == 2
    assert totals["uniqueMeshVertices"] == 8
    assert totals["uniqueMeshPolygons"] == 2
    assert totals["uniqueMeshTriangles"] == 4
    assert totals["prototypeInstances"] == 2
    assert totals["prototypeKeys"] == 1

    assert repeated["objects"] == 2
    assert repeated["logicalPolygons"] == 2
    assert repeated["uniqueMeshDataBlocks"] == 1
    assert repeated["uniqueMeshPolygons"] == 1
    assert repeated["prototypeInstances"] == 2
    assert repeated["prototypeKeys"] == 1


def test_polygon_profile_delta_reports_removed_types():
    before = {
        "byObjectType": {
            "bolt_pocket_cutter": {
                **profiler._new_bucket(),
                "objects": 3,
                "logicalVertices": 15,
                "logicalPolygons": 15,
                "logicalTriangles": 18,
            }
        }
    }
    after = {"byObjectType": {}}

    delta = profiler._build_delta(before, after)["bolt_pocket_cutter"]
    assert delta["objects"] == -3
    assert delta["logicalVertices"] == -15
    assert delta["logicalPolygons"] == -15
    assert delta["logicalTriangles"] == -18
