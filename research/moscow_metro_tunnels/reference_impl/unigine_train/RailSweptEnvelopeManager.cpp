#include "RailSweptEnvelopeManager.h"
#include "Train81775Kinematics.h"

#include <UnigineLog.h>
#include <UnigineMathLib.h>
#include <UnigineVisualizer.h>
#include <UnigineWorld.h>

#include <algorithm>
#include <array>
#include <cfloat>
#include <cmath>
#include <iterator>
#include <limits>
#include <numeric>

using namespace Unigine;
using namespace Unigine::Math;

REGISTER_COMPONENT(RailSweptEnvelopeManager);

namespace
{
	constexpr double EPS = 1e-9;
	constexpr double HALF_PI = 1.57079632679489661923;
	constexpr int CHORD_SOLVER_ITERATIONS = 48;

	double dot_axis(const Vec3 &value, const vec3 &axis)
	{
		return value.x * double(axis.x)
			+ value.y * double(axis.y)
			+ value.z * double(axis.z);
	}

	double distance3(const Vec3 &a, const Vec3 &b)
	{
		return length(a - b);
	}

	vec3 safe_up(const vec3 &forward, const vec3 &up_hint)
	{
		vec3 right = normalize(cross(forward, up_hint));
		return normalize(cross(right, forward));
	}

	double vector_angle(const vec3 &a, const vec3 &b)
	{
		double cosine = clamp(
			double(dot(normalize(a), normalize(b))),
			-1.0,
			1.0);
		return std::acos(cosine);
	}

	const vec4 ROUTE_COLORS[] = {
		vec4(0.15f, 0.85f, 0.25f, 1.0f),
		vec4(0.20f, 0.55f, 1.00f, 1.0f),
		vec4(1.00f, 0.65f, 0.10f, 1.0f),
		vec4(0.85f, 0.20f, 0.85f, 1.0f),
	};
}

void RailSweptEnvelopeManager::init()
{
	if (!train_kinematics_node.get())
	{
		Log::error(
			"RailSweptEnvelopeManager: train_kinematics_node is required\n");
		return;
	}
	train = ComponentSystem::get()->getComponent<Train81775Kinematics>(
		train_kinematics_node.get());
	if (!train)
	{
		Log::error(
			"RailSweptEnvelopeManager: Train81775Kinematics component not found\n");
		return;
	}
	if (route_hypotheses.size() <= 0)
	{
		Log::error(
			"RailSweptEnvelopeManager: at least one route hypothesis is required\n");
		return;
	}
	if (vehicle_base_m.get() <= 0.0f
		|| vehicle_length_proxy_m.get() <= vehicle_base_m.get()
		|| vehicle_width_m.get() <= 0.0f
		|| vehicle_height_above_tor_m.get() <= 0.0f)
	{
		Log::error(
			"RailSweptEnvelopeManager: invalid 81-775 proxy dimensions\n");
		return;
	}
	if (max_chainage_step_m.get() <= 0.0f
		|| max_pose_deviation_m.get() <= 0.0f
		|| maximum_refinement_depth.get() < 1)
	{
		Log::error(
			"RailSweptEnvelopeManager: invalid envelope sampling parameters\n");
		return;
	}
	if (documented_body_bogie_lateral_free_m.get() < 0.0f
		|| (vehicle_roll_bound_rad.get() >= float(HALF_PI)))
	{
		Log::error(
			"RailSweptEnvelopeManager: invalid vehicle allowance parameters\n");
		return;
	}

	routes.clear();
	for (int i = 0; i < route_hypotheses.size(); ++i)
	{
		auto &param = route_hypotheses[i];
		if (!param->enabled.get())
			continue;

		String route_id = param->route_id.get();
		String spline_path = param->spline_file.get();
		if (route_id.size() <= 0 || spline_path.size() <= 0)
		{
			Log::warning(
				"RailSweptEnvelopeManager: skipping incomplete route hypothesis %d\n",
				i);
			continue;
		}

		RouteRuntime runtime;
		runtime.route_id = route_id.get();
		runtime.global_chainage_origin_m =
			double(param->global_chainage_origin_m.get());
		runtime.enabled = true;

		if (param->path_uncertainty_exact_ground_truth.get())
		{
			runtime.path_lateral_offset_bound_m = 0.0;
			runtime.path_heading_bound_rad = 0.0;
			runtime.path_curvature_bound_per_m = 0.0;
			runtime.path_vertical_offset_bound_m = 0.0;
			runtime.path_grade_bound_rad = 0.0;
			runtime.path_cant_roll_bound_rad = 0.0;
			runtime.path_uncertainty_complete = true;
		}
		else
		{
			runtime.path_lateral_offset_bound_m =
				double(param->path_lateral_offset_bound_m.get());
			runtime.path_heading_bound_rad =
				double(param->path_heading_bound_rad.get());
			runtime.path_curvature_bound_per_m =
				double(param->path_curvature_bound_per_m.get());
			runtime.path_vertical_offset_bound_m =
				double(param->path_vertical_offset_bound_m.get());
			runtime.path_grade_bound_rad =
				double(param->path_grade_bound_rad.get());
			runtime.path_cant_roll_bound_rad =
				double(param->path_cant_roll_bound_rad.get());

			const double half_pi = HALF_PI;
			const bool invalid_angle =
				runtime.path_heading_bound_rad >= half_pi
				|| runtime.path_grade_bound_rad >= half_pi
				|| runtime.path_cant_roll_bound_rad >= half_pi;
			if (invalid_angle)
			{
				Log::warning(
					"RailSweptEnvelopeManager: skipping route %s with invalid path angle bound\n",
					route_id.get());
				continue;
			}
			runtime.path_uncertainty_complete =
				runtime.path_lateral_offset_bound_m >= 0.0
				&& runtime.path_heading_bound_rad >= 0.0
				&& runtime.path_curvature_bound_per_m >= 0.0
				&& runtime.path_vertical_offset_bound_m >= 0.0
				&& runtime.path_grade_bound_rad >= 0.0
				&& runtime.path_cant_roll_bound_rad >= 0.0;
		}

		if (!loadRoute(runtime, spline_path.get()))
		{
			Log::error(
				"RailSweptEnvelopeManager: failed to load route %s from %s\n",
				route_id.get(),
				spline_path.get());
			continue;
		}
		routes.emplace_back(std::move(runtime));
	}

	if (routes.empty())
	{
		Log::error(
			"RailSweptEnvelopeManager: no route hypotheses could be loaded\n");
		return;
	}

	visualizer_was_enabled = Visualizer::isEnabled();
	if (debug_visualization.get())
		Visualizer::setEnabled(true);

	ready = true;
	rebuildEnvelopes();
	queryWorldObjects();
}

