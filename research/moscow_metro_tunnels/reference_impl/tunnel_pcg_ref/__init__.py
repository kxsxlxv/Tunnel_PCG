from .rail_profiles import R50, R65, reconstruct_half_primitives, sample_closed_profile, validation_metrics
from .track import gauge_for_radius, cant_angle
from .clearances import cmk, om_upper_polygon
from .contact_rail import nominal_contact_rail, rule_side
from .alignment3d import (
    Vec2 as AlignmentVec2,
    Vec3,
    Frame3,
    ProfileAnchor,
    chainage_xy,
    resample_polyline_xy,
    project_point_to_polyline_xy,
    grade_permille,
    vertical_curve_tangent_length_m,
    station_ugr_from_depth,
    interpolate_profile,
    localize,
    parallel_transport_frames,
    apply_cant,
)

__all__ = [
    "R50", "R65", "reconstruct_half_primitives", "sample_closed_profile", "validation_metrics",
    "gauge_for_radius", "cant_angle", "cmk", "om_upper_polygon", "nominal_contact_rail", "rule_side",
    "AlignmentVec2", "Vec3", "Frame3", "ProfileAnchor", "chainage_xy", "resample_polyline_xy",
    "project_point_to_polyline_xy", "grade_permille", "vertical_curve_tangent_length_m",
    "station_ugr_from_depth", "interpolate_profile", "localize", "parallel_transport_frames", "apply_cant",
]
