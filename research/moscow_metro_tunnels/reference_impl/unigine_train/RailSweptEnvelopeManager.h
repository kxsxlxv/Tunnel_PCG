#pragma once

#include <UnigineComponentSystem.h>
#include <UnigineMathLibBounds.h>
#include <UnigineNodes.h>
#include <UnigineObjects.h>
#include <UnigineSplineGraph.h>

#include <string>
#include <vector>

class Train81775Kinematics;

// Conservative route-hypothesis obstacle screening for the 81-775 reference.
//
// This is an SDK-facing reference implementation. It intentionally keeps
// unresolved turnout branches alive and unions their future OBB chains.
// The current vehicle volume is the same above-TOR rectangular screening proxy
// used by src/tunnel_scanner_core/rail_obstacle.py, not a certified kinematic
// gauge.
class RailSweptEnvelopeManager : public Unigine::ComponentBase
{
public:
	COMPONENT_DEFINE(RailSweptEnvelopeManager, Unigine::ComponentBase);
	COMPONENT_DESCRIPTION(
		"81-775 multi-route swept obstacle screening envelope");

	COMPONENT_INIT(init);
	COMPONENT_UPDATE(update);
	COMPONENT_SHUTDOWN(shutdown);

	enum class Relevance
	{
		OUTSIDE = 0,
		ACTIVE_ROUTE = 1,
		ALL_FEASIBLE_ROUTES = 2,
		ROUTE_AMBIGUOUS = 3,
	};

	struct RouteHypothesisParam : public Unigine::ComponentStruct
	{
		PROP_PARAM(String, route_id, "");
		PROP_PARAM(File, spline_file);
		PROP_PARAM(Double, global_chainage_origin_m, 0.0);
		PROP_PARAM(Toggle, enabled, true);

		// Path-fit uncertainty. Negative values mean unknown. For simulator
		// ground truth set exact_ground_truth=true instead of relying on
		// default zeros.
		PROP_PARAM(Toggle, path_uncertainty_exact_ground_truth, false);
		PROP_PARAM(Float, path_lateral_offset_bound_m, -1.0f);
		PROP_PARAM(Float, path_heading_bound_rad, -1.0f);
		PROP_PARAM(Float, path_curvature_bound_per_m, -1.0f);
		PROP_PARAM(Float, path_vertical_offset_bound_m, -1.0f);
		PROP_PARAM(Float, path_grade_bound_rad, -1.0f);
		PROP_PARAM(Float, path_cant_roll_bound_rad, -1.0f);
	};

	PROP_PARAM(Node, train_kinematics_node);
	PROP_ARRAY_STRUCT(RouteHypothesisParam, route_hypotheses);
	PROP_PARAM(String, active_route_id, "");

	PROP_PARAM(Float, lookahead_m, 80.0f);
	PROP_PARAM(Float, max_chainage_step_m, 1.0f);
	PROP_PARAM(Float, max_pose_deviation_m, 0.005f);
	PROP_PARAM(Int, maximum_refinement_depth, 12);
	PROP_PARAM(Int, arc_length_samples_per_segment, 128);

	PROP_PARAM(Float, vehicle_base_m, 12.6f);
	PROP_PARAM(Float, vehicle_length_proxy_m, 20.08f);
	PROP_PARAM(Float, vehicle_width_m, 2.74f);
	PROP_PARAM(Float, vehicle_height_above_tor_m, 3.68f);

	// Vehicle/track gauging allowance ledger. Negative values mean unknown.
	// The 0.016 m stop gap is source-backed but is not a complete GOST w.
	PROP_PARAM(Float, documented_body_bogie_lateral_free_m, 0.016f);
	PROP_PARAM(Float, gost_q_bogie_frame_relative_wheelset_m, -1.0f);
	PROP_PARAM(Float, gost_w_carbody_relative_bogie_m, -1.0f);
	PROP_PARAM(Float, additional_vehicle_lateral_dynamic_m, -1.0f);
	PROP_PARAM(Float, vehicle_vertical_dynamic_m, -1.0f);
	PROP_PARAM(Float, vehicle_roll_bound_rad, -1.0f);
	PROP_PARAM(Float, track_lateral_tolerance_m, -1.0f);
	PROP_PARAM(Float, track_vertical_tolerance_m, -1.0f);

	// 0 disables mask filtering. Otherwise an object is considered only when
	// at least one surface has a matching intersection mask.
	PROP_PARAM(Mask, obstacle_intersection_mask, "intersection", 0);
	PROP_ARRAY(Node, ignored_nodes);