bool RailSweptEnvelopeManager::loadRoute(
	RouteRuntime &route,
	const char *path)
{
	route.spline = SplineGraph::create();
	if (!route.spline->load(path))
	{
		route.spline.clear();
		return false;
	}
	if (route.spline->getNumSegments() <= 0)
	{
		route.spline.clear();
		return false;
	}
	rebuildRouteArcLength(route);
	return route.length_m > 0.0;
}

void RailSweptEnvelopeManager::rebuildRouteArcLength(RouteRuntime &route)
{
	route.arc_luts.clear();
	route.length_m = 0.0;
	const int samples = std::max(
		8,
		arc_length_samples_per_segment.get());

	for (int segment = 0;
		segment < route.spline->getNumSegments();
		++segment)
	{
		SegmentArcLut lut;
		lut.route_start_m = route.length_m;
		lut.cumulative_m.reserve(size_t(samples + 1));
		lut.cumulative_m.push_back(0.0);

		Vec3 previous = route.spline->calcSegmentPoint(segment, 0.0f);
		double cumulative = 0.0;
		for (int i = 1; i <= samples; ++i)
		{
			float t = float(i) / float(samples);
			Vec3 current = route.spline->calcSegmentPoint(segment, t);
			cumulative += distance3(previous, current);
			lut.cumulative_m.push_back(cumulative);
			previous = current;
		}
		lut.length_m = cumulative;
		route.length_m += cumulative;
		route.arc_luts.emplace_back(std::move(lut));
	}
}

RailSweptEnvelopeManager::TrackSample
RailSweptEnvelopeManager::sampleRoute(
	const RouteRuntime &route,
	double local_chainage_m) const
{
	double s = clamp(local_chainage_m, 0.0, route.length_m);
	int segment = int(route.arc_luts.size()) - 1;
	for (int i = 0; i < int(route.arc_luts.size()); ++i)
	{
		const auto &lut = route.arc_luts[size_t(i)];
		if (s <= lut.route_start_m + lut.length_m
			|| i + 1 == int(route.arc_luts.size()))
		{
			segment = i;
			break;
		}
	}

	const auto &lut = route.arc_luts[size_t(segment)];
	double local_m = clamp(
		s - lut.route_start_m,
		0.0,
		lut.length_m);
	auto it = std::lower_bound(
		lut.cumulative_m.begin(),
		lut.cumulative_m.end(),
		local_m);
	size_t upper_index = size_t(
		std::distance(lut.cumulative_m.begin(), it));
	if (upper_index == 0)
		upper_index = 1;
	if (upper_index >= lut.cumulative_m.size())
		upper_index = lut.cumulative_m.size() - 1;
	size_t lower_index = upper_index - 1;

	double l0 = lut.cumulative_m[lower_index];
	double l1 = lut.cumulative_m[upper_index];
	double alpha = (l1 > l0)
		? (local_m - l0) / (l1 - l0)
		: 0.0;
	double sample_count = double(lut.cumulative_m.size() - 1);
	double t0 = double(lower_index) / sample_count;
	double t1 = double(upper_index) / sample_count;
	float t = float(t0 + (t1 - t0) * alpha);

	Vec3 position = route.spline->calcSegmentPoint(segment, t);
	vec3 tangent = normalize(
		route.spline->calcSegmentTangent(segment, t));
	vec3 up_hint = normalize(
		route.spline->calcSegmentUpVector(segment, t));
	return {position, tangent, safe_up(tangent, up_hint)};
}

