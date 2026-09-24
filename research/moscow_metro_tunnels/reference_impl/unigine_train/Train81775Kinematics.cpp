#include "Train81775Kinematics.h"

#include <UnigineLog.h>
#include <UnigineMathLib.h>
#include <UniginePhysics.h>
#include <UnigineVisualizer.h>

#include <algorithm>
#include <cmath>
#include <iterator>
#include <utility>

using namespace Unigine;
using namespace Unigine::Math;

REGISTER_COMPONENT(Train81775Kinematics);

namespace
{
	constexpr double CHORD_TOLERANCE_M = 1e-7;
	constexpr int CHORD_SOLVER_ITERATIONS = 80;

	double distance3(const Vec3 &a, const Vec3 &b)
	{
		return length(a - b);
	}

	vec3 orthogonal_up(const vec3 &forward, const vec3 &up_hint)
	{
		vec3 f = normalize(forward);
		vec3 hint = up_hint;
		if (length2(hint) <= 1e-12f)
			hint = vec3(0.0f, 0.0f, 1.0f);
		hint = normalize(hint);

		vec3 right = cross(f, hint);
		if (length2(right) <= 1e-12f)
		{
			hint = std::abs(f.z) < 0.9f
				? vec3(0.0f, 0.0f, 1.0f)
				: vec3(1.0f, 0.0f, 0.0f);
			right = cross(f, hint);
		}
		right = normalize(right);
		return normalize(cross(right, f));
	}

	vec3 interpolate_segment_up(
		const SplineGraphPtr &graph,
		int segment,
		float t)
	{
		vec3 start = graph->getSegmentStartUpVector(segment);
		vec3 end = graph->getSegmentEndUpVector(segment);
		if (length2(start) <= 1e-12f)
			start = vec3(0.0f, 0.0f, 1.0f);
		if (length2(end) <= 1e-12f)
			end = start;
		start = normalize(start);
		end = normalize(end);

		vec3 blended = start * (1.0f - t) + end * t;
		if (length2(blended) <= 1e-12f)
			blended = start;
		return normalize(blended);
	}

	vec3 transform_direction(
		const Mat4 &transform,
		const vec3 &direction)
	{
		Vec3 origin = transform * Vec3(0.0);
		Vec3 endpoint = transform * Vec3(direction);
		return normalize(vec3(endpoint - origin));
	}
}

void Train81775Kinematics::log_node_position(
	const char *label,
	const NodePtr &target) const
{
	if (!diagnostic_logging.get() || !target)
		return;
	Vec3 p = target->getWorldPosition();
	Log::message(
		"[Train81775] %s node_id=%d world=(%.6f, %.6f, %.6f)\n",
		label,
		target->getID(),
		p.x,
		p.y,
		p.z);
}

void Train81775Kinematics::log_track_sample(
	const char *label,
	double chainage_m,
	const TrackSample &sample) const
{
	if (!diagnostic_logging.get())
		return;
	Log::message(
		"[Train81775] %s s=%.6f pos=(%.6f, %.6f, %.6f) "
		"tangent=(%.6f, %.6f, %.6f) up=(%.6f, %.6f, %.6f)\n",
		label,
		chainage_m,
		sample.position.x,
		sample.position.y,
		sample.position.z,
		double(sample.tangent.x),
		double(sample.tangent.y),
		double(sample.tangent.z),
		double(sample.up.x),
		double(sample.up.y),
		double(sample.up.z));
}