	PROP_PARAM(Toggle, debug_visualization, true);
	PROP_PARAM(Toggle, log_detection_changes, false);

	struct Detection
	{
		Unigine::ObjectPtr object;
		Relevance relevance = Relevance::OUTSIDE;
		std::vector<std::string> intersecting_route_ids;
	};

	Relevance classifyPoint(const Unigine::Math::Vec3 &point) const;
	const std::vector<Detection> &getDetections() const { return detections; }
	int getDetectionCount() const { return int(detections.size()); }
	bool isSafetyComplete() const;

private:
	struct SegmentArcLut
	{
		double route_start_m = 0.0;
		double length_m = 0.0;
		std::vector<double> cumulative_m;
	};

	struct TrackSample
	{
		Unigine::Math::Vec3 position;
		Unigine::Math::vec3 tangent;
		Unigine::Math::vec3 up;
	};

	struct VehiclePose
	{
		double leading_chainage_m = 0.0;
		double trailing_chainage_m = 0.0;
		Unigine::Math::Vec3 body_position;
		Unigine::Math::vec3 body_forward;
		Unigine::Math::vec3 body_right;
		Unigine::Math::vec3 body_up;
	};

	struct OBB
	{
		Unigine::Math::Vec3 center;
		Unigine::Math::vec3 right;
		Unigine::Math::vec3 forward;
		Unigine::Math::vec3 up;
		Unigine::Math::vec3 half_extents;
	};

	struct RouteRuntime
	{
		std::string route_id;
		double global_chainage_origin_m = 0.0;
		Unigine::SplineGraphPtr spline;
		std::vector<SegmentArcLut> arc_luts;
		double length_m = 0.0;
		double current_start_chainage_m = 0.0;
		std::vector<OBB> boxes;
		bool enabled = true;

		double path_lateral_offset_bound_m = -1.0;
		double path_heading_bound_rad = -1.0;
		double path_curvature_bound_per_m = -1.0;
		double path_vertical_offset_bound_m = -1.0;
		double path_grade_bound_rad = -1.0;
		double path_cant_roll_bound_rad = -1.0;
		bool path_uncertainty_complete = false;
	};

	void init();
	void update();
	void shutdown();

	bool loadRoute(RouteRuntime &route, const char *path);
	void rebuildRouteArcLength(RouteRuntime &route);
	TrackSample sampleRoute(const RouteRuntime &route, double local_chainage_m) const;
	double solveTrailingChainage(
		const RouteRuntime &route,
		double leading_chainage_m) const;
	VehiclePose vehiclePose(
		const RouteRuntime &route,
		double leading_chainage_m) const;
	OBB carbodyBox(
		const VehiclePose &pose,
		const RouteRuntime &route,
		double lookahead_m) const;
	double poseDeviation(
		const VehiclePose &left,
		const VehiclePose &middle,
		const VehiclePose &right) const;

	double knownBodyBogieLateralM() const;
	double knownLateralAllowanceM() const;
	double knownVerticalAllowanceM() const;
	double knownRollBoundRad() const;
	bool vehicleTrackAllowanceComplete() const;
	static double maximumRotatedExtent(
		double primary_half_extent_m,
		double coupled_half_extent_m,
		double angle_bound_rad);

	void rebuildEnvelopes();
	void appendAdaptiveInterval(
		RouteRuntime &route,
		const VehiclePose &left,
		const VehiclePose &right,
		int depth);
	Unigine::Math::WorldBoundBox routeBroadPhase(
		const RouteRuntime &route) const;
	Unigine::Math::WorldBoundBox allRoutesBroadPhase() const;

	bool pointInBox(const Unigine::Math::Vec3 &point, const OBB &box) const;
	bool boxIntersectsAABB(
		const OBB &box,
		const Unigine::Math::WorldBoundBox &aabb) const;
	bool routeIntersectsAABB(
		const RouteRuntime &route,
		const Unigine::Math::WorldBoundBox &aabb) const;
	bool objectMatchesMask(const Unigine::ObjectPtr &object) const;
	bool isIgnored(const Unigine::ObjectPtr &object) const;

	Relevance classifyHits(
		int hit_count,
		bool active_hit,
		int feasible_count,
		bool active_present) const;
	void queryWorldObjects();
	void renderDebug() const;

	Train81775Kinematics *train = nullptr;
	std::vector<RouteRuntime> routes;
	std::vector<Detection> detections;
	bool ready = false;
	bool visualizer_was_enabled = false;
	int previous_detection_count = -1;
};