double RailSweptEnvelopeManager::solveTrailingChainage(
	const RouteRuntime &route,
	double leading_chainage_m) const
{
	TrackSample leading = sampleRoute(route, leading_chainage_m);
	const double base = double(vehicle_base_m.get());

	auto residual = [&](double candidate_s)
	{
		return distance3(
			leading.position,
			sampleRoute(route, candidate_s).position)
			- base;
	};

	double available = leading_chainage_m;
	if (available <= base)
		return 0.0;

	double delta = std::min(
		available,
		std::max(base * 1.02, 0.25));
	double hi = leading_chainage_m;
	double lo = leading_chainage_m - delta;
	double lo_residual = residual(lo);

	while (lo_residual < 0.0 && delta < available)
	{
		delta = std::min(
			available,
			std::max(delta * 1.5, delta + 0.25));
		lo = leading_chainage_m - delta;
		lo_residual = residual(lo);
	}
	if (lo_residual < 0.0)
		return lo;

	for (int i = 0; i < CHORD_SOLVER_ITERATIONS; ++i)
	{
		double mid = 0.5 * (lo + hi);
		double value = residual(mid);
		if (std::abs(value) <= 1e-7 || hi - lo <= 1e-7)
			return mid;
		if (value >= 0.0)
			lo = mid;
		else
			hi = mid;
	}
	return 0.5 * (lo + hi);
}

RailSweptEnvelopeManager::VehiclePose
RailSweptEnvelopeManager::vehiclePose(
	const RouteRuntime &route,
	double leading_chainage_m) const
{
	VehiclePose pose;
	pose.leading_chainage_m = leading_chainage_m;
	pose.trailing_chainage_m =
		solveTrailingChainage(route, leading_chainage_m);

	TrackSample leading = sampleRoute(route, pose.leading_chainage_m);
	TrackSample trailing = sampleRoute(route, pose.trailing_chainage_m);

	pose.body_position =
		(leading.position + trailing.position) * 0.5;
	pose.body_forward = normalize(
		vec3(leading.position - trailing.position));
	vec3 up_hint = leading.up + trailing.up;
	if (length2(up_hint) <= float(EPS))
		up_hint = leading.up;
	pose.body_right = normalize(
		cross(pose.body_forward, normalize(up_hint)));
	pose.body_up = normalize(
		cross(pose.body_right, pose.body_forward));
	return pose;
}

double RailSweptEnvelopeManager::knownBodyBogieLateralM() const
{
	double known = double(documented_body_bogie_lateral_free_m.get());
	double gost_w = double(gost_w_carbody_relative_bogie_m.get());
	if (gost_w >= 0.0)
		known = std::max(known, gost_w);
	return known;
}

double RailSweptEnvelopeManager::knownLateralAllowanceM() const
{
	double total = knownBodyBogieLateralM();
	const double values[] = {
		double(gost_q_bogie_frame_relative_wheelset_m.get()),
		double(additional_vehicle_lateral_dynamic_m.get()),
		double(track_lateral_tolerance_m.get()),
	};
	for (double value : values)
	{
		if (value >= 0.0)
			total += value;
	}
	return total;
}

double RailSweptEnvelopeManager::knownVerticalAllowanceM() const
{
	double total = 0.0;
	const double values[] = {
		double(vehicle_vertical_dynamic_m.get()),
		double(track_vertical_tolerance_m.get()),
	};
	for (double value : values)
	{
		if (value >= 0.0)
			total += value;
	}
	return total;
}

double RailSweptEnvelopeManager::knownRollBoundRad() const
{
	double value = double(vehicle_roll_bound_rad.get());
	return value >= 0.0 ? value : 0.0;
}

bool RailSweptEnvelopeManager::vehicleTrackAllowanceComplete() const
{
	return gost_q_bogie_frame_relative_wheelset_m.get() >= 0.0f
		&& gost_w_carbody_relative_bogie_m.get() >= 0.0f
		&& additional_vehicle_lateral_dynamic_m.get() >= 0.0f
		&& vehicle_vertical_dynamic_m.get() >= 0.0f
		&& vehicle_roll_bound_rad.get() >= 0.0f
		&& track_lateral_tolerance_m.get() >= 0.0f
		&& track_vertical_tolerance_m.get() >= 0.0f;
}

double RailSweptEnvelopeManager::maximumRotatedExtent(
	double primary_half_extent_m,
	double coupled_half_extent_m,
	double angle_bound_rad)
{
	double bound = clamp(angle_bound_rad, 0.0, HALF_PI);
	double optimum = std::atan2(
		coupled_half_extent_m,
		primary_half_extent_m);
	if (bound >= optimum)
		return std::hypot(
			primary_half_extent_m,
			coupled_half_extent_m);
	return primary_half_extent_m * std::cos(bound)
		+ coupled_half_extent_m * std::sin(bound);
}

