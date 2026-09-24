from __future__ import annotations

"""UNIGINE SplineGraph export for Tunnel_PCG frame-aware alignments."""

import json
from pathlib import Path
from typing import Any, Sequence

from .production import (
    AlignmentStation,
    alignment_station_frame,
    alignment_station_origin,
)


def unigine_spline_graph_dict(
    stations: Sequence[AlignmentStation],
) -> dict[str, Any]:
    """Convert the C1 alignment into UNIGINE .spl cubic-Bezier data.

    Tunnel_PCG external interpolation is cubic Hermite with endpoint derivative
    equal to unit track tangent multiplied by the chainage span. The equivalent
    Bezier control offsets are derivative / 3. UNIGINE stores the end tangent
    pointing backward from the end point, hence the negative sign.
    """

    stations = tuple(stations)
    if len(stations) < 2:
        raise ValueError("UNIGINE spline export requires at least two stations")
    for left, right in zip(stations, stations[1:]):
        if right.chainage_m <= left.chainage_m:
            raise ValueError("alignment chainages must increase strictly")

    points = [
        [float(value) for value in alignment_station_origin(station)]
        for station in stations
    ]
    segments: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(stations, stations[1:])):
        span = float(right.chainage_m - left.chainage_m)
        _right0, tangent0, up0 = alignment_station_frame(left)
        _right1, tangent1, up1 = alignment_station_frame(right)
        scale = span / 3.0
        segments.append(
            {
                "start_index": index,
                "start_tangent": [
                    float(component * scale) for component in tangent0
                ],
                "start_up": [float(component) for component in up0],
                "end_index": index + 1,
                "end_tangent": [
                    float(-component * scale) for component in tangent1
                ],
                "end_up": [float(component) for component in up1],
            }
        )
    return {
        "points": points,
        "segments": segments,
    }


def write_unigine_spline_graph_spl(
    stations: Sequence[AlignmentStation],
    path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Write a UNIGINE SplineGraph .spl JSON text file."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = unigine_spline_graph_dict(stations)
    output.write_text(
        json.dumps(payload, indent=indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