void Train81775Kinematics::init()
{
	String spline_path = spline_file.get();
	if (diagnostic_logging.get())
	{
		Log::message(
			"[Train81775] INIT begin spline='%s' speed=%.6f m/s "
			"initial_leading_s=%.6f base=%.6f length_proxy=%.6f "
			"arc_samples=%d loop=%d\n",
			spline_path.get(),
			double(speed_mps.get()),
			double(initial_leading_chainage_m.get()),
			double(vehicle_base_m.get()),
			double(vehicle_length_proxy_m.get()),
			arc_length_samples_per_segment.get(),
			loop_route.get() ? 1 : 0);
	}
	if (spline_path.size() <= 0)
	{
		Log::error("Train81775Kinematics: spline_file is empty\n");
		return;
	}
	if (!carbody_node.get()
		|| !leading_bogie_node.get()
		|| !trailing_bogie_node.get())
	{
		Log::error(
			"Train81775Kinematics: carbody and both bogie nodes are required\n");
		return;
	}
	if (diagnostic_logging.get())
	{
		Log::message("[Train81775] Node positions BEFORE spline snap:\n");
		log_node_position("carbody", carbody_node.get());
		log_node_position("leading_bogie", leading_bogie_node.get());
		log_node_position("trailing_bogie", trailing_bogie_node.get());
	}

	spline_to_world_transform = Mat4_identity;
	if (spline_space_node.get())
	{
		spline_to_world_transform =
			spline_space_node.get()->getWorldTransform();
		const vec3 scale =
			spline_to_world_transform.getScale();
		if (diagnostic_logging.get())
		{
			const Vec3 translation =
				spline_to_world_transform.getTranslate();
			Log::message(
				"[Train81775] Spline Space Node id=%d "
				"translation=(%.6f, %.6f, %.6f) "
				"scale=(%.6f, %.6f, %.6f)\n",
				spline_space_node.get()->getID(),
				translation.x,
				translation.y,
				translation.z,
				double(scale.x),
				double(scale.y),
				double(scale.z));
		}
		if (
			std::abs(double(scale.x) - 1.0) > 1e-4
			|| std::abs(double(scale.y) - 1.0) > 1e-4
			|| std::abs(double(scale.z) - 1.0) > 1e-4)
		{
			Log::warning(
				"[Train81775] Spline Space Node has non-unit scale. "
				"Rail chainage/chord geometry assumes a rigid transform.\n");
		}
	}
	else if (diagnostic_logging.get())
	{
		Log::warning(
			"[Train81775] Spline Space Node is empty; raw .spl coordinates "
			"will be treated as UNIGINE world coordinates.\n");
	}

	if (vehicle_base_m.get() <= 0.0f)
	{
		Log::error("Train81775Kinematics: vehicle_base_m must be positive\n");
		return;
	}
	spline_graph = SplineGraph::create();
	if (!spline_graph->load(spline_path))
	{
		Log::error(
			"Train81775Kinematics: failed to load spline: %s\n",
			spline_path.get());
		spline_graph.clear();
		return;
	}
	if (spline_graph->getNumSegments() <= 0)
	{
		Log::error("Train81775Kinematics: spline has no segments\n");
		spline_graph.clear();
		return;
	}

	rebuild_arc_length_luts();
	if (diagnostic_logging.get())
	{
		Log::message(
			"[Train81775] Spline loaded: segments=%d route_length=%.6f m\n",
			spline_graph->getNumSegments(),
			route_length_m);
		TrackSample route_start_local = sample_route_local(0.0);
		TrackSample route_end_local =
			sample_route_local(route_length_m);
		TrackSample route_start = sample_route(0.0);
		TrackSample route_end = sample_route(route_length_m);
		log_track_sample("route_start_local", 0.0, route_start_local);
		log_track_sample(
			"route_end_local",
			route_length_m,
			route_end_local);
		log_track_sample("route_start_world", 0.0, route_start);
		log_track_sample(
			"route_end_world",
			route_length_m,
			route_end);
	}
	if (route_length_m <= double(vehicle_base_m.get()))
	{
		Log::error(
			"Train81775Kinematics: route is shorter than vehicle base\n");
		spline_graph.clear();
		return;
	}

	leading_chainage_m = double(initial_leading_chainage_m.get());
	current_speed_mps = double(speed_mps.get());
	if (!loop_route.get() && leading_chainage_m < double(vehicle_base_m.get()))
		leading_chainage_m = double(vehicle_base_m.get()) + 0.01;
	if (!loop_route.get())
		leading_chainage_m = clamp(
			leading_chainage_m,
			double(vehicle_base_m.get()) + 0.01,
			route_length_m);

	if (diagnostic_logging.get())
	{
		const double trailing_s = solve_trailing_chainage(leading_chainage_m);
		const TrackSample front = sample_route(leading_chainage_m);
		const TrackSample rear = sample_route(trailing_s);
		const Vec3 body = (front.position + rear.position) * 0.5;
		const Vec3 current_body =
			carbody_node.get()->getWorldPosition();
		const double initial_snap_distance =
			distance3(current_body, body);
		if (initial_snap_distance > 5.0)
		{
			Log::warning(
				"[Train81775] Initial spline target is %.3f m from the "
				"current carbody position. Set Spline Space Node to the "
				"same transformed root/dummy used by the imported tunnel.\n",
				initial_snap_distance);
		}
		Log::message(
			"[Train81775] Initial resolved chainage: leading=%.6f trailing=%.6f "
			"chord=%.6f m body_target=(%.6f, %.6f, %.6f)\n",
			leading_chainage_m,
			trailing_s,
			distance3(front.position, rear.position),
			body.x,
			body.y,
			body.z);
		log_track_sample("initial_leading", leading_chainage_m, front);
		log_track_sample("initial_trailing", trailing_s, rear);
	}

	visualizer_was_enabled = Visualizer::isEnabled();
	if (debug_visualization.get())
		Visualizer::setEnabled(true);

	ready = true;
	diagnostic_ticks_remaining = std::max(
		0,
		diagnostic_physics_ticks.get());
	apply_vehicle_pose();

	if (diagnostic_logging.get())
	{
		Log::message("[Train81775] Node positions AFTER initial spline snap:\n");
		log_node_position("carbody", carbody_node.get());
		log_node_position("leading_bogie", leading_bogie_node.get());
		log_node_position("trailing_bogie", trailing_bogie_node.get());
		Log::message("[Train81775] INIT complete ready=1\n");
	}
}

