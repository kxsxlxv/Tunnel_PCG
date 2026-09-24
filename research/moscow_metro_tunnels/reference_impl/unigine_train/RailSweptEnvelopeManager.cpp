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

using namespace Unigine;
using namespace Unigine::Math;

REGISTER_COMPONENT(RailSweptEnvelopeManager);

namespace
{
	constexpr double EPS = 1e-9;
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

RailSweptEnvelopeManager::OBB
RailSweptEnvelopeManager::carbodyBox(const VehiclePose &pose) const
{
	const double height = double(vehicle_height_above_tor_m.get());
	const double inflation = double(max_pose_deviation_m.get());

	OBB box;
	box.right = pose.body_right;
	box.forward = pose.body_forward;
	box.up = pose.body_up;
	box.center = pose.body_position
		+ Vec3(pose.body_up) * (0.5 * height);
	box.half_extents = vec3(
		0.5f * vehicle_width_m.get()
			+ known_lateral_allowance_m.get()
			+ float(inflation),
		0.5f * vehicle_length_proxy_m.get()
			+ float(inflation),
		0.5f * vehicle_height_above_tor_m.get()
			+ known_vertical_allowance_m.get()
			+ float(inflation));
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
		route.boxes.emplace_back(carbodyBox(right));
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
		double local_start =
			global_leading_s - route.global_chainage_origin_m;
		if (local_start < double(vehicle_base_m.get())
			|| local_start > route.length_m)
			continue;

		double local_end = std::min(
			route.length_m,
			local_start + lookahead);

		VehiclePose left = vehiclePose(route, local_start);
		route.boxes.emplace_back(carbodyBox(left));
		double current = local_start;
		while (current < local_end - EPS)
		{
			double next = std::min(local_end, current + step);
			VehiclePose right = vehiclePose(route, next);
			appendAdaptiveInterval(route, left, right, 0);
			left = right;
			current = next;
		}
	}
}

Math::WorldBoundBox RailSweptEnvelopeManager::routeBroadPhase(
	const RouteRuntime &route) const
{
	Vec3 minimum(
		std::numeric_limits<double>::max());
	Vec3 maximum(
		-std::numeric_limits<double>::max());

	for (const OBB &box : route.boxes)
	{
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
	}
	return WorldBoundBox(minimum, maximum);
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
	for (const OBB &box : route.boxes)
	{
		if (boxIntersectsAABB(box, aabb))
			return true;
	}
	return false;
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
	for (int i = 0; i < ignored_nodes.size(); ++i)
	{
		if (candidate == ignored_nodes[i].get())
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
		bool route_hit = false;
		for (const OBB &box : route.boxes)
		{
			if (pointInBox(point, box))
			{
				route_hit = true;
				break;
			}
		}
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
