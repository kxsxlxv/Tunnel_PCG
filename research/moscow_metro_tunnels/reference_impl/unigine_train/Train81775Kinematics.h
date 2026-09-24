#pragma once

#include <UnigineComponentSystem.h>
#include <UnigineNodes.h>
#include <UnigineObjects.h>
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
	// Optional rigid transform from Tunnel_PCG spline coordinates into the
	// UNIGINE world. Point this at the same transformed root/dummy used for the
	// imported tunnel. Leave empty only when the tunnel is already in raw
	// Tunnel_PCG world coordinates.
	PROP_PARAM(Node, spline_space_node);
	// Default runtime behavior: register the route against the actual generated
	// running-rail meshes in the UNIGINE world. No manual train placement is
	// required. The expected chunk-first names are
	// CHxxxxx__PROD_RAIL_0 / CHxxxxx__PROD_RAIL_1.
	PROP_PARAM(Toggle, auto_register_to_tunnel_rails, true);
	PROP_PARAM(Int, registration_chunk_id, 0);
	PROP_PARAM(Float, registration_chunk_length_m, 20.0f);

	// Legacy fallback only. Keep disabled for a generated tunnel because it
	// aligns the route to the vehicle spawn frame, not to the tunnel.
	PROP_PARAM(Toggle, auto_anchor_to_initial_vehicle_frame, false);
	PROP_PARAM(Toggle, preserve_initial_bogie_visual_offsets, true);
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
	bool isReady() const { return ready; }
	const Unigine::Math::Mat4 &getSplineToWorldTransform() const
	{
		return spline_to_world_transform;
	}
	Unigine::Math::Vec3 mapSplinePointToWorld(
		const Unigine::Math::Vec3 &local_point) const;
	Unigine::Math::vec3 mapSplineDirectionToWorld(
		const Unigine::Math::vec3 &local_direction) const;

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
	TrackSample sample_route_local(double chainage_m) const;
	TrackSample sample_route(double chainage_m) const;
	bool configure_automatic_tunnel_rail_registration();
	void configure_automatic_spawn_anchor();
	void capture_initial_bogie_visual_offsets();
	bool collect_static_mesh_world_vertices(
		const char *node_name,
		std::vector<Unigine::Math::Vec3> &vertices,
		Unigine::Math::Vec3 &centroid) const;
	Unigine::Math::Vec3 apply_bogie_visual_offset(
		const TrackSample &sample,
		const Unigine::Math::vec3 &local_offset) const;
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
	Unigine::Math::Mat4 spline_to_world_transform =
		Unigine::Math::Mat4_identity;

	bool automatic_spawn_anchor_active = false;
	Unigine::Math::Vec3 anchor_source_position;
	Unigine::Math::vec3 anchor_source_right =
		Unigine::Math::vec3(1.0f, 0.0f, 0.0f);
	Unigine::Math::vec3 anchor_source_forward =
		Unigine::Math::vec3(0.0f, 1.0f, 0.0f);
	Unigine::Math::vec3 anchor_source_up =
		Unigine::Math::vec3(0.0f, 0.0f, 1.0f);
	Unigine::Math::Vec3 anchor_target_position;
	Unigine::Math::vec3 anchor_target_right =
		Unigine::Math::vec3(1.0f, 0.0f, 0.0f);
	Unigine::Math::vec3 anchor_target_forward =
		Unigine::Math::vec3(0.0f, 1.0f, 0.0f);
	Unigine::Math::vec3 anchor_target_up =
		Unigine::Math::vec3(0.0f, 0.0f, 1.0f);

	bool bogie_visual_offsets_active = false;
	Unigine::Math::vec3 carbody_visual_offset =
		Unigine::Math::vec3_zero;
	Unigine::Math::vec3 leading_bogie_visual_offset =
		Unigine::Math::vec3_zero;
	Unigine::Math::vec3 trailing_bogie_visual_offset =
		Unigine::Math::vec3_zero;

	double route_length_m = 0.0;
	double leading_chainage_m = 0.0;
	double current_speed_mps = 0.0;
	bool ready = false;
	bool visualizer_was_enabled = false;
	int diagnostic_ticks_remaining = 0;

	Unigine::Math::Vec3 debug_front_proxy;
	Unigine::Math::Vec3 debug_rear_proxy;
};
