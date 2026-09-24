from __future__ import annotations

import json
import math

from tunnel_scanner_core import (
    AlignmentStation,
    sample_alignment_station,
    unigine_spline_graph_dict,
    write_unigine_spline_graph_spl,
)


def _bezier_point(p0, start_tangent, p3, end_tangent, t):
    p1 = tuple(p0[i] + start_tangent[i] for i in range(3))
    p2 = tuple(p3[i] + end_tangent[i] for i in range(3))
    u = 1.0 - t
    return tuple(
        u * u * u * p0[i]
        + 3.0 * u * u * t * p1[i]
        + 3.0 * u * t * t * p2[i]
        + t * t * t * p3[i]
        for i in range(3)
    )


def test_unigine_spline_export_matches_tunnel_pcg_cubic_alignment():
    stations = (
        AlignmentStation(
            chainage_m=0.0,
            world_y_m=0.0,
            offset_x_m=10.0,
            offset_z_m=0.0,
            source="external_geojson:test:vertex_0000",
            tangent_world=(0.0, 1.0, 0.0),
        ),
        AlignmentStation(
            chainage_m=20.0,
            world_y_m=15.0,
            offset_x_m=20.0,
            offset_z_m=2.0,
            source="external_geojson:test:vertex_0001",
            tangent_world=(1.0, 1.0, 0.2),
        ),
    )
    payload = unigine_spline_graph_dict(stations)
    assert len(payload["points"]) == 2
    assert len(payload["segments"]) == 1
    segment = payload["segments"][0]

    for t in (0.0, 0.125, 0.5, 0.875, 1.0):
        spline_point = _bezier_point(
            payload["points"][0],
            segment["start_tangent"],
            payload["points"][1],
            segment["end_tangent"],
            t,
        )
        project = sample_alignment_station(stations, 20.0 * t)
        expected = (
            project.offset_x_m,
            project.world_y_m,
            project.offset_z_m,
        )
        assert all(
            math.isclose(a, b, abs_tol=2e-12)
            for a, b in zip(spline_point, expected)
        )


def test_unigine_spline_export_can_shift_alignment_origin_to_track_ugr():
    stations = (
        AlignmentStation(
            0.0,
            0.0,
            2.0,
            10.0,
            "external_geojson:test:vertex_0000",
            (0.0, 1.0, 0.0),
        ),
        AlignmentStation(
            10.0,
            10.0,
            2.0,
            11.0,
            "external_geojson:test:vertex_0001",
            (0.0, 1.0, 0.1),
        ),
    )
    payload = unigine_spline_graph_dict(
        stations,
        local_z_offset_m=-1.67,
    )
    assert math.isclose(payload["points"][0][0], 2.0, abs_tol=1e-12)
    assert math.isclose(payload["points"][0][1], 0.0, abs_tol=1e-12)
    assert math.isclose(payload["points"][0][2], 8.33, abs_tol=1e-12)
    assert math.isclose(payload["points"][1][2], 9.33, abs_tol=1e-12)
    # A constant datum shift does not alter Hermite/Bezier derivatives.
    unshifted = unigine_spline_graph_dict(stations)
    assert (
        payload["segments"][0]["start_tangent"]
        == unshifted["segments"][0]["start_tangent"]
    )
    assert (
        payload["segments"][0]["end_tangent"]
        == unshifted["segments"][0]["end_tangent"]
    )


def test_unigine_spline_writer_emits_native_spl_json(tmp_path):
    stations = (
        AlignmentStation(
            0.0,
            0.0,
            0.0,
            0.0,
            "external_geojson:test:vertex_0000",
            (0.0, 1.0, 0.0),
        ),
        AlignmentStation(
            10.0,
            10.0,
            0.0,
            0.0,
            "external_geojson:test:vertex_0001",
            (0.0, 1.0, 0.0),
        ),
    )
    path = write_unigine_spline_graph_spl(
        stations,
        tmp_path / "track.spl",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"points", "segments"}
    assert data["segments"][0]["start_index"] == 0
    assert data["segments"][0]["end_index"] == 1
    assert data["segments"][0]["start_up"] == [0.0, 0.0, 1.0]