RailSweptEnvelopeManager::OBB
RailSweptEnvelopeManager::carbodyBox(
	const VehiclePose &pose,
	const RouteRuntime &route,
	double lookahead_m) const
{
	const double height = double(vehicle_height_above_tor_m.get());
	const double inflation = double(max_pose_deviation_m.get());
	const double d = std::max(0.0, lookahead_m);

	auto known = [](double value)
	{
		return value >= 0.0 ? value : 0.0;
	};

	const double lateral_center_bound =
		known(route.path_lateral_offset_bound_m)
		+ d * std::tan(known(route.path_heading_bound_rad))
		+ 0.5 * d * d
			* known(route.path_curvature_bound_per_m);
	const double yaw_bound =
		known(route.path_heading_bound_rad)
		+ d * known(route.path_curvature_bound_per_m);
	const double vertical_center_bound =
		known(route.path_vertical_offset_bound_m)
		+ d * std::tan(known(route.path_grade_bound_rad));
	const double total_roll_bound =
		knownRollBoundRad()
		+ known(route.path_cant_roll_bound_rad);

	const double base_width =
		0.5 * double(vehicle_width_m.get())
		+ knownLateralAllowanceM();
	const double base_length =
		0.5 * double(vehicle_length_proxy_m.get());
	const double base_height =
		0.5 * height + knownVerticalAllowanceM();

	const double yaw_width = maximumRotatedExtent(
		base_width,
		base_length,
		yaw_bound);
	const double yaw_length = maximumRotatedExtent(
		base_length,
		base_width,
		yaw_bound);
	const double roll_width = maximumRotatedExtent(
		yaw_width,
		base_height,
		total_roll_bound);
	const double roll_height = maximumRotatedExtent(
		base_height,
		yaw_width,
		total_roll_bound);

	OBB box;
	box.right = pose.body_right;
	box.forward = pose.body_forward;
	box.up = pose.body_up;
	box.center = pose.body_position
		+ Vec3(pose.body_up) * (0.5 * height);
	box.half_extents = vec3(
		float(roll_width + lateral_center_bound + inflation),
		float(yaw_length + inflation),
		float(roll_height + vertical_center_bound + inflation));
	return box;
}

double RailSweptEnvelopeManager::poseDeviation(
	const VehiclePose &left,
	const VehiclePose &middle,
	const VehiclePose &right) const
{
	Vec3 expected_center =
		(left.body_position + right.body_position) * 0.5;
	double center_error =
		distance3(middle.body_position, expected_center);

	vec3 expected_forward = left.body_forward + right.body_forward;
	if (length2(expected_forward) <= float(EPS))
		expected_forward = left.body_forward;
	expected_forward = normalize(expected_forward);

	double angle = vector_angle(
		middle.body_forward,
		expected_forward);
	double half_diagonal = std::sqrt(
		std::pow(0.5 * double(vehicle_length_proxy_m.get()), 2.0)
		+ std::pow(0.5 * double(vehicle_width_m.get()), 2.0)
		+ std::pow(
			0.5 * double(vehicle_height_above_tor_m.get()),
			2.0));
	double rotational_error =
		2.0 * half_diagonal * std::sin(0.5 * angle);
	return center_error + rotational_error;
}

void RailSweptEnvelopeManager::appendAdaptiveInterval(
	RouteRuntime &route,
	const VehiclePose &left,
	const VehiclePose &right,
	int depth)
{
	double middle_s = 0.5 * (
		left.leading_chainage_m + right.leading_chainage_m);
	VehiclePose middle = vehiclePose(route, middle_s);
	double error = poseDeviation(left, middle, right);

	if (error <= double(max_pose_deviation_m.get())
		|| depth >= maximum_refinement_depth.get())
	{
		route.boxes.emplace_back(
			carbodyBox(
				right,
				route,
				right.leading_chainage_m
					- route.current_start_chainage_m));
		return;
	}

	appendAdaptiveInterval(route, left, middle, depth + 1);
	appendAdaptiveInterval(route, middle, right, depth + 1);
}

void RailSweptEnvelopeManager::rebuildEnvelopes()
{
	if (!train)
		return;

	const double global_leading_s = train->getLeadingChainageM();
	const double step = std::max(
		0.05,
		double(max_chainage_step_m.get()));
	const double lookahead = std::max(
		0.0,
		double(lookahead_m.get()));

	for (auto &route : routes)
	{
		route.boxes.clear();
		route.box_aabbs.clear();
		route.bvh_box_indices.clear();
		route.bvh_nodes.clear();
		route.bvh_root = -1;
		double local_start =
			global_leading_s - route.global_chainage_origin_m;
		if (local_start < double(vehicle_base_m.get())
			|| local_start > route.length_m)
			continue;

		double local_end = std::min(
			route.length_m,
			local_start + lookahead);
		route.current_start_chainage_m = local_start;

		VehiclePose left = vehiclePose(route, local_start);
		route.boxes.emplace_back(
			carbodyBox(left, route, 0.0));
		double current = local_start;
		while (current < local_end - EPS)
		{
			double next = std::min(local_end, current + step);
			VehiclePose right = vehiclePose(route, next);
			appendAdaptiveInterval(route, left, right, 0);
			left = right;
			current = next;
		}
		buildRouteBVH(route);
	}
}

