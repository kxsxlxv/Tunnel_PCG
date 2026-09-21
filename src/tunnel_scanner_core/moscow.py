from __future__ import annotations

"""Stage-10.1 Moscow Metro production profile and R65 geometry contract.

The production core keeps the historical Tunnel_PCG convention (+Y longitudinal,
XZ cross-section). Moscow research data is represented in an engineering track
frame and mapped explicitly instead of changing the core axes.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MoscowCoordinateContract:
    units: str
    origin_description: str
    lateral_positive_description: str
    z_positive_description: str
    ugr_z_m: float
    profile_x_to_core_x_sign: int
    engineering_route_left_to_profile_x_sign: int
    profile_z_to_core_z_offset_m: float

    def __post_init__(self) -> None:
        if self.units != "m":
            raise ValueError("Moscow production profile currently requires metre units")
        if not math.isfinite(self.ugr_z_m):
            raise ValueError("UGR z must be finite")
        if self.profile_x_to_core_x_sign not in (-1, 1):
            raise ValueError("profile X to core X sign must be +/-1")
        if self.engineering_route_left_to_profile_x_sign not in (-1, 1):
            raise ValueError("route-left to profile-X sign must be +/-1")
        if not math.isfinite(self.profile_z_to_core_z_offset_m):
            raise ValueError("profile Z to core Z offset must be finite")

    def research_xz_to_core_xz(
        self,
        lateral_x_m: float,
        z_m: float,
    ) -> tuple[float, float]:
        """Map the Stage-10 2D profile frame into the core XZ cross-section."""
        return (
            self.profile_x_to_core_x_sign * float(lateral_x_m),
            float(z_m) + self.profile_z_to_core_z_offset_m,
        )

    def core_xz_to_research_xz(
        self,
        core_x_m: float,
        core_z_m: float,
    ) -> tuple[float, float]:
        return (
            self.profile_x_to_core_x_sign * float(core_x_m),
            float(core_z_m) - self.profile_z_to_core_z_offset_m,
        )

    def engineering_route_to_core_local(
        self,
        chainage_m: float,
        left_m: float,
        z_m: float,
    ) -> tuple[float, float, float]:
        """Map route (+X chainage,+Y left,+Z up) to core (+Y longitudinal)."""
        profile_x = self.engineering_route_left_to_profile_x_sign * float(left_m)
        core_x = self.profile_x_to_core_x_sign * profile_x
        return (
            core_x,
            float(chainage_m),
            float(z_m) + self.profile_z_to_core_z_offset_m,
        )

    def core_local_to_engineering_route(
        self,
        core_x_m: float,
        core_y_m: float,
        core_z_m: float,
    ) -> tuple[float, float, float]:
        profile_x = self.profile_x_to_core_x_sign * float(core_x_m)
        left_m = self.engineering_route_left_to_profile_x_sign * profile_x
        return (
            float(core_y_m),
            left_m,
            float(core_z_m) - self.profile_z_to_core_z_offset_m,
        )


@dataclass(frozen=True)
class MoscowDatums:
    ugr_z_m: float
    track_axis_x_m: float
    track_axis_z_m: float
    lining_axis_x_m: float
    lining_axis_z_m: float
    intrados_invert_z_m: float
    intrados_crown_z_m: float
    extrados_invert_z_m: float
    extrados_crown_z_m: float

    def __post_init__(self) -> None:
        if any(not math.isfinite(float(v)) for v in vars(self).values()):
            raise ValueError("Moscow datum values must be finite")
        if not math.isclose(self.track_axis_z_m, self.ugr_z_m, abs_tol=1e-12):
            raise ValueError(
                "track-axis vertical datum must lie on UGR for Stage 10.1"
            )


@dataclass(frozen=True)
class MoscowTrackProfile:
    service_preset: str
    rail_type: str
    gauge_m: float
    rail_height_m: float
    ugr_definition: str
    gauge_measurement_below_ugr_m: float
    gauge_measurement_sources: tuple[str, ...]
    rail_profile_source: str

    def __post_init__(self) -> None:
        if self.rail_type != "R65":
            raise ValueError("Stage-10.1 initial production profile requires R65")
        if not math.isfinite(self.gauge_m) or self.gauge_m <= 0.0:
            raise ValueError("track gauge must be finite and positive")
        if not math.isfinite(self.rail_height_m) or self.rail_height_m <= 0.0:
            raise ValueError("rail height must be finite and positive")
        if (
            not math.isfinite(self.gauge_measurement_below_ugr_m)
            or self.gauge_measurement_below_ugr_m <= 0.0
        ):
            raise ValueError(
                "gauge measurement level must be below UGR by a positive distance"
            )
        if not self.gauge_measurement_sources:
            raise ValueError("gauge measurement datum requires provenance")



@dataclass(frozen=True)
class MoscowTimberSleeperProfile:
    top_z_m: float
    bottom_z_m: float
    length_m: float
    thickness_m: float
    upper_face_width_m: float
    lower_face_width_m: float
    sawn_side_height_m: float
    density_per_km: float
    source: str

    def __post_init__(self) -> None:
        vals = (
            self.length_m,
            self.thickness_m,
            self.upper_face_width_m,
            self.lower_face_width_m,
            self.sawn_side_height_m,
            self.density_per_km,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in vals):
            raise ValueError("timber sleeper dimensions/density must be positive")
        if not math.isclose(
            self.top_z_m - self.bottom_z_m,
            self.thickness_m,
            abs_tol=1e-12,
        ):
            raise ValueError("sleeper top/bottom must match sleeper thickness")
        if self.upper_face_width_m > self.lower_face_width_m:
            raise ValueError("timber sleeper upper face must not exceed lower face")
        if self.sawn_side_height_m > self.thickness_m:
            raise ValueError("sawn side height must fit inside sleeper thickness")

    @property
    def pitch_m(self) -> float:
        return 1000.0 / self.density_per_km


@dataclass(frozen=True)
class MoscowKD65Profile:
    baseplate_transverse_m: float
    baseplate_longitudinal_m: float
    baseplate_max_height_m: float
    baseplate_rail_seat_height_m: float
    baseplate_hole_spacing_transverse_m: float
    baseplate_hole_spacing_longitudinal_m: float
    baseplate_hole_diameter_m: float
    baseplate_outer_wing_top_height_m: float
    baseplate_shoulder_inner_x_m: float
    baseplate_shoulder_outer_x_m: float
    baseplate_rail_seat_half_width_m: float
    under_pad_transverse_m: float
    under_pad_longitudinal_m: float
    under_pad_thickness_m: float
    under_pad_hole_diameter_m: float
    rail_pad_transverse_m: float
    rail_pad_longitudinal_m: float
    rail_pad_base_thickness_m: float
    rail_pad_total_thickness_m: float
    rail_pad_raised_seat_transverse_m: float
    track_screw_diameter_m: float
    track_screw_length_m: float
    track_screws_per_baseplate: int
    track_screw_head_radius_m: float
    track_screw_head_height_m: float
    clamp_bolt_diameter_m: float
    clamp_bolt_length_m: float
    clamp_bolts_per_baseplate: int
    nut_height_m: float
    nuts_per_baseplate: int
    spring_clamps_per_baseplate: int
    clamp_bolt_axis_offset_m: float
    nut_circumradius_m: float
    spring_clamp_center_offset_m: float
    spring_clamp_box_transverse_m: float
    spring_clamp_box_longitudinal_m: float
    spring_clamp_box_height_m: float
    spring_clamp_base_above_rail_seat_m: float
    baseplate_mesh_mode: str
    track_screw_head_mode: str
    clamp_geometry_mode: str
    family: str

    def __post_init__(self) -> None:
        vals = (
            self.baseplate_transverse_m,
            self.baseplate_longitudinal_m,
            self.baseplate_max_height_m,
            self.baseplate_rail_seat_height_m,
            self.baseplate_hole_spacing_transverse_m,
            self.baseplate_hole_spacing_longitudinal_m,
            self.baseplate_hole_diameter_m,
            self.baseplate_outer_wing_top_height_m,
            self.baseplate_shoulder_inner_x_m,
            self.baseplate_shoulder_outer_x_m,
            self.baseplate_rail_seat_half_width_m,
            self.under_pad_transverse_m,
            self.under_pad_longitudinal_m,
            self.under_pad_thickness_m,
            self.under_pad_hole_diameter_m,
            self.rail_pad_transverse_m,
            self.rail_pad_longitudinal_m,
            self.rail_pad_base_thickness_m,
            self.rail_pad_total_thickness_m,
            self.rail_pad_raised_seat_transverse_m,
            self.track_screw_diameter_m,
            self.track_screw_length_m,
            self.track_screw_head_radius_m,
            self.track_screw_head_height_m,
            self.clamp_bolt_diameter_m,
            self.clamp_bolt_length_m,
            self.nut_height_m,
            self.clamp_bolt_axis_offset_m,
            self.nut_circumradius_m,
            self.spring_clamp_center_offset_m,
            self.spring_clamp_box_transverse_m,
            self.spring_clamp_box_longitudinal_m,
            self.spring_clamp_box_height_m,
            self.spring_clamp_base_above_rail_seat_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in vals):
            raise ValueError("KD-65 dimensions must be finite and positive")
        if self.baseplate_rail_seat_height_m > self.baseplate_max_height_m:
            raise ValueError("KD-65 rail seat cannot exceed maximum envelope")
        if self.rail_pad_base_thickness_m > self.rail_pad_total_thickness_m:
            raise ValueError("rail pad base thickness cannot exceed total thickness")
        counts = (
            self.track_screws_per_baseplate,
            self.clamp_bolts_per_baseplate,
            self.nuts_per_baseplate,
            self.spring_clamps_per_baseplate,
        )
        if any(v <= 0 for v in counts):
            raise ValueError("KD-65 hardware counts must be positive")


@dataclass(frozen=True)
class MoscowTrackConcreteProfile:
    surface_cross_slope_to_drain: float
    surface_reference_abs_x_m: float
    surface_reference_z_m: float
    minimum_bottom_at_rail_z_m: float
    central_drain_center_x_m: float
    central_drain_clear_width_m: float
    central_drain_bottom_z_m: float
    water_groove_width_m: float
    water_groove_depth_m: float
    water_groove_center_x_m: float
    concrete_material: str
    surface_reference_mode: str
    groove_position_mode: str

    def __post_init__(self) -> None:
        positive = (
            self.surface_cross_slope_to_drain,
            self.surface_reference_abs_x_m,
            self.central_drain_clear_width_m,
            self.water_groove_width_m,
            self.water_groove_depth_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("track-concrete dimensions/slope must be positive")
        if self.water_groove_width_m >= self.central_drain_clear_width_m:
            raise ValueError("water-release groove must fit inside central drain")
        if not math.isfinite(self.surface_reference_z_m):
            raise ValueError("concrete surface reference z must be finite")
        if self.minimum_bottom_at_rail_z_m >= self.surface_reference_z_m:
            raise ValueError("concrete minimum bottom must lie below top datum")
        if self.central_drain_bottom_z_m >= self.surface_reference_z_m:
            raise ValueError("central drain bottom must lie below concrete top")


@dataclass(frozen=True)
class MoscowWalkwayProfile:
    top_z_m: float
    inner_edge_x_m: float
    outer_edge_x_m: float
    top_clear_width_m: float
    side_profile_x_sign: int
    geometry_mode: str
    service_era_interpretation: str
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        positive = (
            self.inner_edge_x_m,
            self.outer_edge_x_m,
            self.top_clear_width_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("walkway dimensions must be finite and positive")
        if not math.isfinite(self.top_z_m):
            raise ValueError("walkway top z must be finite")
        if self.side_profile_x_sign not in (-1, 1):
            raise ValueError("walkway profile-X side sign must be +/-1")
        if self.outer_edge_x_m <= self.inner_edge_x_m:
            raise ValueError("walkway outer edge must lie outside inner edge")
        if not math.isclose(
            self.outer_edge_x_m - self.inner_edge_x_m,
            self.top_clear_width_m,
            abs_tol=1e-12,
        ):
            raise ValueError("walkway width must match inner/outer edge difference")
        if not self.sources:
            raise ValueError("walkway requires provenance")


@dataclass(frozen=True)
class MoscowCableRackProfile:
    family: str
    assembly_designation: str
    upright_designation: str
    horn_designation: str
    overall_arc_length_m: float
    upright_width_longitudinal_m: float
    upright_thickness_m: float
    horn_count: int
    horn_thickness_m: float
    horn_radius_m: float
    horn_overall_length_m: float
    horn_overall_height_m: float
    cable_places_per_horn: int
    occupied_places_per_horn: int
    max_cable_diameter_m: float
    horn_pitch_m: float
    repeat_pitch_m: float
    phase_m: float
    center_profile_z_m: float
    negative_side_center_profile_z_m: float
    shell_clearance_inward_m: float
    horn_longitudinal_width_m: float
    first_cable_center_inward_m: float
    second_cable_center_inward_m: float
    representative_cable_diameter_m: float
    cable_circle_vertices: int
    occupied_level_indices: tuple[int, ...]
    cable_sag_midspan_m: float
    cable_sag_variation_fraction: float
    cable_sag_peak_phase_jitter_fraction: float

    def __post_init__(self) -> None:
        positive = (
            self.overall_arc_length_m,
            self.upright_width_longitudinal_m,
            self.upright_thickness_m,
            self.horn_thickness_m,
            self.horn_radius_m,
            self.horn_overall_length_m,
            self.horn_overall_height_m,
            self.max_cable_diameter_m,
            self.horn_pitch_m,
            self.repeat_pitch_m,
            self.shell_clearance_inward_m,
            self.horn_longitudinal_width_m,
            self.first_cable_center_inward_m,
            self.second_cable_center_inward_m,
            self.representative_cable_diameter_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("cable-rack dimensions must be finite and positive")
        if self.horn_count <= 0 or self.cable_circle_vertices < 6:
            raise ValueError("cable-rack horn/circle counts are invalid")
        if not math.isfinite(self.negative_side_center_profile_z_m):
            raise ValueError("negative-side cable-rack center must be finite")
        if self.cable_sag_midspan_m < 0.0 or not math.isfinite(
            self.cable_sag_midspan_m
        ):
            raise ValueError("cable sag must be finite and non-negative")
        if (
            not math.isfinite(self.cable_sag_variation_fraction)
            or not (0.0 <= self.cable_sag_variation_fraction <= 0.75)
        ):
            raise ValueError("cable sag variation fraction must be in [0, 0.75]")
        if (
            not math.isfinite(self.cable_sag_peak_phase_jitter_fraction)
            or not (0.0 <= self.cable_sag_peak_phase_jitter_fraction <= 0.25)
        ):
            raise ValueError("cable sag peak-phase jitter must be in [0, 0.25]")
        if (
            not self.occupied_level_indices
            or len(set(self.occupied_level_indices)) != len(self.occupied_level_indices)
            or any(
                level < 0 or level >= self.horn_count
                for level in self.occupied_level_indices
            )
        ):
            raise ValueError("occupied R2K11 levels must be unique valid horn indices")
        if self.cable_places_per_horn != 2:
            raise ValueError("R2K11 double horn must expose two cable places")
        if not (1 <= self.occupied_places_per_horn <= self.cable_places_per_horn):
            raise ValueError("cable-rack occupied places exceed horn capacity")
        if not (0.0 <= self.phase_m < self.repeat_pitch_m):
            raise ValueError("cable-rack phase must lie within repeat pitch")
        if self.representative_cable_diameter_m > self.max_cable_diameter_m:
            raise ValueError("representative cable exceeds rack capacity")
        if self.second_cable_center_inward_m <= self.first_cable_center_inward_m:
            raise ValueError("second cable place must lie farther inward")
        if not self.family or not self.assembly_designation:
            raise ValueError("cable-rack family/designation must not be empty")
        if not self.upright_designation or not self.horn_designation:
            raise ValueError("cable-rack component designations must not be empty")


@dataclass(frozen=True)
class MoscowWaterMainProfile:
    min_nominal_dn_mm: int
    quantity_single_track_tunnel: int
    side_profile_x_sign: int
    preview_outer_diameter_m: float
    center_profile_z_m: float
    shell_clearance_inward_m: float
    support_max_pitch_m: float
    support_geometry_mode: str
    placement_mode: str
    outer_diameter_mode: str
    material_family: str
    normative_source: str
    confidence: str

    def __post_init__(self) -> None:
        if self.min_nominal_dn_mm < 80:
            raise ValueError("modern tunnel water main must remain at least DN80")
        if self.quantity_single_track_tunnel != 1:
            raise ValueError("single-track modern preset requires one water main")
        if self.side_profile_x_sign not in (-1, 1):
            raise ValueError("water-main side sign must be +/-1")
        if (
            not math.isfinite(self.preview_outer_diameter_m)
            or self.preview_outer_diameter_m <= 0.0
        ):
            raise ValueError("water-main preview diameter must be positive")
        if (
            not math.isfinite(self.shell_clearance_inward_m)
            or self.shell_clearance_inward_m <= 0.0
        ):
            raise ValueError("water-main shell clearance must be positive")
        if not math.isfinite(self.center_profile_z_m):
            raise ValueError("water-main center z must be finite")
        if (
            not math.isfinite(self.support_max_pitch_m)
            or self.support_max_pitch_m <= 0.0
            or self.support_max_pitch_m > 4.0 + 1e-12
        ):
            raise ValueError("water-main support pitch must be positive and <=4 m")
        if not self.support_geometry_mode:
            raise ValueError("water-main support geometry mode must not be empty")
        if self.center_profile_z_m <= 0.0:
            raise ValueError("water main must remain above UGR")
        if not self.normative_source:
            raise ValueError("water main requires normative provenance")


@dataclass(frozen=True)
class MoscowModernPermanentWayProfile:
    preset_id: str
    support_pitch_m: float
    block_top_width_m: float
    block_height_m: float
    block_base_length_transverse_m: float
    block_base_width_wide_m: float
    block_base_width_narrow_m: float
    rail_seat_recess_m: float
    rail_seat_cant_ratio: float
    boot_inner_length_m: float
    boot_bottom_inner_length_m: float
    boot_bottom_width_wide_m: float
    boot_bottom_width_narrow_m: float
    boot_side_height_m: float
    boot_preview_wall_thickness_m: float
    fastening_family: str
    rail_pad_thickness_m: float
    rail_pad_plan_transverse_m: float
    rail_pad_plan_longitudinal_m: float
    clamps_per_rail_seat: int
    monoregulators_per_rail_seat: int
    underclamp_pieces_per_rail_seat: int
    insulating_angles_per_rail_seat: int
    anchors_per_rail_seat: int
    clamp_preview_transverse_m: float
    clamp_preview_longitudinal_m: float
    clamp_preview_height_m: float
    monoregulator_preview_radius_m: float
    fastening_mesh_mode: str

    def __post_init__(self) -> None:
        vals = (
            self.support_pitch_m,
            self.block_top_width_m,
            self.block_height_m,
            self.block_base_length_transverse_m,
            self.block_base_width_wide_m,
            self.block_base_width_narrow_m,
            self.rail_seat_recess_m,
            self.rail_seat_cant_ratio,
            self.boot_inner_length_m,
            self.boot_bottom_inner_length_m,
            self.boot_bottom_width_wide_m,
            self.boot_bottom_width_narrow_m,
            self.boot_side_height_m,
            self.boot_preview_wall_thickness_m,
            self.rail_pad_thickness_m,
            self.rail_pad_plan_transverse_m,
            self.rail_pad_plan_longitudinal_m,
            self.clamp_preview_transverse_m,
            self.clamp_preview_longitudinal_m,
            self.clamp_preview_height_m,
            self.monoregulator_preview_radius_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in vals):
            raise ValueError("modern permanent-way dimensions must be positive")
        if self.block_base_width_narrow_m >= self.block_base_width_wide_m:
            raise ValueError("LVT-M narrow base width must be less than wide width")
        if self.boot_bottom_inner_length_m > self.boot_inner_length_m:
            raise ValueError("LVT boot bottom length cannot exceed opening length")
        if not self.preset_id or not self.fastening_family:
            raise ValueError("modern permanent-way identifiers must not be empty")
        counts = (
            self.clamps_per_rail_seat,
            self.monoregulators_per_rail_seat,
            self.underclamp_pieces_per_rail_seat,
            self.insulating_angles_per_rail_seat,
            self.anchors_per_rail_seat,
        )
        if any(v <= 0 for v in counts):
            raise ValueError("modern APC-4 component counts must be positive")


@dataclass(frozen=True)
class MoscowModernContactRailProfile:
    preset_id: str
    cover_top_width_m: float
    cover_base_width_m: float
    cover_height_m: float
    cover_side_wall_m: float
    cover_top_wall_m: float
    cover_lower_edge_above_contact_surface_m: float
    cover_span_overlap_m: float
    support_block_height_m: float
    support_dowel_length_m: float
    support_target_pitch_m: float
    support_normative_min_m: float
    support_normative_max_m: float
    running_support_exclusion_half_length_m: float
    bracket_longitudinal_thickness_m: float
    bracket_channel_band_thickness_m: float
    bracket_top_plate_width_m: float
    bracket_top_plate_thickness_m: float
    insulator_height_m: float
    insulator_diameter_m: float
    support_hood_length_m: float
    support_hood_extra_width_m: float
    support_hood_extra_height_m: float
    drawing_reference_to_axis_m: float
    drawing_reference_to_outer_envelope_m: float
    drawing_upper_return_m: float
    drawing_top_above_ugr_m: float
    drawing_lower_bend_callout_m: float
    drawing_upper_bend_callout_m: float
    bracket_lower_bend_radius_m: float
    bracket_upper_bend_radius_m: float
    minimum_clearance_to_lvt_block_m: float
    base_plate_transverse_m: float
    base_plate_longitudinal_m: float
    base_plate_thickness_m: float
    base_plate_anchor_pitch_transverse_m: float
    base_plate_anchor_pitch_longitudinal_m: float
    base_plate_anchor_count: int
    clamp_bridge_width_m: float
    clamp_bridge_thickness_m: float
    clamp_jaw_thickness_m: float
    clamp_jaw_height_m: float
    clamp_bolt_count: int
    clamp_bolt_diameter_m: float
    clamp_bolt_head_radius_m: float
    clamp_bolt_head_height_m: float

    def __post_init__(self) -> None:
        vals = (
            self.cover_top_width_m,
            self.cover_base_width_m,
            self.cover_height_m,
            self.cover_side_wall_m,
            self.cover_top_wall_m,
            self.cover_lower_edge_above_contact_surface_m,
            self.cover_span_overlap_m,
            self.support_block_height_m,
            self.support_dowel_length_m,
            self.support_target_pitch_m,
            self.support_normative_min_m,
            self.support_normative_max_m,
            self.running_support_exclusion_half_length_m,
            self.bracket_longitudinal_thickness_m,
            self.bracket_channel_band_thickness_m,
            self.bracket_top_plate_width_m,
            self.bracket_top_plate_thickness_m,
            self.insulator_height_m,
            self.insulator_diameter_m,
            self.support_hood_length_m,
            self.support_hood_extra_width_m,
            self.support_hood_extra_height_m,
            self.drawing_reference_to_axis_m,
            self.drawing_reference_to_outer_envelope_m,
            self.drawing_upper_return_m,
            self.drawing_top_above_ugr_m,
            self.drawing_lower_bend_callout_m,
            self.drawing_upper_bend_callout_m,
            self.bracket_lower_bend_radius_m,
            self.bracket_upper_bend_radius_m,
            self.minimum_clearance_to_lvt_block_m,
            self.base_plate_transverse_m,
            self.base_plate_longitudinal_m,
            self.base_plate_thickness_m,
            self.base_plate_anchor_pitch_transverse_m,
            self.base_plate_anchor_pitch_longitudinal_m,
            self.clamp_bridge_width_m,
            self.clamp_bridge_thickness_m,
            self.clamp_jaw_thickness_m,
            self.clamp_jaw_height_m,
            self.clamp_bolt_diameter_m,
            self.clamp_bolt_head_radius_m,
            self.clamp_bolt_head_height_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in vals):
            raise ValueError("modern contact-rail dimensions must be positive")
        if self.cover_top_wall_m >= self.cover_height_m:
            raise ValueError("modern contact cover top wall is invalid")
        if 2.0 * self.cover_side_wall_m >= self.cover_base_width_m:
            raise ValueError("modern contact cover side walls are invalid")
        if not (
            self.support_normative_min_m
            <= self.support_target_pitch_m
            <= self.support_normative_max_m
        ):
            raise ValueError("modern contact support target pitch outside normative range")
        if self.base_plate_anchor_count != 4:
            raise ValueError("dimensioned contact-support base plate requires four anchors")
        if self.clamp_bolt_count != 2:
            raise ValueError("dimensioned over-rail clamp requires two bolts")
        if self.drawing_reference_to_outer_envelope_m <= self.drawing_reference_to_axis_m:
            raise ValueError("contact-support drawing outer envelope must lie outboard of axis")
        if not self.preset_id:
            raise ValueError("modern contact-rail preset id must not be empty")


@dataclass(frozen=True)
class MoscowContactRailProfile:
    side_profile_x_sign: int
    collection: str
    horizontal_from_inner_working_face_m: float
    horizontal_tolerance_m: float
    working_surface_z_m: float
    vertical_tolerance_m: float
    rail_family: str
    rail_overall_height_m: float
    rail_top_width_m: float
    rail_base_width_m: float
    rail_web_width_m: float
    rail_vertical_callouts_m: tuple[float, ...]
    rail_profile_source: str
    rail_profile_mode: str
    rail_profile_confidence: str
    rail_profile_era_warning: str
    cover_historical_vertical_envelope_m: float
    cover_outer_top_width_m: float
    cover_outer_base_width_m: float
    cover_height_m: float
    cover_side_wall_m: float
    cover_top_wall_m: float
    cover_lower_edge_above_contact_surface_m: float
    cover_mode: str
    cover_era_mismatch: bool
    cover_historical_side_gap_m: float
    cover_box_gap_m: float
    cover_box_to_insulator_gap_m: float
    cover_support_offset_from_box_end_m: float
    support_resource_envelope_m: tuple[float, float, float]
    support_target_pitch_m: float
    support_target_phase_m: float
    support_normative_min_m: float
    support_normative_max_m: float
    support_snap_to_sleeper: bool
    support_geometry_mode: str
    support_longitudinal_thickness_m: float
    support_channel_band_thickness_m: float
    support_sleeper_end_attachment_inset_m: float
    support_upper_outboard_clearance_from_rail_m: float
    insulator_axial_length_m: float
    insulator_diameter_m: float
    insulator_mode: str

    def __post_init__(self) -> None:
        if self.side_profile_x_sign not in (-1, 1):
            raise ValueError("contact-rail profile-X side sign must be +/-1")
        if self.collection != "bottom":
            raise ValueError("initial Moscow contact rail requires bottom collection")
        positive = (
            self.horizontal_from_inner_working_face_m,
            self.horizontal_tolerance_m,
            self.working_surface_z_m,
            self.vertical_tolerance_m,
            self.rail_overall_height_m,
            self.rail_top_width_m,
            self.rail_base_width_m,
            self.rail_web_width_m,
            self.cover_historical_vertical_envelope_m,
            self.cover_outer_top_width_m,
            self.cover_outer_base_width_m,
            self.cover_height_m,
            self.cover_side_wall_m,
            self.cover_top_wall_m,
            self.cover_lower_edge_above_contact_surface_m,
            self.cover_historical_side_gap_m,
            self.cover_box_gap_m,
            self.cover_box_to_insulator_gap_m,
            self.cover_support_offset_from_box_end_m,
            self.support_target_pitch_m,
            self.support_target_phase_m,
            self.support_normative_min_m,
            self.support_normative_max_m,
            self.support_longitudinal_thickness_m,
            self.support_channel_band_thickness_m,
            self.support_sleeper_end_attachment_inset_m,
            self.support_upper_outboard_clearance_from_rail_m,
            self.insulator_axial_length_m,
            self.insulator_diameter_m,
            *self.rail_vertical_callouts_m,
            *self.support_resource_envelope_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("contact-rail dimensions must be finite and positive")
        if self.rail_web_width_m >= min(
            self.rail_top_width_m,
            self.rail_base_width_m,
        ):
            raise ValueError("contact-rail web must be narrower than head/base")
        if self.cover_side_wall_m * 2.0 >= self.cover_outer_base_width_m:
            raise ValueError("contact-rail cover side walls consume base width")
        if self.cover_top_wall_m >= self.cover_height_m:
            raise ValueError("contact-rail cover top wall must fit inside height")
        if self.support_normative_min_m >= self.support_normative_max_m:
            raise ValueError("contact-rail support pitch range is invalid")
        if not (
            self.support_normative_min_m
            <= self.support_target_pitch_m
            <= self.support_normative_max_m
        ):
            raise ValueError("contact-rail target pitch must lie in normative range")
        if not (0.0 <= self.support_target_phase_m < self.support_target_pitch_m):
            raise ValueError("contact-rail support phase must lie in one pitch")
        clear_base = (
            self.cover_outer_base_width_m - 2.0 * self.cover_side_wall_m
        )
        required_clear = (
            self.rail_base_width_m + 2.0 * self.cover_historical_side_gap_m
        )
        if clear_base + 1e-12 < required_clear:
            raise ValueError(
                "contact-rail cover fallback violates historical side clearance"
            )
        if not math.isclose(
            self.cover_lower_edge_above_contact_surface_m + self.cover_height_m,
            self.cover_historical_vertical_envelope_m,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "contact-rail cover fallback must preserve historical "
                "working-surface-to-cover-top envelope"
            )



@dataclass(frozen=True)
class MoscowProfileProvenance:
    source_path: str | None
    source_pinpoints_file: str
    source_ids: tuple[str, ...]
    canonical_sha256: str


@dataclass(frozen=True)
class MoscowStage10Profile:
    schema_version: str
    profile_id: str
    purpose: str
    coordinate: MoscowCoordinateContract
    datums: MoscowDatums
    track: MoscowTrackProfile
    sleeper: MoscowTimberSleeperProfile
    fastening: MoscowKD65Profile
    track_concrete: MoscowTrackConcreteProfile
    contact_rail: MoscowContactRailProfile
    modern_contact_rail: MoscowModernContactRailProfile
    modern_permanent_way: MoscowModernPermanentWayProfile
    cable_rack: MoscowCableRackProfile
    water_main: MoscowWaterMainProfile
    default_service_preset: str
    walkway: MoscowWalkwayProfile
    civil_geometry_mode: str
    civil_segment_surface_mode: str
    civil_family: str
    intrados_radius_m: float
    extrados_radius_m: float
    ring_pitch_m: float
    provenance: MoscowProfileProvenance
    _canonical_json: str = field(repr=False, compare=False)

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, Any],
        *,
        source_path: str | Path | None = None,
    ) -> "MoscowStage10Profile":
        raw = deepcopy(dict(mapping))
        canonical = json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        coord = raw["coordinate_system"]
        mapping_contract = coord["core_mapping"]
        civil = raw["civil_lining"]
        civil_geom_raw = civil["initial_geometry"]
        intrados = civil["intrados"]
        extrados = civil["extrados"]
        landmarks = civil["vertical_landmarks"]
        track = raw["running_rail_and_track"]
        gauge_definition = track["gauge_definition"]
        sleeper_raw = track["timber_sleeper"]
        sleeper_top_raw = track["sleeper_top_z_m"]
        sleeper_bottom_raw = track["sleeper_bottom_z_m"]
        sleeper_density_raw = track["sleeper_density_per_km"]
        fastening_raw = track["fastening"]
        baseplate_raw = fastening_raw["baseplate"]
        baseplate_mesh_raw = baseplate_raw["initial_mesh_profile"]
        under_pad_raw = fastening_raw["under_baseplate_pad"]
        rail_pad_raw = fastening_raw["rail_pad"]
        track_screw_raw = fastening_raw["track_screw"]
        screw_head_raw = track_screw_raw["initial_visual_head"]
        clamp_geometry_raw = fastening_raw["initial_clamp_geometry"]
        concrete_raw = raw["track_concrete_and_invert"]
        drain_raw = concrete_raw["central_drain"]
        groove_raw = concrete_raw["water_release_groove"]
        walkway_raw = raw["walkway"]
        walkway_geom_raw = walkway_raw["initial_geometry"]
        contact_raw = raw["contact_rail"]
        modern_contact_raw = contact_raw["modern_service_preset"]
        modern_pw_raw = raw["modern_permanent_way"]
        service_presets_raw = raw["service_era_presets"]
        service_infra_raw = raw["modern_service_infrastructure"]
        cable_rack_raw = service_infra_raw["cable_rack"]
        cable_rack_place_raw = cable_rack_raw["placement"]
        cable_horn_mesh_raw = cable_rack_raw["initial_horn_mesh"]
        cable_preview_raw = service_infra_raw["cable_preview"]
        water_main_raw = service_infra_raw["pipes"]["water_main"]
        modern_cover_raw = modern_contact_raw["cover"]
        modern_cover_place_raw = modern_cover_raw["placement"]
        modern_support_raw = modern_contact_raw["support"]
        modern_support_schedule_raw = modern_support_raw["schedule"]
        modern_bracket_raw = modern_support_raw["bracket"]
        modern_insulator_raw = modern_support_raw["insulator"]
        modern_pw_block_raw = modern_pw_raw["block"]
        modern_pw_boot_raw = modern_pw_raw["rubber_boot"]
        modern_pw_install_raw = modern_pw_raw["installation"]
        modern_fastening_source_raw = modern_pw_raw["fastening_details"]
        modern_pad_source_raw = modern_fastening_source_raw["under_rail_pad"]
        modern_component_source_raw = modern_fastening_source_raw["component_topology"]
        contact_place_raw = contact_raw["placement"]
        contact_profile_raw = contact_raw["rail_profile"]
        contact_mesh_raw = contact_profile_raw["initial_mesh_profile"]
        contact_protect_raw = contact_raw["protective_assembly"]
        contact_cover_raw = contact_protect_raw["cover_profile"]
        contact_cover_effective_raw = contact_cover_raw[
            "effective_initial_geometry"
        ]
        contact_cover_hist_raw = contact_cover_raw["historical_constraints"]
        contact_support_raw = contact_raw["support"]
        contact_support_geom_raw = contact_support_raw["initial_geometry"]
        contact_support_schedule_raw = contact_support_raw["schedule"]
        contact_insulator_raw = contact_raw["insulator"]
        contact_insulator_geom_raw = contact_insulator_raw["initial_geometry"]

        source_ids: list[str] = []
        for candidate in (
            intrados.get("source"),
            track.get("rail_profile_source_id"),
            sleeper_top_raw.get("source"),
            sleeper_raw.get("source"),
            sleeper_density_raw.get("source"),
            fastening_raw.get("source_assembly"),
            baseplate_raw.get("historical_album_source"),
            under_pad_raw.get("source"),
            rail_pad_raw.get("source"),
            concrete_raw.get("source"),
            groove_raw.get("source"),
            *walkway_raw.get("sources", ()),
            contact_place_raw.get("source"),
            contact_profile_raw.get("source"),
            contact_cover_raw.get("initial_geometry_source"),
            contact_cover_hist_raw.get("source"),
            contact_support_raw.get("source"),
            contact_support_schedule_raw.get("source"),
            contact_insulator_raw.get("source"),
            modern_cover_raw.get("source"),
            modern_cover_place_raw.get("source"),
            modern_support_raw.get("source"),
            modern_bracket_raw.get("source"),
            modern_insulator_raw.get("source"),
            modern_pw_raw.get("source_pitch"),
            modern_pw_block_raw.get("source"),
            modern_pw_boot_raw.get("source"),
            modern_pw_install_raw.get("source"),
            modern_pad_source_raw.get("source"),
            modern_component_source_raw.get("source"),
            *cable_rack_raw.get("sources", ()),
            water_main_raw.get("normative_source"),
            water_main_raw.get("support_source"),
            *contact_support_geom_raw.get("sources", ()),
            *drain_raw.get("sources", ()),
            *gauge_definition.get("sources", ()),
        ):
            if candidate and candidate not in source_ids:
                source_ids.append(str(candidate))

        coordinate = MoscowCoordinateContract(
            units=str(coord["units"]),
            origin_description=str(coord["origin"]),
            lateral_positive_description=str(coord["x_positive"]),
            z_positive_description=str(coord["z_positive"]),
            ugr_z_m=float(coord["ugr_z_m"]),
            profile_x_to_core_x_sign=int(
                mapping_contract["profile_x_to_core_x_sign"]
            ),
            engineering_route_left_to_profile_x_sign=int(
                mapping_contract["engineering_route_left_to_profile_x_sign"]
            ),
            profile_z_to_core_z_offset_m=-float(
                landmarks["lining_axis_z_m"]
            ),
        )
        datums = MoscowDatums(
            ugr_z_m=coordinate.ugr_z_m,
            track_axis_x_m=0.0,
            track_axis_z_m=coordinate.ugr_z_m,
            lining_axis_x_m=float(intrados["center_x_m"]),
            lining_axis_z_m=float(landmarks["lining_axis_z_m"]),
            intrados_invert_z_m=float(landmarks["intrados_invert_z_m"]),
            intrados_crown_z_m=float(landmarks["intrados_crown_z_m"]),
            extrados_invert_z_m=float(landmarks["extrados_invert_z_m"]),
            extrados_crown_z_m=float(landmarks["extrados_crown_z_m"]),
        )
        track_profile = MoscowTrackProfile(
            service_preset=str(track["service_preset"]),
            rail_type=str(track["rail_type"]),
            gauge_m=float(track["gauge_m"]),
            rail_height_m=float(track["rail_height_m"]),
            ugr_definition=str(track["ugr_definition"]),
            gauge_measurement_below_ugr_m=float(
                gauge_definition["measurement_level_below_ugr_m"]
            ),
            gauge_measurement_sources=tuple(
                str(v) for v in gauge_definition["sources"]
            ),
            rail_profile_source=str(track["rail_profile_source"]),
        )

        sleeper_profile = MoscowTimberSleeperProfile(
            top_z_m=float(sleeper_top_raw["value"]),
            bottom_z_m=float(sleeper_bottom_raw["value"]),
            length_m=float(sleeper_raw["length_m"]),
            thickness_m=float(sleeper_raw["thickness_m"]),
            upper_face_width_m=float(sleeper_raw["upper_face_width_m"]),
            lower_face_width_m=float(sleeper_raw["lower_face_width_m"]),
            sawn_side_height_m=float(sleeper_raw["sawn_side_height_m"]),
            density_per_km=float(
                sleeper_density_raw["straight_and_radius_ge_1200"]
            ),
            source=str(sleeper_raw["source"]),
        )

        orientation = baseplate_raw["plan_orientation"]
        seat = baseplate_raw["initial_rail_seat_height_m"]
        kd65_profile = MoscowKD65Profile(
            baseplate_transverse_m=float(baseplate_raw["overall_plan_length_m"]),
            baseplate_longitudinal_m=float(baseplate_raw["overall_plan_width_m"]),
            baseplate_max_height_m=float(
                baseplate_raw["maximum_section_envelope_height_m"]
            ),
            baseplate_rail_seat_height_m=float(seat["value"]),
            baseplate_hole_spacing_transverse_m=float(
                orientation["hole_center_spacing_transverse_x_m"]
            ),
            baseplate_hole_spacing_longitudinal_m=float(
                orientation["hole_center_spacing_longitudinal_y_m"]
            ),
            baseplate_hole_diameter_m=float(
                baseplate_raw["holes"]["diameter_m"]
            ),
            baseplate_outer_wing_top_height_m=float(
                baseplate_mesh_raw["outer_wing_top_height_m"]
            ),
            baseplate_shoulder_inner_x_m=float(
                baseplate_mesh_raw["shoulder_inner_x_m"]
            ),
            baseplate_shoulder_outer_x_m=float(
                baseplate_mesh_raw["shoulder_outer_x_m"]
            ),
            baseplate_rail_seat_half_width_m=float(
                baseplate_mesh_raw["rail_seat_half_width_m"]
            ),
            under_pad_transverse_m=float(under_pad_raw["overall_plan_m"][0]),
            under_pad_longitudinal_m=float(under_pad_raw["overall_plan_m"][1]),
            under_pad_thickness_m=float(under_pad_raw["thickness_m"]),
            under_pad_hole_diameter_m=float(
                under_pad_raw["holes"]["diameter_m"]
            ),
            rail_pad_transverse_m=float(rail_pad_raw["overall_plan_m"][0]),
            rail_pad_longitudinal_m=float(rail_pad_raw["overall_plan_m"][1]),
            rail_pad_base_thickness_m=float(rail_pad_raw["base_thickness_m"]),
            rail_pad_total_thickness_m=float(
                rail_pad_raw["raised_total_thickness_m"]
            ),
            rail_pad_raised_seat_transverse_m=float(
                rail_pad_raw["raised_seat_length_m"]
            ),
            track_screw_diameter_m=float(track_screw_raw["diameter_m"]),
            track_screw_length_m=float(track_screw_raw["length_m"]),
            track_screws_per_baseplate=int(
                track_screw_raw["quantity_per_baseplate"]
            ),
            track_screw_head_radius_m=float(screw_head_raw["radius_m"]),
            track_screw_head_height_m=float(screw_head_raw["height_m"]),
            clamp_bolt_diameter_m=float(
                fastening_raw["clamp_bolt"]["thread"].removeprefix("M")
            ) / 1000.0,
            clamp_bolt_length_m=float(
                fastening_raw["clamp_bolt"]["length_m"]
            ),
            clamp_bolts_per_baseplate=int(
                fastening_raw["clamp_bolt"]["quantity_per_baseplate"]
            ),
            nut_height_m=float(fastening_raw["nut"]["height_m"]),
            nuts_per_baseplate=int(
                fastening_raw["nut"]["quantity_per_baseplate"]
            ),
            spring_clamps_per_baseplate=int(
                fastening_raw["spring_clamp"]["quantity_per_baseplate"]
            ),
            clamp_bolt_axis_offset_m=float(
                clamp_geometry_raw["clamp_bolt_axis_offset_from_rail_center_m"]
            ),
            nut_circumradius_m=float(
                clamp_geometry_raw["nut_circumradius_m"]
            ),
            spring_clamp_center_offset_m=float(
                clamp_geometry_raw[
                    "spring_clamp_center_offset_from_rail_center_m"
                ]
            ),
            spring_clamp_box_transverse_m=float(
                clamp_geometry_raw["spring_clamp_box_transverse_m"]
            ),
            spring_clamp_box_longitudinal_m=float(
                clamp_geometry_raw["spring_clamp_box_longitudinal_m"]
            ),
            spring_clamp_box_height_m=float(
                clamp_geometry_raw["spring_clamp_box_height_m"]
            ),
            spring_clamp_base_above_rail_seat_m=float(
                clamp_geometry_raw["spring_clamp_base_above_rail_seat_m"]
            ),
            baseplate_mesh_mode=str(baseplate_mesh_raw["mode"]),
            track_screw_head_mode=str(screw_head_raw["mode"]),
            clamp_geometry_mode=str(clamp_geometry_raw["mode"]),
            family=str(fastening_raw["family"]),
        )

        concrete_reference = concrete_raw["shoulder_geometry"][
            "initial_surface_reference"
        ]
        groove_position = groove_raw["initial_position"]
        concrete_profile = MoscowTrackConcreteProfile(
            surface_cross_slope_to_drain=float(
                concrete_raw["surface_cross_slope_to_drain"]
            ),
            surface_reference_abs_x_m=float(
                concrete_reference["reference_abs_x_m"]
            ),
            surface_reference_z_m=float(concrete_reference["reference_z_m"]),
            minimum_bottom_at_rail_z_m=float(
                concrete_raw[
                    "derived_min_concrete_bottom_z_at_rail_on_straight_m"
                ]["value"]
            ),
            central_drain_center_x_m=float(drain_raw["center_x_m"]),
            central_drain_clear_width_m=float(drain_raw["clear_width_m"]),
            central_drain_bottom_z_m=-float(
                drain_raw["depth_from_ugr_m"]["initial_geometry_value"]
            ),
            water_groove_width_m=float(groove_raw["width_m"]),
            water_groove_depth_m=float(groove_raw["depth_m"]),
            water_groove_center_x_m=float(groove_position["center_x_m"]),
            concrete_material=str(concrete_raw["material"]),
            surface_reference_mode=str(concrete_reference["mode"]),
            groove_position_mode=str(groove_position["mode"]),
        )

        walkway_side = str(walkway_raw["side"])
        if walkway_side == "x_positive_opposite_contact_rail":
            walkway_side_sign = 1
        elif walkway_side == "x_negative_opposite_contact_rail":
            walkway_side_sign = -1
        else:
            raise ValueError(f"unsupported initial walkway side {walkway_side!r}")

        walkway_profile = MoscowWalkwayProfile(
            top_z_m=float(walkway_raw["top_z_m"]),
            inner_edge_x_m=float(walkway_raw["inner_edge_x_m"]),
            outer_edge_x_m=float(walkway_raw["outer_edge"]["x_m"]),
            top_clear_width_m=float(walkway_raw["top_clear_width_m"]["value"]),
            side_profile_x_sign=walkway_side_sign,
            geometry_mode=str(walkway_geom_raw["mode"]),
            service_era_interpretation=str(
                walkway_raw["service_era_interpretation"]
            ),
            sources=tuple(str(v) for v in walkway_raw["sources"]),
        )

        side_name = str(contact_raw["side"])
        if side_name == "x_negative_for_initial_profile":
            contact_side_sign = -1
        elif side_name == "x_positive_for_initial_profile":
            contact_side_sign = 1
        else:
            raise ValueError(f"unsupported initial contact-rail side {side_name!r}")

        contact_profile = MoscowContactRailProfile(
            side_profile_x_sign=contact_side_sign,
            collection=str(contact_raw["collection"]),
            horizontal_from_inner_working_face_m=float(
                contact_place_raw["horizontal_from_running_rail_reference_m"]
            ),
            horizontal_tolerance_m=float(
                contact_place_raw["horizontal_tolerance_m"]
            ),
            working_surface_z_m=float(
                contact_place_raw["working_surface_z_m"]
            ),
            vertical_tolerance_m=float(
                contact_place_raw["vertical_tolerance_m"]
            ),
            rail_family=str(contact_profile_raw["family"]),
            rail_overall_height_m=float(
                contact_profile_raw["overall_height_m"]
            ),
            rail_top_width_m=float(contact_profile_raw["top_width_m"]),
            rail_base_width_m=float(contact_profile_raw["base_width_m"]),
            rail_web_width_m=float(contact_profile_raw["web_width_m"]),
            rail_vertical_callouts_m=tuple(
                float(v)
                for v in contact_profile_raw["secondary_vertical_callouts_m"]
            ),
            rail_profile_source=str(contact_profile_raw["source"]),
            rail_profile_mode=str(contact_mesh_raw["mode"]),
            rail_profile_confidence=str(contact_mesh_raw["confidence"]),
            rail_profile_era_warning=str(contact_profile_raw["era_warning"]),
            cover_historical_vertical_envelope_m=float(
                contact_protect_raw["historical_overall_vertical_envelope_m"]
            ),
            cover_outer_top_width_m=float(
                contact_cover_effective_raw["outer_top_width_m"]
            ),
            cover_outer_base_width_m=float(
                contact_cover_effective_raw["outer_base_width_m"]
            ),
            cover_height_m=float(contact_cover_effective_raw["height_m"]),
            cover_side_wall_m=float(
                contact_cover_effective_raw["side_wall_m"]
            ),
            cover_top_wall_m=float(
                contact_cover_effective_raw["top_wall_m"]
            ),
            cover_lower_edge_above_contact_surface_m=float(
                contact_cover_effective_raw[
                    "lower_edge_z_above_contact_surface_m"
                ]
            ),
            cover_mode=str(contact_cover_effective_raw["mode"]),
            cover_era_mismatch=bool(
                contact_cover_effective_raw["era_mismatch"]
            ),
            cover_historical_side_gap_m=float(
                contact_cover_hist_raw["side_to_rail_head_gap_m"]
            ),
            cover_box_gap_m=float(
                contact_cover_hist_raw["gap_between_boxes_m"]
            ),
            cover_box_to_insulator_gap_m=float(
                contact_cover_hist_raw["gap_box_to_insulator_m"]
            ),
            cover_support_offset_from_box_end_m=float(
                contact_cover_hist_raw[
                    "fastening_support_offset_from_box_end_m"
                ]
            ),
            support_resource_envelope_m=tuple(
                float(v) for v in contact_support_raw["bracket_envelope_m"]
            ),
            support_target_pitch_m=float(
                contact_support_schedule_raw["target_pitch_m"]
            ),
            support_target_phase_m=float(
                contact_support_schedule_raw["target_phase_m"]
            ),
            support_normative_min_m=float(
                contact_support_schedule_raw["normative_min_m"]
            ),
            support_normative_max_m=float(
                contact_support_schedule_raw["normative_max_m"]
            ),
            support_snap_to_sleeper=bool(
                contact_support_schedule_raw["snap_to_nearest_timber_sleeper"]
            ),
            support_geometry_mode=str(contact_support_geom_raw["mode"]),
            support_longitudinal_thickness_m=float(
                contact_support_geom_raw["longitudinal_thickness_m"]
            ),
            support_channel_band_thickness_m=float(
                contact_support_geom_raw["channel_band_thickness_m"]
            ),
            support_sleeper_end_attachment_inset_m=float(
                contact_support_geom_raw["sleeper_end_attachment_inset_m"]
            ),
            support_upper_outboard_clearance_from_rail_m=float(
                contact_support_geom_raw[
                    "upper_outboard_clearance_from_rail_m"
                ]
            ),
            insulator_axial_length_m=float(
                contact_insulator_geom_raw["axial_length_m"]
            ),
            insulator_diameter_m=float(
                contact_insulator_geom_raw["diameter_m"]
            ),
            insulator_mode=str(contact_insulator_geom_raw["mode"]),
        )

        modern_cover_raw = modern_contact_raw["cover"]
        modern_cover_place_raw = modern_cover_raw["placement"]
        modern_support_raw = modern_contact_raw["support"]
        modern_support_schedule_raw = modern_support_raw["schedule"]
        modern_bracket_raw = modern_support_raw["bracket"]
        modern_insulator_raw = modern_support_raw["insulator"]
        modern_hood_raw = modern_support_raw["support_hood"]
        modern_drawing_raw = modern_support_raw["dimensioned_drawing"]
        modern_drawing_callouts_raw = modern_drawing_raw["readable_callouts_m"]
        modern_clamp_raw = modern_support_raw["clamp"]
        modern_anchor_pattern = tuple(
            float(v) for v in modern_bracket_raw["base_plate_anchor_pattern_m"]
        )
        if len(modern_anchor_pattern) != 2:
            raise ValueError("modern contact-support anchor pattern must have two pitches")
        modern_contact_profile = MoscowModernContactRailProfile(
            preset_id=str(modern_contact_raw["id"]),
            cover_top_width_m=float(modern_cover_raw["top_width_m"]),
            cover_base_width_m=float(modern_cover_raw["base_width_m"]),
            cover_height_m=float(modern_cover_raw["height_m"]),
            cover_side_wall_m=float(modern_cover_raw["side_wall_m"]),
            cover_top_wall_m=float(modern_cover_raw["top_wall_m"]),
            cover_lower_edge_above_contact_surface_m=float(
                modern_cover_place_raw["lower_edge_above_contact_surface_m"]
            ),
            cover_span_overlap_m=float(
                modern_cover_raw["span_installation"]["overlap_between_polymer_spans_m"]
            ),
            support_block_height_m=float(modern_support_raw["block_height_m"]),
            support_dowel_length_m=float(modern_support_raw["polymer_dowel_length_m"]),
            support_target_pitch_m=float(modern_support_schedule_raw["target_pitch_m"]),
            support_normative_min_m=float(modern_support_schedule_raw["normative_min_m"]),
            support_normative_max_m=float(modern_support_schedule_raw["normative_max_m"]),
            running_support_exclusion_half_length_m=float(
                modern_support_schedule_raw["running_support_exclusion_half_length_m"]
            ),
            bracket_longitudinal_thickness_m=float(
                modern_bracket_raw["longitudinal_thickness_m"]
            ),
            bracket_channel_band_thickness_m=float(
                modern_bracket_raw["channel_band_thickness_m"]
            ),
            bracket_top_plate_width_m=float(modern_bracket_raw["top_plate_width_m"]),
            bracket_top_plate_thickness_m=float(
                modern_bracket_raw["top_plate_thickness_m"]
            ),
            insulator_height_m=float(modern_insulator_raw["axial_height_m"]),
            insulator_diameter_m=float(modern_insulator_raw["diameter_m"]),
            support_hood_length_m=float(modern_hood_raw["longitudinal_length_m"]),
            support_hood_extra_width_m=float(
                modern_hood_raw["width_extra_over_main_cover_m"]
            ),
            support_hood_extra_height_m=float(
                modern_hood_raw["height_extra_over_main_cover_m"]
            ),
            drawing_reference_to_axis_m=float(
                modern_drawing_callouts_raw["running_reference_to_contact_axis"]
            ),
            drawing_reference_to_outer_envelope_m=float(
                modern_drawing_callouts_raw[
                    "running_reference_to_outer_bracket_envelope"
                ]
            ),
            drawing_upper_return_m=float(
                modern_drawing_callouts_raw["contact_axis_to_outer_upper_return"]
            ),
            drawing_top_above_ugr_m=float(
                modern_drawing_callouts_raw["top_above_ugr_reference"]
            ),
            drawing_lower_bend_callout_m=float(
                modern_drawing_callouts_raw["lower_bend_vertical_callout"]
            ),
            drawing_upper_bend_callout_m=float(
                modern_drawing_callouts_raw["upper_bend_vertical_callout"]
            ),
            bracket_lower_bend_radius_m=float(
                modern_bracket_raw["preview_lower_bend_radius_m"]
            ),
            bracket_upper_bend_radius_m=float(
                modern_bracket_raw["preview_upper_bend_radius_m"]
            ),
            minimum_clearance_to_lvt_block_m=float(
                modern_bracket_raw["minimum_clearance_to_lvt_block_m"]
            ),
            base_plate_transverse_m=float(
                modern_bracket_raw["base_plate_transverse_m"]
            ),
            base_plate_longitudinal_m=float(
                modern_bracket_raw["base_plate_longitudinal_m"]
            ),
            base_plate_thickness_m=float(
                modern_bracket_raw["base_plate_thickness_m"]
            ),
            base_plate_anchor_pitch_transverse_m=modern_anchor_pattern[0],
            base_plate_anchor_pitch_longitudinal_m=modern_anchor_pattern[1],
            base_plate_anchor_count=int(
                modern_bracket_raw["base_plate_anchor_count"]
            ),
            clamp_bridge_width_m=float(modern_clamp_raw["bridge_width_m"]),
            clamp_bridge_thickness_m=float(
                modern_clamp_raw["bridge_thickness_m"]
            ),
            clamp_jaw_thickness_m=float(
                modern_clamp_raw["jaw_thickness_m"]
            ),
            clamp_jaw_height_m=float(modern_clamp_raw["jaw_height_m"]),
            clamp_bolt_count=int(modern_clamp_raw["bolt_count"]),
            clamp_bolt_diameter_m=float(
                modern_clamp_raw["bolt_diameter_m"]
            ),
            clamp_bolt_head_radius_m=float(
                modern_clamp_raw["bolt_head_radius_m"]
            ),
            clamp_bolt_head_height_m=float(
                modern_clamp_raw["bolt_head_height_m"]
            ),
        )

        if not math.isclose(
            modern_contact_profile.drawing_reference_to_axis_m,
            contact_profile.horizontal_from_inner_working_face_m,
            abs_tol=contact_profile.horizontal_tolerance_m,
        ):
            raise ValueError(
                "dimensioned 683 mm support drawing must remain inside the "
                "690 +/- tolerance contact-rail placement contract"
            )
        if not math.isclose(
            modern_contact_profile.drawing_lower_bend_callout_m,
            contact_profile.working_surface_z_m,
            abs_tol=contact_profile.vertical_tolerance_m,
        ):
            raise ValueError(
                "dimensioned 155 mm support drawing must remain inside the "
                "+160 mm contact-surface height tolerance"
            )
        if abs(
            (
                modern_contact_profile.drawing_reference_to_outer_envelope_m
                - modern_contact_profile.drawing_reference_to_axis_m
            )
            - modern_contact_profile.drawing_upper_return_m
        ) > 0.015:
            raise ValueError(
                "873/683/180 mm support drawing callouts are mutually inconsistent"
            )
        if (
            modern_contact_profile.drawing_top_above_ugr_m
            <= contact_profile.working_surface_z_m
            + contact_profile.rail_overall_height_m
        ):
            raise ValueError("dimensioned bracket top must lie above contact rail")

        block_raw = modern_pw_raw["block"]
        boot_raw = modern_pw_raw["rubber_boot"]
        boot_mesh_raw = boot_raw["initial_mesh"]
        modern_fastening_raw = modern_pw_raw["fastening_details"]
        modern_pad_raw = modern_fastening_raw["under_rail_pad"]
        modern_fastening_topology_raw = modern_fastening_raw["component_topology"]
        modern_fastening_mesh_raw = modern_fastening_raw["initial_mesh"]
        cant_text = str(block_raw["rail_seat_cant"])
        if not cant_text.startswith("1:"):
            raise ValueError("modern LVT rail-seat cant must use 1:N notation")
        cant_ratio = 1.0 / float(cant_text.split(":", 1)[1])
        modern_pw_profile = MoscowModernPermanentWayProfile(
            preset_id=str(modern_pw_raw["id"]),
            support_pitch_m=float(modern_pw_raw["support_pitch_m"]),
            block_top_width_m=float(block_raw["top_width_at_rail_seat_m"]),
            block_height_m=float(block_raw["height_at_rail_seat_m"]),
            block_base_length_transverse_m=float(
                block_raw["base_length_transverse_m"]
            ),
            block_base_width_wide_m=float(block_raw["base_width_wide_m"]),
            block_base_width_narrow_m=float(block_raw["base_width_narrow_m"]),
            rail_seat_recess_m=float(block_raw["rail_seat_recess_m"]),
            rail_seat_cant_ratio=cant_ratio,
            boot_inner_length_m=float(boot_raw["inner_length_m"]),
            boot_bottom_inner_length_m=float(boot_raw["bottom_inner_length_m"]),
            boot_bottom_width_wide_m=float(boot_raw["bottom_width_wide_m"]),
            boot_bottom_width_narrow_m=float(boot_raw["bottom_width_narrow_m"]),
            boot_side_height_m=float(boot_raw["side_height_m"]),
            boot_preview_wall_thickness_m=float(
                boot_mesh_raw["preview_wall_thickness_m"]
            ),
            fastening_family=str(modern_pw_raw["fastening"]),
            rail_pad_thickness_m=float(modern_pad_raw["nominal_thickness_m"]),
            rail_pad_plan_transverse_m=float(
                modern_fastening_mesh_raw["rail_pad_plan_transverse_m"]
            ),
            rail_pad_plan_longitudinal_m=float(
                modern_fastening_mesh_raw["rail_pad_plan_longitudinal_m"]
            ),
            clamps_per_rail_seat=int(
                modern_fastening_topology_raw["clamps_per_rail_seat"]
            ),
            monoregulators_per_rail_seat=int(
                modern_fastening_topology_raw["monoregulators_per_rail_seat"]
            ),
            underclamp_pieces_per_rail_seat=int(
                modern_fastening_topology_raw["underclamp_pieces_per_rail_seat"]
            ),
            insulating_angles_per_rail_seat=int(
                modern_fastening_topology_raw["insulating_angles_per_rail_seat"]
            ),
            anchors_per_rail_seat=int(
                modern_fastening_topology_raw["anchors_per_rail_seat"]
            ),
            clamp_preview_transverse_m=float(
                modern_fastening_mesh_raw["clamp_preview_transverse_m"]
            ),
            clamp_preview_longitudinal_m=float(
                modern_fastening_mesh_raw["clamp_preview_longitudinal_m"]
            ),
            clamp_preview_height_m=float(
                modern_fastening_mesh_raw["clamp_preview_height_m"]
            ),
            monoregulator_preview_radius_m=float(
                modern_fastening_mesh_raw["monoregulator_preview_radius_m"]
            ),
            fastening_mesh_mode=str(modern_fastening_mesh_raw["mode"]),
        )

        cable_rack_profile = MoscowCableRackProfile(
            family=str(cable_rack_raw["family"]),
            assembly_designation=str(cable_rack_raw["assembly_designation"]),
            upright_designation=str(cable_rack_raw["upright_designation"]),
            horn_designation=str(cable_rack_raw["horn_designation"]),
            overall_arc_length_m=float(cable_rack_raw["overall_arc_length_m"]),
            upright_width_longitudinal_m=float(
                cable_rack_raw["upright_width_longitudinal_m"]
            ),
            upright_thickness_m=float(cable_rack_raw["upright_thickness_m"]),
            horn_count=int(cable_rack_raw["horn_count"]),
            horn_thickness_m=float(cable_rack_raw["horn_thickness_m"]),
            horn_radius_m=float(cable_rack_raw["horn_radius_m"]),
            horn_overall_length_m=float(
                cable_rack_raw["horn_overall_length_m"]
            ),
            horn_overall_height_m=float(
                cable_rack_raw["horn_overall_height_m"]
            ),
            cable_places_per_horn=int(
                cable_rack_raw["cable_places_per_horn"]
            ),
            occupied_places_per_horn=int(
                cable_preview_raw["occupied_places_per_horn"]
            ),
            max_cable_diameter_m=float(cable_rack_raw["max_cable_diameter_m"]),
            horn_pitch_m=float(cable_rack_raw["horn_pitch_m"]["value"]),
            repeat_pitch_m=float(cable_rack_place_raw["repeat_pitch_m"]),
            phase_m=float(cable_rack_place_raw["phase_m"]),
            center_profile_z_m=float(
                cable_rack_place_raw["center_profile_z_m"]
            ),
            negative_side_center_profile_z_m=float(
                cable_rack_place_raw.get(
                    "negative_side_center_profile_z_m",
                    cable_rack_place_raw["center_profile_z_m"],
                )
            ),
            shell_clearance_inward_m=float(
                cable_rack_place_raw["shell_clearance_inward_m"]
            ),
            horn_longitudinal_width_m=float(
                cable_horn_mesh_raw["longitudinal_width_m"]
            ),
            first_cable_center_inward_m=float(
                cable_horn_mesh_raw["first_cable_center_inward_m"]
            ),
            second_cable_center_inward_m=float(
                cable_horn_mesh_raw["second_cable_center_inward_m"]
            ),
            representative_cable_diameter_m=float(
                cable_preview_raw["representative_diameter_m"]
            ),
            cable_circle_vertices=int(cable_preview_raw["circle_vertices"]),
            occupied_level_indices=tuple(
                int(v) for v in cable_preview_raw.get(
                    "occupied_level_indices",
                    range(int(cable_rack_raw["horn_count"])),
                )
            ),
            cable_sag_midspan_m=float(
                cable_preview_raw.get("midspan_sag_m", 0.0)
            ),
            cable_sag_variation_fraction=float(
                cable_preview_raw.get(
                    "midspan_sag_variation_fraction",
                    0.0,
                )
            ),
            cable_sag_peak_phase_jitter_fraction=float(
                cable_preview_raw.get(
                    "peak_phase_jitter_fraction",
                    0.0,
                )
            ),
        )


        water_side = str(water_main_raw["side"])
        if water_side == "positive_profile_x_weak_current_side_opposite_contact_rail":
            water_side_sign = 1
        elif water_side == "negative_profile_x_weak_current_side_opposite_contact_rail":
            water_side_sign = -1
        else:
            raise ValueError(
                f"unsupported modern water-main side {water_side!r}"
            )

        water_main_profile = MoscowWaterMainProfile(
            min_nominal_dn_mm=int(water_main_raw["min_nominal_dn_mm"]),
            quantity_single_track_tunnel=int(
                water_main_raw["quantity_single_track_tunnel"]
            ),
            side_profile_x_sign=water_side_sign,
            preview_outer_diameter_m=float(
                water_main_raw["preview_outer_diameter_m"]
            ),
            center_profile_z_m=float(water_main_raw["center_profile_z_m"]),
            shell_clearance_inward_m=float(
                water_main_raw["shell_clearance_inward_m"]
            ),
            support_max_pitch_m=float(
                water_main_raw["support_max_pitch_m"]
            ),
            support_geometry_mode=str(
                water_main_raw["support_geometry_mode"]
            ),
            placement_mode=str(water_main_raw["placement_mode"]),
            outer_diameter_mode=str(
                water_main_raw["preview_outer_diameter_mode"]
            ),
            material_family=str(water_main_raw["material_family"]),
            normative_source=str(water_main_raw["normative_source"]),
            confidence=str(water_main_raw["confidence"]),
        )


        if not math.isclose(
            track_profile.rail_height_m,
            0.180,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "initial Moscow R65 profile must preserve 0.180 m nominal height"
            )
        if not math.isclose(
            datums.lining_axis_z_m - datums.ugr_z_m,
            1.670,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "initial Moscow lining axis must be +1.670 m above UGR"
            )
        supported_civil_radii = {
            "CAST_IRON_5500_R1000": (2.550, 2.750),
            "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000": (2.800, 3.050),
        }
        civil_family = str(civil["family"])
        if civil_family not in supported_civil_radii:
            raise ValueError(
                f"unsupported Stage-10 civil family {civil_family!r}"
            )
        expected_intrados, expected_extrados = supported_civil_radii[civil_family]
        if not math.isclose(
            float(intrados["radius_m"]),
            expected_intrados,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"{civil_family} intrados radius must be {expected_intrados:.3f} m"
            )
        if not math.isclose(
            float(extrados["radius_m"]),
            expected_extrados,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"{civil_family} extrados radius must be {expected_extrados:.3f} m"
            )

        support_gap = (
            datums.ugr_z_m
            - track_profile.rail_height_m
            - sleeper_profile.top_z_m
        )
        support_stack = (
            kd65_profile.under_pad_thickness_m
            + kd65_profile.baseplate_rail_seat_height_m
            + kd65_profile.rail_pad_total_thickness_m
        )
        if not math.isclose(support_gap, support_stack, abs_tol=1e-12):
            raise ValueError(
                "Stage-10.2 support stack must close exactly between sleeper top "
                "and R65 base datum"
            )
        if not math.isclose(sleeper_profile.pitch_m, 1000.0 / 1680.0, abs_tol=1e-12):
            raise ValueError("initial straight sleeper density must remain 1680/km")

        if not math.isclose(
            concrete_profile.surface_reference_abs_x_m,
            0.5 * sleeper_profile.length_m,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "Stage-10.2 concrete crossfall reference must remain at the "
                "outer end of the deterministic timber sleeper"
            )
        if not math.isclose(
            sleeper_profile.top_z_m - concrete_profile.surface_reference_z_m,
            0.010,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "Stage-10.2 sleeper-end exposure must remain 0.010 m"
            )
        if not math.isclose(
            contact_profile.horizontal_from_inner_working_face_m,
            0.690,
            abs_tol=1e-12,
        ):
            raise ValueError("initial contact-rail horizontal datum must be 0.690 m")
        if not math.isclose(
            contact_profile.working_surface_z_m,
            0.160,
            abs_tol=1e-12,
        ):
            raise ValueError("initial contact-rail working surface must be +0.160 m")
        if not math.isclose(
            walkway_profile.top_z_m,
            0.200,
            abs_tol=1e-12,
        ):
            raise ValueError("initial Moscow walkway top must be +0.200 m")
        if not math.isclose(
            walkway_profile.inner_edge_x_m,
            1.660,
            abs_tol=1e-12,
        ):
            raise ValueError("initial Moscow walkway inner edge must be +1.660 m")
        if not math.isclose(
            walkway_profile.outer_edge_x_m,
            math.sqrt(
                float(intrados["radius_m"]) ** 2
                - (
                    walkway_profile.top_z_m
                    - float(landmarks["lining_axis_z_m"])
                ) ** 2
            ),
            abs_tol=1e-9,
        ):
            raise ValueError("walkway outer edge must close on physical intrados")
        if not contact_profile.cover_era_mismatch:
            raise ValueError(
                "initial legacy contact-rail cover fallback must retain era mismatch"
            )

        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            schema_version=str(raw["schema_version"]),
            profile_id=str(raw["profile_id"]),
            purpose=str(raw["purpose"]),
            coordinate=coordinate,
            datums=datums,
            track=track_profile,
            sleeper=sleeper_profile,
            fastening=kd65_profile,
            track_concrete=concrete_profile,
            contact_rail=contact_profile,
            modern_contact_rail=modern_contact_profile,
            modern_permanent_way=modern_pw_profile,
            cable_rack=cable_rack_profile,
            water_main=water_main_profile,
            default_service_preset=str(service_presets_raw["default"]),
            walkway=walkway_profile,
            civil_geometry_mode=str(civil_geom_raw["mode"]),
            civil_segment_surface_mode=str(
                civil_geom_raw["circumferential_segment_surface_mode"]
            ),
            civil_family=str(civil["family"]),
            intrados_radius_m=float(intrados["radius_m"]),
            extrados_radius_m=float(extrados["radius_m"]),
            ring_pitch_m=float(civil["ring_pitch_m"]),
            provenance=MoscowProfileProvenance(
                source_path=None if source_path is None else str(source_path),
                source_pinpoints_file=str(raw["source_pinpoints_file"]),
                source_ids=tuple(source_ids),
                canonical_sha256=digest,
            ),
            _canonical_json=canonical,
        )

    def to_mapping(self) -> dict[str, Any]:
        return json.loads(self._canonical_json)

    def canonical_json(self) -> str:
        return self._canonical_json


def repository_stage10_initial_profile_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "research"
        / "moscow_metro_tunnels"
        / "data"
        / "stage10_initial_profile.json"
    )


STAGE10_CIVIL_ARCHETYPES = (
    "cast_iron_5500_5100",
    "rc_block_6100_5600",
)


def _apply_stage10_civil_archetype(
    mapping: Mapping[str, Any],
    civil_archetype: str,
) -> dict[str, Any]:
    raw = deepcopy(dict(mapping))
    if civil_archetype not in STAGE10_CIVIL_ARCHETYPES:
        raise ValueError(
            f"unsupported Stage-10 civil archetype {civil_archetype!r}; "
            f"expected one of {STAGE10_CIVIL_ARCHETYPES!r}"
        )
    if civil_archetype == "cast_iron_5500_5100":
        return raw

    civil = raw["civil_lining"]
    axis_z = float(civil["vertical_landmarks"]["lining_axis_z_m"])
    intrados_radius = 2.800
    extrados_radius = 3.050

    raw["profile_id"] = (
        "stage10_profile_RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
    )
    civil["family"] = "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
    civil["shape"] = (
        "circular 6.1/5.6 m Moscow RC lining with ten identical curved blocks"
    )
    civil["intrados"].update(
        {
            "radius_m": intrados_radius,
            "diameter_m": 2.0 * intrados_radius,
            "source": "S026",
        }
    )
    civil["extrados"].update(
        {
            "radius_m": extrados_radius,
            "diameter_m": 2.0 * extrados_radius,
            "basis": (
                "S026 documented Moscow 6.1/5.6 m ten-block RC lining; "
                "principal radii and equal ten-block topology are rendered directly, "
                "while detailed radial-end hole/pin CAD remains unresolved"
            ),
            "confidence": "C",
        }
    )
    landmarks = civil["vertical_landmarks"]
    landmarks.update(
        {
            "intrados_crown_z_m": axis_z + intrados_radius,
            "intrados_invert_z_m": axis_z - intrados_radius,
            "extrados_crown_z_m": axis_z + extrados_radius,
            "extrados_invert_z_m": axis_z - extrados_radius,
            "lining_axis_to_intrados_invert_m": intrados_radius,
            "ugr_to_intrados_invert_m": intrados_radius - axis_z,
        }
    )
    civil["ring_pitch_m"] = 1.0
    civil["coarse_ring_topology"] = {
        "total_segments": 10,
        "identical_blocks": 10,
        "source": "S026",
        "confidence": "C",
        "warning": (
            "S026 fixes the ten identical blocks and principal dimensions. "
            "Stage-10 renders the equal curved block sectors directly; exact "
            "radial-end holes, pin seating and edge chamfers remain unresolved."
        ),
    }
    civil["initial_geometry"].update(
        {
            "mode": "segmented_rc_6100_5600_10block_stage9_like_v1",
            "ring_pitch_m": 1.0,
            "circumferential_segment_surface_mode": (
                "source_backed_equal_10block_curved_segments_v1"
            ),
            "coarse_segment_count_reference": 10,
            "coarse_segment_count_is_geometry": True,
            "confidence": "C_source_family_dimensions_and_topology",
            "reason": (
                "Render the researched ten identical Moscow RC blocks as separate "
                "curved annular sectors, using Stage-9-like segment construction "
                "without inventing exact radial-end holes, pin seats or chamfers."
            ),
        }
    )

    walkway = raw["walkway"]
    outer_x = math.sqrt(
        intrados_radius * intrados_radius
        - (float(walkway["top_z_m"]) - axis_z) ** 2
    )
    walkway["outer_edge"].update(
        {
            "x_m": round(outer_x, 9),
            "basis": (
                "intersection with selected civil intrados at walkway top; "
                "track/UGR-to-lining-axis datum transferred from the Stage-10 "
                "reference profile because S026 does not publish a separate UGR datum"
            ),
            "confidence": "C_transfer_rule",
        }
    )
    walkway["top_clear_width_m"].update(
        {
            "value": round(
                outer_x - float(walkway["inner_edge_x_m"]),
                9,
            ),
            "derivation": (
                "selected physical intrados intersection minus retained "
                "Stage-10 walkway inner-edge datum"
            ),
            "confidence": "C_transfer_rule",
        }
    )
    return raw


def load_stage10_initial_moscow_profile(
    path: str | Path | None = None,
    *,
    civil_archetype: str = "cast_iron_5500_5100",
) -> MoscowStage10Profile:
    source = (
        Path(path)
        if path is not None
        else repository_stage10_initial_profile_path()
    )
    with source.open("r", encoding="utf-8") as fh:
        mapping = json.load(fh)
    resolved = _apply_stage10_civil_archetype(mapping, civil_archetype)
    return MoscowStage10Profile.from_mapping(resolved, source_path=source)


@dataclass(frozen=True)
class _Vec2:
    x: float
    z: float

    def __add__(self, other: "_Vec2") -> "_Vec2":
        return _Vec2(self.x + other.x, self.z + other.z)

    def __sub__(self, other: "_Vec2") -> "_Vec2":
        return _Vec2(self.x - other.x, self.z - other.z)

    def __mul__(self, k: float) -> "_Vec2":
        return _Vec2(self.x * k, self.z * k)

    __rmul__ = __mul__

    def dot(self, other: "_Vec2") -> float:
        return self.x * other.x + self.z * other.z

    def norm(self) -> float:
        return math.hypot(self.x, self.z)

    def normalized(self) -> "_Vec2":
        n = self.norm()
        if n == 0.0:
            raise ValueError("zero-length vector")
        return _Vec2(self.x / n, self.z / n)


@dataclass(frozen=True)
class _Line2:
    n: _Vec2
    c: float

    @classmethod
    def through(cls, p: _Vec2, direction: _Vec2) -> "_Line2":
        d = direction.normalized()
        n = _Vec2(-d.z, d.x)
        return cls(n=n, c=-(n.dot(p)))

    def signed_distance(self, p: _Vec2) -> float:
        return self.n.dot(p) + self.c

    def project(self, p: _Vec2) -> _Vec2:
        return p - self.n * self.signed_distance(p)


@dataclass(frozen=True)
class R65Primitive:
    kind: str
    start: _Vec2
    end: _Vec2
    center: _Vec2 | None = None
    radius: float | None = None
    label: str = ""


def _intersect_offset_lines(
    a: _Line2,
    da: float,
    b: _Line2,
    db: float,
) -> _Vec2:
    det = a.n.x * b.n.z - a.n.z * b.n.x
    if abs(det) < 1e-12:
        raise ValueError("parallel lines")
    rhs1 = da - a.c
    rhs2 = db - b.c
    return _Vec2(
        (rhs1 * b.n.z - a.n.z * rhs2) / det,
        (a.n.x * rhs2 - rhs1 * b.n.x) / det,
    )


def _line_circle_intersections(
    line: _Line2,
    signed_offset: float,
    center: _Vec2,
    radius: float,
) -> list[_Vec2]:
    d = signed_offset - line.c
    p0 = line.n * d
    tangent = _Vec2(-line.n.z, line.n.x)
    rel = p0 - center
    b = 2.0 * rel.dot(tangent)
    c = rel.dot(rel) - radius * radius
    disc = b * b - 4.0 * c
    if disc < -1e-10:
        return []
    root = math.sqrt(max(0.0, disc))
    return [
        p0 + tangent * ((-b + root) / 2.0),
        p0 + tangent * ((-b - root) / 2.0),
    ]


def _circle_tangent_point(
    big_center: _Vec2,
    big_radius: float,
    small_center: _Vec2,
) -> _Vec2:
    n = (small_center - big_center).normalized()
    return big_center + n * big_radius


def _sample_arc(
    center: _Vec2,
    radius: float,
    start: _Vec2,
    end: _Vec2,
    chord_error_m: float,
) -> list[_Vec2]:
    a0 = math.atan2(start.z - center.z, start.x - center.x)
    a1 = math.atan2(end.z - center.z, end.x - center.x)
    da = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    if radius <= 0.0 or chord_error_m <= 0.0:
        raise ValueError("arc radius and chord error must be positive")
    if chord_error_m >= radius:
        n = 1
    else:
        theta_max = 2.0 * math.acos(
            max(-1.0, min(1.0, 1.0 - chord_error_m / radius))
        )
        n = max(1, int(math.ceil(abs(da) / theta_max)))
    return [
        _Vec2(
            center.x + radius * math.cos(a0 + da * i / n),
            center.z + radius * math.sin(a0 + da * i / n),
        )
        for i in range(n + 1)
    ]


def _stitch(
    parts: Sequence[Sequence[_Vec2]],
    tol: float = 1e-9,
) -> list[_Vec2]:
    out: list[_Vec2] = []
    for part in parts:
        for p in part:
            if out and (p - out[-1]).norm() <= tol:
                continue
            out.append(p)
    return out


def _polygon_area_centroid(
    poly: Sequence[_Vec2],
) -> tuple[float, _Vec2]:
    cross_sum = cx_sum = cz_sum = 0.0
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        cr = p.x * q.z - q.x * p.z
        cross_sum += cr
        cx_sum += (p.x + q.x) * cr
        cz_sum += (p.z + q.z) * cr
    area = 0.5 * cross_sum
    if abs(area) < 1e-15:
        raise ValueError("degenerate rail polygon")
    return area, _Vec2(
        cx_sum / (6.0 * area),
        cz_sum / (6.0 * area),
    )


@dataclass(frozen=True)
class R65ProductionProfile:
    """Production port of the research R65 tangent-chain reconstruction."""

    overall_height_m: float = 0.180
    nominal_head_width_m: float = 0.07459
    base_width_m: float = 0.150
    web_thickness_m: float = 0.018
    target_area_m2: float = 0.008265
    target_centroid_z_m: float = 0.08130
    chord_error_m: float = 0.00005

    def __post_init__(self) -> None:
        if (
            self.chord_error_m <= 0.0
            or not math.isfinite(self.chord_error_m)
        ):
            raise ValueError("R65 chord error must be finite and positive")

    def right_half_primitives(self) -> tuple[R65Primitive, ...]:
        h = self.overall_height_m
        a = 0.0200328
        b = 0.0490859

        c500 = _Vec2(0.0, h - 0.500)
        top = _Vec2(0.0, h)
        xa = a / 2.0
        p1 = _Vec2(
            xa,
            c500.z + math.sqrt(0.500**2 - xa**2),
        )
        c80 = p1 + (c500 - p1) * (0.080 / 0.500)
        xb = b / 2.0
        p2 = _Vec2(
            xb,
            c80.z + math.sqrt(
                0.080**2 - (xb - c80.x) ** 2
            ),
        )
        c15 = p2 + (c80 - p2) * (0.015 / 0.080)
        p3 = _Vec2(0.07300 / 2.0, h - 0.01567)

        side = _Line2.through(p3, _Vec2(1.0, -20.0))
        underside = _Line2.through(
            _Vec2(0.0, h - 0.045),
            _Vec2(-4.0, -1.0),
        )
        c5 = _intersect_offset_lines(
            side,
            -0.005,
            underside,
            -0.005,
        )
        p4 = side.project(c5)
        p5 = underside.project(c5)

        zc = h - 0.0975
        xw = self.web_thickness_m / 2.0
        c_up = _Vec2(xw + 0.370, zc)
        c12_candidates = _line_circle_intersections(
            underside,
            +0.012,
            c_up,
            0.370 - 0.012,
        )
        c12 = min(
            (p for p in c12_candidates if 0.0 < p.x < 0.060),
            key=lambda p: abs(
                p.z - (h - 0.045 - 0.006)
            ),
        )
        p6 = underside.project(c12)
        p7 = _circle_tangent_point(c_up, 0.370, c12)
        pmid = _Vec2(xw, zc)

        c_low = _Vec2(xw + 0.400, zc)
        base = _Line2.through(
            _Vec2(0.0, 0.030),
            _Vec2(4.0, -1.0),
        )
        cf_candidates = _line_circle_intersections(
            base,
            +0.025,
            c_low,
            0.400 - 0.025,
        )
        cf = min(
            (p for p in cf_candidates if 0.0 < p.x < 0.080),
            key=lambda p: abs(p.z - (0.030 + 0.017)),
        )
        p8 = _circle_tangent_point(c_low, 0.400, cf)
        p9 = base.project(cf)

        halfbase = self.base_width_m / 2.0
        side_base = _Line2.through(
            _Vec2(halfbase, 0.0),
            _Vec2(0.0, -1.0),
        )
        c4 = _intersect_offset_lines(
            base,
            +0.004,
            side_base,
            -0.004,
        )
        p10 = base.project(c4)
        p11 = side_base.project(c4)

        c2 = _Vec2(halfbase - 0.002, 0.002)
        p12 = _Vec2(halfbase, 0.002)
        p13 = _Vec2(halfbase - 0.002, 0.0)
        bottom = _Vec2(0.0, 0.0)

        return (
            R65Primitive(
                "arc",
                top,
                p1,
                c500,
                0.500,
                "head_R500",
            ),
            R65Primitive(
                "arc",
                p1,
                p2,
                c80,
                0.080,
                "head_R80",
            ),
            R65Primitive(
                "arc",
                p2,
                p3,
                c15,
                0.015,
                "head_R15",
            ),
            R65Primitive(
                "line",
                p3,
                p4,
                label="head_side_1_20",
            ),
            R65Primitive(
                "arc",
                p4,
                p5,
                c5,
                0.005,
                "head_lower_outer",
            ),
            R65Primitive(
                "line",
                p5,
                p6,
                label="head_underside_1_4",
            ),
            R65Primitive(
                "arc",
                p6,
                p7,
                c12,
                0.012,
                "head_web_fillet",
            ),
            R65Primitive(
                "arc",
                p7,
                pmid,
                c_up,
                0.370,
                "upper_web",
            ),
            R65Primitive(
                "arc",
                pmid,
                p8,
                c_low,
                0.400,
                "lower_web",
            ),
            R65Primitive(
                "arc",
                p8,
                p9,
                cf,
                0.025,
                "web_foot_fillet",
            ),
            R65Primitive(
                "line",
                p9,
                p10,
                label="foot_top_1_4",
            ),
            R65Primitive(
                "arc",
                p10,
                p11,
                c4,
                0.004,
                "foot_outer_R4",
            ),
            R65Primitive(
                "line",
                p11,
                p12,
                label="foot_outer_side",
            ),
            R65Primitive(
                "arc",
                p12,
                p13,
                c2,
                0.002,
                "foot_outer_R2",
            ),
            R65Primitive(
                "line",
                p13,
                bottom,
                label="foot_bottom",
            ),
        )

    def _sample_half(self) -> list[_Vec2]:
        parts: list[list[_Vec2]] = []
        for primitive in self.right_half_primitives():
            if primitive.kind == "line":
                parts.append(
                    [primitive.start, primitive.end]
                )
            else:
                assert primitive.center is not None
                assert primitive.radius is not None
                parts.append(
                    _sample_arc(
                        primitive.center,
                        primitive.radius,
                        primitive.start,
                        primitive.end,
                        self.chord_error_m,
                    )
                )
        return _stitch(parts)

    def closed_profile_base_coordinates(
        self,
    ) -> tuple[tuple[float, float], ...]:
        right = self._sample_half()
        left = [
            _Vec2(-p.x, p.z)
            for p in reversed(right)
        ]
        closed = right + left[1:-1]
        return tuple((p.x, p.z) for p in closed)

    def points_xz(
        self,
        *,
        center_x_m: float,
        top_z_m: float,
    ) -> tuple[tuple[float, float], ...]:
        dz = float(top_z_m) - self.overall_height_m
        return tuple(
            (float(center_x_m) + x, dz + z)
            for x, z in self.closed_profile_base_coordinates()
        )

    def working_face_offset_m(
        self,
        *,
        measurement_below_top_m: float = 0.013,
    ) -> float:
        """Solve R65 half-width at the gauge measurement plane."""
        if (
            measurement_below_top_m <= 0.0
            or measurement_below_top_m >= self.overall_height_m
        ):
            raise ValueError(
                "working-face measurement level must lie inside the rail height"
            )

        z = self.overall_height_m - measurement_below_top_m
        candidates: list[float] = []
        tol = 1e-10
        for primitive in self.right_half_primitives():
            zmin = min(
                primitive.start.z,
                primitive.end.z,
            ) - tol
            zmax = max(
                primitive.start.z,
                primitive.end.z,
            ) + tol
            if not (zmin <= z <= zmax):
                continue
            xmin = min(
                primitive.start.x,
                primitive.end.x,
            ) - 1e-8
            xmax = max(
                primitive.start.x,
                primitive.end.x,
            ) + 1e-8

            if primitive.kind == "line":
                dz = primitive.end.z - primitive.start.z
                if abs(dz) <= tol:
                    continue
                u = (z - primitive.start.z) / dz
                x = (
                    primitive.start.x
                    + u
                    * (
                        primitive.end.x
                        - primitive.start.x
                    )
                )
                if xmin <= x <= xmax:
                    candidates.append(x)
            else:
                assert primitive.center is not None
                assert primitive.radius is not None
                radicand = (
                    primitive.radius**2
                    - (z - primitive.center.z) ** 2
                )
                if radicand < -tol:
                    continue
                dx = math.sqrt(max(0.0, radicand))
                for x in (
                    primitive.center.x - dx,
                    primitive.center.x + dx,
                ):
                    if xmin <= x <= xmax:
                        candidates.append(x)

        if not candidates:
            raise ValueError(
                "gauge measurement plane does not intersect R65 working face"
            )
        return max(candidates)

    def validation_metrics(self) -> dict[str, float]:
        validation_profile = (
            self
            if self.chord_error_m <= 0.00001
            else R65ProductionProfile(
                chord_error_m=0.00001
            )
        )
        poly = [
            _Vec2(x, z)
            for x, z
            in validation_profile.closed_profile_base_coordinates()
        ]
        area_signed, centroid = _polygon_area_centroid(poly)
        area = abs(area_signed)
        max_x = max(abs(p.x) for p in poly)
        max_head_x = max(
            abs(p.x)
            for p in poly
            if p.z > self.overall_height_m - 0.045
        )
        return {
            "height_m": (
                max(p.z for p in poly)
                - min(p.z for p in poly)
            ),
            "base_width_m": 2.0 * max_x,
            "head_width_m": 2.0 * max_head_x,
            "web_thickness_m": self.web_thickness_m,
            "area_m2": area,
            "area_rel_error": (
                (area - self.target_area_m2)
                / self.target_area_m2
            ),
            "centroid_z_m": centroid.z,
            "centroid_z_error_m": (
                centroid.z
                - self.target_centroid_z_m
            ),
        }


def r65_rail_center_offsets_for_gauge(
    gauge_m: float,
    *,
    profile: R65ProductionProfile | None = None,
    measurement_below_top_m: float = 0.013,
) -> tuple[float, float]:
    """Return negative/positive rail symmetry-axis offsets for a target gauge."""
    if not math.isfinite(gauge_m) or gauge_m <= 0.0:
        raise ValueError("gauge must be finite and positive")
    rail = profile or R65ProductionProfile()
    working = rail.working_face_offset_m(
        measurement_below_top_m=measurement_below_top_m
    )
    center = 0.5 * gauge_m + working
    return -center, +center


def r65_inner_working_face_x(
    rail_index: int,
    center_x_m: float,
    *,
    profile: R65ProductionProfile | None = None,
    measurement_below_top_m: float = 0.013,
) -> float:
    rail = profile or R65ProductionProfile()
    working = rail.working_face_offset_m(
        measurement_below_top_m=measurement_below_top_m
    )
    if rail_index == 0:
        return float(center_x_m) + working
    if rail_index == 1:
        return float(center_x_m) - working
    raise ValueError(
        "rail_index must be 0 (negative-X rail) or 1 (positive-X rail)"
    )