void Train81775Kinematics::rebuild_arc_length_luts()
{
	arc_luts.clear();
	route_length_m = 0.0;
	const int samples = std::max(8, arc_length_samples_per_segment.get());

	for (int segment = 0; segment < spline_graph->getNumSegments(); ++segment)
	{
		SegmentArcLut lut;
		lut.route_start_m = route_length_m;
		lut.cumulative_m.reserve(size_t(samples + 1));
		lut.cumulative_m.push_back(0.0);

		Vec3 previous = spline_graph->calcSegmentPoint(segment, 0.0f);
		double cumulative = 0.0;
		for (int i = 1; i <= samples; ++i)
		{
			float t = float(i) / float(samples);
			Vec3 current = spline_graph->calcSegmentPoint(segment, t);
			cumulative += distance3(previous, current);
			lut.cumulative_m.push_back(cumulative);
			previous = current;
		}
		lut.length_m = cumulative;
		route_length_m += cumulative;
		arc_luts.push_back(std::move(lut));
	}
}

double Train81775Kinematics::normalize_route_chainage(double chainage_m) const
{
	if (!loop_route.get())
		return clamp(chainage_m, 0.0, route_length_m);

	double result = std::fmod(chainage_m, route_length_m);
	if (result < 0.0)
		result += route_length_m;
	return result;
}

Train81775Kinematics::TrackSample
Train81775Kinematics::sample_route_local(double chainage_m) const
{
	double s = normalize_route_chainage(chainage_m);
	int segment = int(arc_luts.size()) - 1;
	for (int i = 0; i < int(arc_luts.size()); ++i)
	{
		const auto &lut = arc_luts[size_t(i)];
		if (s <= lut.route_start_m + lut.length_m || i + 1 == int(arc_luts.size()))
		{
			segment = i;
			break;
		}
	}

	const auto &lut = arc_luts[size_t(segment)];
	double local_m = clamp(s - lut.route_start_m, 0.0, lut.length_m);
	auto it = std::lower_bound(
		lut.cumulative_m.begin(),
		lut.cumulative_m.end(),
		local_m);
	size_t upper_index = size_t(std::distance(lut.cumulative_m.begin(), it));
	if (upper_index == 0)
		upper_index = 1;
	if (upper_index >= lut.cumulative_m.size())
		upper_index = lut.cumulative_m.size() - 1;
	size_t lower_index = upper_index - 1;

	double l0 = lut.cumulative_m[lower_index];
	double l1 = lut.cumulative_m[upper_index];
	double alpha = (l1 > l0) ? (local_m - l0) / (l1 - l0) : 0.0;
	double sample_count = double(lut.cumulative_m.size() - 1);
	double t0 = double(lower_index) / sample_count;
	double t1 = double(upper_index) / sample_count;
	float t = float(t0 + (t1 - t0) * alpha);

	Vec3 position = spline_graph->calcSegmentPoint(segment, t);
	vec3 tangent = normalize(
		spline_graph->calcSegmentTangent(segment, t));
	vec3 up_hint = interpolate_segment_up(
		spline_graph,
		segment,
		t);
	vec3 up = orthogonal_up(tangent, up_hint);
	return {position, tangent, up};
}

Train81775Kinematics::TrackSample
Train81775Kinematics::sample_route(double chainage_m) const
{
	const TrackSample local = sample_route_local(chainage_m);
	const Vec3 world_position =
		spline_to_world_transform * local.position;
	const vec3 world_tangent = transform_direction(
		spline_to_world_transform,
		local.tangent);
	const vec3 world_up_hint = transform_direction(
		spline_to_world_transform,
		local.up);
	const vec3 world_up =
		orthogonal_up(world_tangent, world_up_hint);
	return {world_position, world_tangent, world_up};
}