RailSweptEnvelopeManager::AABB
RailSweptEnvelopeManager::obbWorldAABB(const OBB &box) const
{
	Vec3 minimum(std::numeric_limits<double>::max());
	Vec3 maximum(-std::numeric_limits<double>::max());

	for (int sx : {-1, 1})
	{
		for (int sy : {-1, 1})
		{
			for (int sz : {-1, 1})
			{
				Vec3 corner = box.center
					+ Vec3(box.right)
						* (double(sx) * box.half_extents.x)
					+ Vec3(box.forward)
						* (double(sy) * box.half_extents.y)
					+ Vec3(box.up)
						* (double(sz) * box.half_extents.z);
				minimum.x = std::min(minimum.x, corner.x);
				minimum.y = std::min(minimum.y, corner.y);
				minimum.z = std::min(minimum.z, corner.z);
				maximum.x = std::max(maximum.x, corner.x);
				maximum.y = std::max(maximum.y, corner.y);
				maximum.z = std::max(maximum.z, corner.z);
			}
		}
	}
	return {minimum, maximum};
}

RailSweptEnvelopeManager::AABB
RailSweptEnvelopeManager::unionAABB(
	const AABB &a,
	const AABB &b)
{
	return {
		Vec3(
			std::min(a.minimum.x, b.minimum.x),
			std::min(a.minimum.y, b.minimum.y),
			std::min(a.minimum.z, b.minimum.z)),
		Vec3(
			std::max(a.maximum.x, b.maximum.x),
			std::max(a.maximum.y, b.maximum.y),
			std::max(a.maximum.z, b.maximum.z)),
	};
}

bool RailSweptEnvelopeManager::pointInAABB(
	const Vec3 &point,
	const AABB &box)
{
	return point.x >= box.minimum.x
		&& point.x <= box.maximum.x
		&& point.y >= box.minimum.y
		&& point.y <= box.maximum.y
		&& point.z >= box.minimum.z
		&& point.z <= box.maximum.z;
}

bool RailSweptEnvelopeManager::aabbIntersectsAABB(
	const AABB &a,
	const AABB &b)
{
	return a.minimum.x <= b.maximum.x
		&& a.maximum.x >= b.minimum.x
		&& a.minimum.y <= b.maximum.y
		&& a.maximum.y >= b.minimum.y
		&& a.minimum.z <= b.maximum.z
		&& a.maximum.z >= b.minimum.z;
}

RailSweptEnvelopeManager::AABB
RailSweptEnvelopeManager::worldBoundBoxToAABB(
	const WorldBoundBox &bound)
{
	Vec3 center = bound.getCenter();
	Vec3 half = bound.getSize() * 0.5;
	return {center - half, center + half};
}

void RailSweptEnvelopeManager::buildRouteBVH(RouteRuntime &route)
{
	route.box_aabbs.clear();
	route.bvh_box_indices.clear();
	route.bvh_nodes.clear();
	route.bvh_root = -1;
	if (route.boxes.empty())
		return;

	route.box_aabbs.reserve(route.boxes.size());
	for (const OBB &box : route.boxes)
		route.box_aabbs.emplace_back(obbWorldAABB(box));

	route.bvh_box_indices.resize(route.boxes.size());
	std::iota(
		route.bvh_box_indices.begin(),
		route.bvh_box_indices.end(),
		0);
	route.bvh_nodes.reserve(route.boxes.size() * 2);
	route.bvh_root = buildRouteBVHNode(
		route,
		0,
		int(route.bvh_box_indices.size()));
}

