#pragma once

#include <UnigineComponentSystem.h>
#include <UnigineNodes.h>
#include <UnigineSplineGraph.h>

#include <vector>

// Reference UNIGINE component for one resolved rail-route hypothesis.
//
// The component intentionally moves the two bogies independently on the track
// spline and derives the rigid carbody from the chord between bogie pivots.
// It is not a complete safety-certified kinematic gauge implementation.
class Train81775Kinematics : public Unigine::ComponentBase
{
public:
	COMPONENT_DEFINE(Train81775Kinematics, Unigine::ComponentBase);
	COMPONENT_DESCRIPTION(
		"81-775 two-bogie rigid-chord rail vehicle reference kinematics");

	COMPONENT_INIT(init);
	COMPONENT_UPDATE_PHYSICS(update_physics);
	COMPONENT_UPDATE(update);
	COMPONENT_SHUTDOWN(shutdown);

	PROP_PARAM(File, spline_file);
	PROP_PARAM(Node, carbody_node);
	PROP_PARAM(Node, leading_bogie_node);
	PROP_PARAM(Node, trailing_bogie_node);

	PROP_PARAM(Float, speed_mps, 10.0f);
	PROP_PARAM(Float, initial_leading_chainage_m, 20.0f);
	PROP_PARAM(Float, vehicle_base_m, 12.6f);
	PROP_PARAM(Float, vehicle_length_proxy_m, 20.08f);
	PROP_PARAM(Int, arc_length_samples_per_segment, 128);
	PROP_PARAM(Toggle, loop_route, false);
	PROP_PARAM(Toggle, debug_visualization, true);
	PROP_PARAM(Toggle, diagnostic_logging, true);
	PROP_PARAM(Int, diagnostic_physics_ticks, 5);

	double getLeadingChainageM() const { return leading_chainage_m; }
	double getRouteLengthM() const { return route_length_m; }

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

	void init();
	void update_physics();
	void update();
	void shutdown();

	void rebuild_arc_length_luts();
	TrackSample sample_route(double chainage_m) const;
	double solve_trailing_chainage(double leading_chainage_m) const;
	void apply_vehicle_pose();
	void log_node_position(
		const char *label,
		const Unigine::NodePtr &node) const;
	void log_track_sample(
		const char *label,
		double chainage_m,
		const TrackSample &sample) const;
	double normalize_route_chainage(double chainage_m) const;

	Unigine::SplineGraphPtr spline_graph;
	std::vector<SegmentArcLut> arc_luts;
	double route_length_m = 0.0;
	double leading_chainage_m = 0.0;
	double current_speed_mps = 0.0;
	bool ready = false;
	bool visualizer_was_enabled = false;
	int diagnostic_ticks_remaining = 0;

	Unigine::Math::Vec3 debug_front_proxy;
	Unigine::Math::Vec3 debug_rear_proxy;
};