double Train81775Kinematics::solve_trailing_chainage(
	double leading_s) const
{
	const TrackSample leading = sample_route(leading_s);
	auto residual = [&](double candidate_s)
	{
		return distance3(leading.position, sample_route(candidate_s).position)
			- double(vehicle_base_m.get());
	};

	double available = loop_route.get() ? route_length_m : leading_s;
	if (available <= double(vehicle_base_m.get()))
		return leading_s - available;

	double delta = std::min(
		available,
		std::max(double(vehicle_base_m.get()) * 1.02, 0.25));
	double hi = leading_s;
	double lo = leading_s - delta;
	double lo_residual = residual(lo);

	while (lo_residual < 0.0 && delta < available)
	{
		delta = std::min(
			available,
			std::max(delta * 1.5, delta + 0.25));
		lo = leading_s - delta;
		lo_residual = residual(lo);
	}

	if (lo_residual < 0.0)
		return lo;

	for (int i = 0; i < CHORD_SOLVER_ITERATIONS; ++i)
	{
		double mid = 0.5 * (lo + hi);
		double value = residual(mid);
		if (std::abs(value) <= CHORD_TOLERANCE_M
			|| hi - lo <= CHORD_TOLERANCE_M)
			return mid;
		if (value >= 0.0)
			lo = mid;
		else
			hi = mid;
	}
	return 0.5 * (lo + hi);
}

void Train81775Kinematics::apply_vehicle_pose()
{
	if (!ready)
		return;

	double trailing_s = solve_trailing_chainage(leading_chainage_m);
	TrackSample front = sample_route(leading_chainage_m);
	TrackSample rear = sample_route(trailing_s);

	leading_bogie_node.get()->setWorldPosition(front.position);
	leading_bogie_node.get()->setWorldDirection(
		front.tangent,
		front.up,
		AXIS_Y);

	trailing_bogie_node.get()->setWorldPosition(rear.position);
	trailing_bogie_node.get()->setWorldDirection(
		rear.tangent,
		rear.up,
		AXIS_Y);

	Vec3 body_position = (front.position + rear.position) * 0.5;
	vec3 body_forward = normalize(vec3(front.position - rear.position));
	vec3 body_up_hint = normalize(front.up + rear.up);
	vec3 body_up = orthogonal_up(body_forward, body_up_hint);

	carbody_node.get()->setWorldPosition(body_position);
	carbody_node.get()->setWorldDirection(
		body_forward,
		body_up,
		AXIS_Y);

	double half_proxy = 0.5 * double(vehicle_length_proxy_m.get());
	debug_front_proxy = body_position + Vec3(body_forward) * half_proxy;
	debug_rear_proxy = body_position - Vec3(body_forward) * half_proxy;
}

void Train81775Kinematics::update_physics()
{
	if (!ready)
		return;

	const double dt = double(Physics::getIFps());
	const double before_s = leading_chainage_m;
	leading_chainage_m += current_speed_mps * dt;
	if (!loop_route.get() && leading_chainage_m >= route_length_m)
	{
		leading_chainage_m = route_length_m;
		current_speed_mps = 0.0;
	}
	apply_vehicle_pose();

	if (diagnostic_logging.get() && diagnostic_ticks_remaining > 0)
	{
		const double trailing_s =
			solve_trailing_chainage(leading_chainage_m);
		Log::message(
			"[Train81775] PHYS tick=%d dt=%.9f speed=%.6f "
			"leading_s: %.6f -> %.6f trailing_s=%.6f\n",
			diagnostic_physics_ticks.get()
				- diagnostic_ticks_remaining
				+ 1,
			dt,
			current_speed_mps,
			before_s,
			leading_chainage_m,
			trailing_s);
		log_node_position("carbody", carbody_node.get());
		log_node_position("leading_bogie", leading_bogie_node.get());
		log_node_position("trailing_bogie", trailing_bogie_node.get());
		--diagnostic_ticks_remaining;
	}
}

void Train81775Kinematics::update()
{
	if (!ready || !debug_visualization.get())
		return;

	Vec3 front = leading_bogie_node.get()->getWorldPosition();
	Vec3 rear = trailing_bogie_node.get()->getWorldPosition();
	Visualizer::renderLine3D(front, rear, vec4_green);
	Visualizer::renderPoint3D(front, 0.08f, vec4_green);
	Visualizer::renderPoint3D(rear, 0.08f, vec4_green);
	Visualizer::renderPoint3D(debug_front_proxy, 0.06f, vec4_red);
	Visualizer::renderPoint3D(debug_rear_proxy, 0.06f, vec4_red);
}

void Train81775Kinematics::shutdown()
{
	if (diagnostic_logging.get())
		Log::message("[Train81775] SHUTDOWN\n");
	if (debug_visualization.get())
		Visualizer::setEnabled(visualizer_was_enabled);
	ready = false;
	spline_graph.clear();
	arc_luts.clear();
}