int RailSweptEnvelopeManager::buildRouteBVHNode(
	RouteRuntime &route,
	int start,
	int end)
{
	if (start >= end)
		return -1;

	AABB bound =
		route.box_aabbs[size_t(route.bvh_box_indices[size_t(start)])];
	for (int i = start + 1; i < end; ++i)
	{
		bound = unionAABB(
			bound,
			route.box_aabbs[
				size_t(route.bvh_box_indices[size_t(i)])]);
	}

	const int node_index = int(route.bvh_nodes.size());
	route.bvh_nodes.emplace_back();
	route.bvh_nodes[size_t(node_index)].bound = bound;

	const int count = end - start;
	constexpr int LEAF_SIZE = 4;
	if (count <= LEAF_SIZE)
	{
		BVHNode &leaf = route.bvh_nodes[size_t(node_index)];
		leaf.start = start;
		leaf.count = count;
		return node_index;
	}

	Vec3 centroid_minimum(std::numeric_limits<double>::max());
	Vec3 centroid_maximum(-std::numeric_limits<double>::max());
	for (int i = start; i < end; ++i)
	{
		const AABB &box = route.box_aabbs[
			size_t(route.bvh_box_indices[size_t(i)])];
		Vec3 centroid = (box.minimum + box.maximum) * 0.5;
		centroid_minimum.x = std::min(centroid_minimum.x, centroid.x);
		centroid_minimum.y = std::min(centroid_minimum.y, centroid.y);
		centroid_minimum.z = std::min(centroid_minimum.z, centroid.z);
		centroid_maximum.x = std::max(centroid_maximum.x, centroid.x);
		centroid_maximum.y = std::max(centroid_maximum.y, centroid.y);
		centroid_maximum.z = std::max(centroid_maximum.z, centroid.z);
	}
	Vec3 extent = centroid_maximum - centroid_minimum;
	int axis = 0;
	if (extent.y > extent.x && extent.y >= extent.z)
		axis = 1;
	else if (extent.z > extent.x && extent.z > extent.y)
		axis = 2;

	auto centroid_axis = [&](int box_index)
	{
		const AABB &box = route.box_aabbs[size_t(box_index)];
		if (axis == 0)
			return 0.5 * (box.minimum.x + box.maximum.x);
		if (axis == 1)
			return 0.5 * (box.minimum.y + box.maximum.y);
		return 0.5 * (box.minimum.z + box.maximum.z);
	};

	std::sort(
		route.bvh_box_indices.begin() + start,
		route.bvh_box_indices.begin() + end,
		[&](int lhs, int rhs)
		{
			double a = centroid_axis(lhs);
			double b = centroid_axis(rhs);
			if (a != b)
				return a < b;
			return lhs < rhs;
		});

	const int middle = start + count / 2;
	const int left = buildRouteBVHNode(route, start, middle);
	const int right = buildRouteBVHNode(route, middle, end);
	BVHNode &node = route.bvh_nodes[size_t(node_index)];
	node.left = left;
	node.right = right;
	return node_index;
}

bool RailSweptEnvelopeManager::routeContainsPointBVH(
	const RouteRuntime &route,
	const Vec3 &point) const
{
	if (route.bvh_root < 0)
		return false;

	int stack[128];
	int stack_size = 0;
	stack[stack_size++] = route.bvh_root;
	while (stack_size > 0)
	{
		const int node_index = stack[--stack_size];
		const BVHNode &node = route.bvh_nodes[size_t(node_index)];
		if (!pointInAABB(point, node.bound))
			continue;

		if (node.isLeaf())
		{
			for (int i = 0; i < node.count; ++i)
			{
				const int box_index = route.bvh_box_indices[
					size_t(node.start + i)];
				if (!pointInAABB(
						point,
						route.box_aabbs[size_t(box_index)]))
					continue;
				if (pointInBox(
						point,
						route.boxes[size_t(box_index)]))
					return true;
			}
			continue;
		}

		if (node.left >= 0 && stack_size < 128)
			stack[stack_size++] = node.left;
		if (node.right >= 0 && stack_size < 128)
			stack[stack_size++] = node.right;
	}
	return false;
}

bool RailSweptEnvelopeManager::routeIntersectsAABBBVH(
	const RouteRuntime &route,
	const AABB &aabb) const
{
	if (route.bvh_root < 0)
		return false;

	WorldBoundBox world_aabb(aabb.minimum, aabb.maximum);
	std::vector<int> stack;
	stack.reserve(32);
	stack.push_back(route.bvh_root);
	while (!stack.empty())
	{
		const int node_index = stack.back();
		stack.pop_back();
		const BVHNode &node = route.bvh_nodes[size_t(node_index)];
		if (!aabbIntersectsAABB(aabb, node.bound))
			continue;

		if (node.isLeaf())
		{
			for (int i = 0; i < node.count; ++i)
			{
				const int box_index = route.bvh_box_indices[
					size_t(node.start + i)];
				if (!aabbIntersectsAABB(
						aabb,
						route.box_aabbs[size_t(box_index)]))
					continue;
				if (boxIntersectsAABB(
						route.boxes[size_t(box_index)],
						world_aabb))
					return true;
			}
			continue;
		}

		if (node.left >= 0)
			stack.push_back(node.left);
		if (node.right >= 0)
			stack.push_back(node.right);
	}
	return false;
}

Math::WorldBoundBox RailSweptEnvelopeManager::routeBroadPhase(
	const RouteRuntime &route) const
{
	if (route.bvh_root < 0)
		return WorldBoundBox(Vec3(0.0), Vec3(0.0));
	const AABB &bound =
		route.bvh_nodes[size_t(route.bvh_root)].bound;
	return WorldBoundBox(bound.minimum, bound.maximum);
}

