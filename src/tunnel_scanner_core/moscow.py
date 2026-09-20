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
    concrete_top_at_rail_z_m: float
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
            self.central_drain_clear_width_m,
            self.water_groove_width_m,
            self.water_groove_depth_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("track-concrete dimensions/slope must be positive")
        if self.water_groove_width_m >= self.central_drain_clear_width_m:
            raise ValueError("water-release groove must fit inside central drain")
        if self.minimum_bottom_at_rail_z_m >= self.concrete_top_at_rail_z_m:
            raise ValueError("concrete minimum bottom must lie below top datum")
        if self.central_drain_bottom_z_m >= self.concrete_top_at_rail_z_m:
            raise ValueError("central drain bottom must lie below concrete top")


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
            concrete_top_at_rail_z_m=float(
                concrete_raw["nominal_concrete_top_at_sleeper_datum_z_m"][
                    "value"
                ]
            ),
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
        if not math.isclose(
            float(intrados["radius_m"]),
            2.550,
            abs_tol=1e-12,
        ):
            raise ValueError("initial Moscow intrados radius must be 2.550 m")
        if not math.isclose(
            float(extrados["radius_m"]),
            2.750,
            abs_tol=1e-12,
        ):
            raise ValueError("initial Moscow extrados radius must be 2.750 m")

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


def load_stage10_initial_moscow_profile(
    path: str | Path | None = None,
) -> MoscowStage10Profile:
    source = (
        Path(path)
        if path is not None
        else repository_stage10_initial_profile_path()
    )
    with source.open("r", encoding="utf-8") as fh:
        mapping = json.load(fh)
    return MoscowStage10Profile.from_mapping(mapping, source_path=source)


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