Math::WorldBoundBox RailSweptEnvelopeManager::allRoutesBroadPhase() const
{
	Vec3 minimum(
		std::numeric_limits<double>::max());
	Vec3 maximum(
		-std::numeric_limits<double>::max());
	bool any = false;

	for (const auto &route : routes)
	{
		if (route.boxes.empty())
			continue;
		WorldBoundBox bound = routeBroadPhase(route);
		Vec3 center = bound.getCenter();
		Vec3 half = bound.getSize() * 0.5;
		Vec3 lo = center - half;
		Vec3 hi = center + half;
		minimum.x = std::min(minimum.x, lo.x);
		minimum.y = std::min(minimum.y, lo.y);
		minimum.z = std::min(minimum.z, lo.z);
		maximum.x = std::max(maximum.x, hi.x);
		maximum.y = std::max(maximum.y, hi.y);
		maximum.z = std::max(maximum.z, hi.z);
		any = true;
	}

	if (!any)
		return WorldBoundBox(Vec3(0.0), Vec3(0.0));
	return WorldBoundBox(minimum, maximum);
}

bool RailSweptEnvelopeManager::pointInBox(
	const Vec3 &point,
	const OBB &box) const
{
	Vec3 delta = point - box.center;
	return std::abs(dot_axis(delta, box.right))
			<= double(box.half_extents.x)
		&& std::abs(dot_axis(delta, box.forward))
			<= double(box.half_extents.y)
		&& std::abs(dot_axis(delta, box.up))
			<= double(box.half_extents.z);
}

bool RailSweptEnvelopeManager::boxIntersectsAABB(
	const OBB &box,
	const WorldBoundBox &aabb) const
{
	// Separating Axis Theorem for OBB vs world-axis-aligned AABB.
	const vec3 U[3] = {
		normalize(box.right),
		normalize(box.forward),
		normalize(box.up),
	};
	const double A[3] = {
		double(box.half_extents.x),
		double(box.half_extents.y),
		double(box.half_extents.z),
	};

	Vec3 b_center = aabb.getCenter();
	Vec3 b_size = aabb.getSize();
	const double B[3] = {
		0.5 * b_size.x,
		0.5 * b_size.y,
		0.5 * b_size.z,
	};

	double R[3][3];
	double AbsR[3][3];
	for (int i = 0; i < 3; ++i)
	{
		R[i][0] = double(U[i].x);
		R[i][1] = double(U[i].y);
		R[i][2] = double(U[i].z);
		for (int j = 0; j < 3; ++j)
			AbsR[i][j] = std::abs(R[i][j]) + 1e-8;
	}

	Vec3 t_world = b_center - box.center;
	const double t[3] = {
		dot_axis(t_world, U[0]),
		dot_axis(t_world, U[1]),
		dot_axis(t_world, U[2]),
	};

	// OBB axes.
	for (int i = 0; i < 3; ++i)
	{
		double rb = B[0] * AbsR[i][0]
			+ B[1] * AbsR[i][1]
			+ B[2] * AbsR[i][2];
		if (std::abs(t[i]) > A[i] + rb)
			return false;
	}

	// World AABB axes.
	for (int j = 0; j < 3; ++j)
	{
		double ra = A[0] * AbsR[0][j]
			+ A[1] * AbsR[1][j]
			+ A[2] * AbsR[2][j];
		double world_t = (j == 0)
			? t_world.x
			: ((j == 1) ? t_world.y : t_world.z);
		if (std::abs(world_t) > ra + B[j])
			return false;
	}

	// Cross products U_i x world_axis_j.
	for (int i = 0; i < 3; ++i)
	{
		int i1 = (i + 1) % 3;
		int i2 = (i + 2) % 3;
		for (int j = 0; j < 3; ++j)
		{
			int j1 = (j + 1) % 3;
			int j2 = (j + 2) % 3;
			double ra =
				A[i1] * AbsR[i2][j]
				+ A[i2] * AbsR[i1][j];
			double rb =
				B[j1] * AbsR[i][j2]
				+ B[j2] * AbsR[i][j1];
			double projection = std::abs(
				t[i2] * R[i1][j]
				- t[i1] * R[i2][j]);
			if (projection > ra + rb)
				return false;
		}
	}
	return true;
}

bool RailSweptEnvelopeManager::routeIntersectsAABB(
	const RouteRuntime &route,
	const WorldBoundBox &aabb) const
{
	return routeIntersectsAABBBVH(
		route,
		worldBoundBoxToAABB(aabb));
}

bool RailSweptEnvelopeManager::objectMatchesMask(
	const ObjectPtr &object) const
{
	int mask = obstacle_intersection_mask.get();
	if (mask == 0)
		return true;
	for (int surface = 0;
		surface < object->getNumSurfaces();
		++surface)
	{
		if (object->getIntersection(surface)
			&& (object->getIntersectionMask(surface) & mask) != 0)
			return true;
	}
	return false;
}

bool RailSweptEnvelopeManager::isIgnored(const ObjectPtr &candidate) const
{
	if (!candidate)
		return true;
	const int candidate_id = candidate->getID();
	for (int i = 0; i < ignored_nodes.size(); ++i)
	{
		NodePtr ignored = ignored_nodes[i].get();
		if (ignored && ignored->getID() == candidate_id)
			return true;
	}
	return false;
}

RailSweptEnvelopeManager::Relevance
RailSweptEnvelopeManager::classifyHits(
	int hit_count,
	bool active_hit,
	int feasible_count,
	bool active_present) const
{
	String active = active_route_id.get();
	if (active.size() > 0 && active_present)
		return active_hit
			? Relevance::ACTIVE_ROUTE
			: Relevance::OUTSIDE;
	if (hit_count <= 0)
		return Relevance::OUTSIDE;
	if (hit_count == feasible_count)
		return Relevance::ALL_FEASIBLE_ROUTES;
	return Relevance::ROUTE_AMBIGUOUS;
}

bool RailSweptEnvelopeManager::isSafetyComplete() const
{
	if (!vehicleTrackAllowanceComplete() || routes.empty())
		return false;
	for (const auto &route : routes)
	{
		if (route.enabled && !route.path_uncertainty_complete)
			return false;
	}
	return true;
}

RailSweptEnvelopeManager::Relevance
RailSweptEnvelopeManager::classifyPoint(const Vec3 &point) const
{
	int feasible = 0;
	int hits = 0;
	bool active_hit = false;
	bool active_present = false;
	String active = active_route_id.get();

	for (const auto &route : routes)
	{
		if (route.boxes.empty())
			continue;
		++feasible;
		if (active.size() > 0
			&& route.route_id == active.get())
			active_present = true;
		const bool route_hit =
			routeContainsPointBVH(route, point);
		if (!route_hit)
			continue;
		++hits;
		if (active.size() > 0
			&& route.route_id == active.get())
			active_hit = true;
	}
	return classifyHits(hits, active_hit, feasible, active_present);
}

void RailSweptEnvelopeManager::queryWorldObjects()
{
	detections.clear();
	int feasible_count = 0;
	for (const auto &route : routes)
	{
		if (!route.boxes.empty())
			++feasible_count;
	}
	if (feasible_count <= 0)
		return;

	WorldBoundBox broad = allRoutesBroadPhase();
	Vector<ObjectPtr> candidates;
	if (!World::getIntersection(broad, candidates))
		return;

	String active = active_route_id.get();
	bool active_present = false;
	for (const auto &route : routes)
	{
		if (!route.boxes.empty()
			&& active.size() > 0
			&& route.route_id == active.get())
		{
			active_present = true;
			break;
		}
	}
	for (int candidate_index = 0;
		candidate_index < candidates.size();
		++candidate_index)
	{
		ObjectPtr object = candidates[candidate_index];
		if (!object || isIgnored(object) || !objectMatchesMask(object))
			continue;

		WorldBoundBox object_bound = object->getWorldBoundBox();
		Detection detection;
		detection.object = object;
		bool active_hit = false;

		for (const auto &route : routes)
		{
			if (route.boxes.empty())
				continue;
			if (!routeIntersectsAABB(route, object_bound))
				continue;
			detection.intersecting_route_ids.push_back(route.route_id);
			if (active.size() > 0
				&& route.route_id == active.get())
				active_hit = true;
		}

		detection.relevance = classifyHits(
			int(detection.intersecting_route_ids.size()),
			active_hit,
			feasible_count,
			active_present);
		if (detection.relevance != Relevance::OUTSIDE)
			detections.emplace_back(std::move(detection));
	}

	if (log_detection_changes.get()
		&& previous_detection_count != int(detections.size()))
	{
		Log::message(
			"RailSweptEnvelopeManager: %d relevant world objects across %d feasible routes\n",
			int(detections.size()),
			feasible_count);
	}
	previous_detection_count = int(detections.size());
}

void RailSweptEnvelopeManager::renderDebug() const
{
	if (!debug_visualization.get())
		return;

	for (size_t route_index = 0;
		route_index < routes.size();
		++route_index)
	{
		const auto &route = routes[route_index];
		const vec4 color =
			ROUTE_COLORS[route_index % 4];
		for (const OBB &box : route.boxes)
		{
			Vec3 corners[8];
			int index = 0;
			for (int sx : {-1, 1})
			{
				for (int sy : {-1, 1})
				{
					for (int sz : {-1, 1})
					{
						corners[index++] = box.center
							+ Vec3(box.right)
								* (double(sx) * box.half_extents.x)
							+ Vec3(box.forward)
								* (double(sy) * box.half_extents.y)
							+ Vec3(box.up)
								* (double(sz) * box.half_extents.z);
					}
				}
			}

			const int edges[12][2] = {
				{0, 1}, {0, 2}, {0, 4},
				{1, 3}, {1, 5}, {2, 3},
				{2, 6}, {3, 7}, {4, 5},
				{4, 6}, {5, 7}, {6, 7},
			};
			for (const auto &edge : edges)
				Visualizer::renderLine3D(
					corners[edge[0]],
					corners[edge[1]],
					color);
		}
	}
}

void RailSweptEnvelopeManager::update()
{
	if (!ready)
		return;
	rebuildEnvelopes();
	queryWorldObjects();
	renderDebug();
}

void RailSweptEnvelopeManager::shutdown()
{
	if (debug_visualization.get())
		Visualizer::setEnabled(visualizer_was_enabled);
	detections.clear();
	routes.clear();
	train = nullptr;
	ready = false;
}
