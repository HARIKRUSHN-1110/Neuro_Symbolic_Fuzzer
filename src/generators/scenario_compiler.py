# src/generators/scenario_compiler.py
import os
import random
import logging
from scenariogeneration import xosc
from src.core.knowledge_graph import KnowledgeGraph
from src.core.config import settings

# --- IMPORT OFFICIAL TRAFFIC LOGIC ---
# Ensure generate_traffic.py and road_helpers.py are in src/generators/
from src.generators.generate_traffic import get_vehicle_positions 

logger = logging.getLogger(__name__)

class ScenarioCompiler:
    def __init__(self):
        self.kg = KnowledgeGraph(db_dir="chroma_db")

    def compile(self, blueprint: dict, output_name="ai_scenario.xosc"):
        """
        Symbolic Engine: Converts JSON Blueprint -> OpenSCENARIO (.xosc)
        """
        # 1. RESOLVE CONTEXT
        map_key = blueprint.get("map_key", "city")
        
        if map_key in self.kg.static_maps:
            context = self.kg.static_maps[map_key]
        else:
            context = self.kg.get_map_context(blueprint.get("scenario_type", "city"))
            
        # Define paths
        road_path = os.path.join(settings.ESMINI_BIN_PATH, "../resources/xodr", context["file"])
        scene_path = os.path.join(settings.ESMINI_BIN_PATH, "../resources/models", context["model_file"])
        
        road = xosc.RoadNetwork(roadfile=road_path, scenegraph=scene_path)

        # 2. ENTITIES
        entities = xosc.Entities()
        init = xosc.Init()
        step_time = xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)
        
        occupied_positions = [] 

        # A. BUILD PRIMARY ACTORS
        first_actor_name = None
        for actor in blueprint["actors"]:
            name = actor["name"]
            if not first_actor_name: first_actor_name = name
            
            # Save position to avoid collisions
            lane = actor.get("lane", -1)
            s_pos = actor.get("s", 0)
            occupied_positions.append((lane, s_pos))

            e_type = actor.get("type", "car")
            self._add_entity(entities, name, e_type)

            # Init Position
            default_lanes = context.get("lanes", context.get("driving_lanes", [-1]))
            lane_id = actor.get("lane", default_lanes[0])
            
            speed = actor.get("speed", 30) / 3.6 
            
            offset = actor.get("offset", 0)
            if e_type == "pedestrian" and offset == 0: offset = -4.0

            init.add_init_action(name, xosc.TeleportAction(xosc.LanePosition(s=s_pos, offset=offset, lane_id=lane_id, road_id=0)))
            init.add_init_action(name, xosc.AbsoluteSpeedAction(speed, step_time))

        # B. MACRO: DENSE TRAFFIC (Using Official Logic)
        if blueprint.get("traffic_density") == "high":
            # Pass road_path so the generator can parse the OpenDRIVE file
            self._generate_dense_traffic(entities, init, road_path, occupied_positions)

        # 3. STORYBOARD
        stop_trigger = xosc.ValueTrigger("StopSim", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(60, xosc.Rule.greaterThan), triggeringpoint="stop")
        sb = xosc.StoryBoard(init, stop_trigger)

        for idx, action in enumerate(blueprint["actions"]):
            actor_name = action.get("actor", first_actor_name)
            man_name = f"{actor_name}_act_{idx}_{action['type']}"
            maneuver = xosc.Maneuver(man_name)
            event_added = False

            # TRAFFIC LIGHTS
            if action["type"] == "traffic_light":
                tl_id = action.get("id", "1")
                raw_state = action.get("state", "red").lower()
                esmini_state = "on;off;off"
                if "green" in raw_state: esmini_state = "off;off;on"
                elif "yellow" in raw_state: esmini_state = "off;on;off"
                elif ";" in raw_state: esmini_state = raw_state 
                
                tl_action = xosc.TrafficSignalStateAction(tl_id, esmini_state)
                trig = xosc.ValueTrigger("TLTrig", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(action.get("trigger_time", 0), xosc.Rule.greaterThan))
                evt = xosc.Event("TLEvent", xosc.Priority.override)
                evt.add_trigger(trig)
                evt.add_action("TLAction", tl_action)
                maneuver.add_event(evt)
                event_added = True

            # LANE CHANGE 
            elif action["type"] == "lane_change":
                target_lane = action.get("target_lane", -1)
                duration = action.get("duration", 3.0)
                lc_action = xosc.AbsoluteLaneChangeAction(target_lane, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, duration))
                
                if "trigger_entity" in action:
                    ent = action["trigger_entity"]
                    dist = action.get("trigger_dist", 20)
                    cond = xosc.RelativeDistanceCondition(dist, xosc.Rule.lessThan, entity=ent, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
                    # Trigger entity is the ACTOR (Ego), triggered by proximity to TARGET
                    trig = xosc.EntityTrigger("LCTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor_name)
                else:
                    trig = xosc.ValueTrigger("LCTrig", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(action.get("trigger_time", 2), xosc.Rule.greaterThan))
                
                evt = xosc.Event("LCEvent", xosc.Priority.override)
                evt.add_trigger(trig)
                evt.add_action("LCAction", lc_action)
                maneuver.add_event(evt)
                event_added = True

            # PEDESTRIAN CROSSING
            elif action["type"] == "cross_street":
                start_s = 50 
                duration = 5.0
                traj_shape = xosc.Polyline([0.0, duration], [xosc.LanePosition(s=start_s, offset=-4, lane_id=-1, road_id=0), xosc.LanePosition(s=start_s, offset=4, lane_id=-1, road_id=0)])
                traj = xosc.Trajectory("WalkPath", False)
                traj.add_shape(traj_shape)
                cross_action = xosc.FollowTrajectoryAction(traj, xosc.FollowingMode.position, xosc.ReferenceContext.relative, 1.0, 0.0)
                
                target_ent = action.get("trigger_entity", "Ego")
                cond = xosc.RelativeDistanceCondition(action.get("trigger_dist", 30), xosc.Rule.lessThan, entity=target_ent, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
                trig = xosc.EntityTrigger("CrossTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=target_ent)
                
                evt = xosc.Event("CrossEvent", xosc.Priority.override)
                evt.add_trigger(trig)
                evt.add_action("WalkAction", cross_action)
                maneuver.add_event(evt)
                event_added = True

            # SPEED CHANGE 
            elif action["type"] in ["brake", "speed_change", "accelerate", "decelerate", "stop"]:
                spd = action.get("target_speed", 0) / 3.6
                dur = action.get("duration", 5.0)
                if action["type"] == "brake" and "target_speed" not in action:
                    spd = 0.0
                if action["type"] == "stop":
                    spd = 0.0
                spd_action = xosc.AbsoluteSpeedAction(spd, xosc.TransitionDynamics(xosc.DynamicsShapes.linear, xosc.DynamicsDimension.time, dur))
                trig = xosc.ValueTrigger("SpeedTrig", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(action.get("trigger_time", 5), xosc.Rule.greaterThan))
                evt = xosc.Event("SpeedEvent", xosc.Priority.override)
                evt.add_trigger(trig)
                evt.add_action("SpeedAction", spd_action)
                maneuver.add_event(evt)
                event_added = True

            if event_added:
                sb.add_maneuver(maneuver, actor_name)

        # 4. WRITE
        scn = xosc.Scenario("NeuroScenario", "AI_Gen", xosc.ParameterDeclarations(), entities=entities, storyboard=sb, roadnetwork=road, catalog=xosc.Catalog())
        full_path = os.path.join(settings.OUTPUT_DIR, output_name)
        scn.write_xml(full_path)
        return full_path

    def _add_entity(self, entities, name, e_type, model_override=None):
        # Default models
        model = "car_white.osgb"
        cat = xosc.VehicleCategory.car
        bb = xosc.BoundingBox(2.0, 5.0, 1.8, 2.0, 0.0, 0.0)
        
        # Override if generated traffic provides a specific color/model
        if model_override:
            # e.g., "car_blue" -> "car_blue.osgb"
            model = f"{model_override}.osgb"

        if e_type == "pedestrian":
            bb = xosc.BoundingBox(0.5, 0.6, 1.8, 0.0, 0.0, 0.0)
            obj = xosc.Pedestrian(name, 80, xosc.PedestrianCategory.pedestrian, bb)
            if not model_override: model = "car_red.osgb" # Fallback if no specific ped model
        
        elif e_type in ["truck", "bus"]:
            bb = xosc.BoundingBox(3.0, 10.0, 3.5, 2.0, 0.0, 0.0)
            fa = xosc.Axle(0.5, 0.8, 1.68, 2.9, 0.35)
            ra = xosc.Axle(0.0, 0.8, 1.68, 0.0, 0.35)
            obj = xosc.Vehicle(name, xosc.VehicleCategory.truck, bb, fa, ra, 69, 10, 10)
            if not model_override: model = "car_red.osgb" # Fallback
            
        else: # Car
            fa = xosc.Axle(0.5, 0.8, 1.68, 2.9, 0.35)
            ra = xosc.Axle(0.0, 0.8, 1.68, 0.0, 0.35)
            obj = xosc.Vehicle(name, xosc.VehicleCategory.car, bb, fa, ra, 69, 10, 10)
            
        obj.add_property("osgb", f"../resources/models/{model}")
        obj.add_property("model_id", "0")
        entities.add_scenario_object(name, obj)

    def _generate_dense_traffic(self, entities, init, road_path, occupied_positions):
        print(f"[COMPILER] Attempting to generate dense traffic...")
        print(f"           Road file: {road_path}")

        if occupied_positions:
            ego_start_pos = (occupied_positions[0][1], 0, occupied_positions[0][0], 0)
        else:
            ego_start_pos = (0, 0, -2, 0)

        step_time = xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)

        try:
            # Call the generator
            traffic_positions = get_vehicle_positions(
                roadfile=road_path,
                ego_pos=ego_start_pos,
                density=2.0,  # INCREASED DENSITY (Try 2.0 or 3.0 to force more cars)
                catalog_path=None 
            )
            
            # DEBUG: How many did we find?
            print(f"[COMPILER] Generator found {len(traffic_positions)} potential positions.")

            added_count = 0
            for i, data in traffic_positions.items():
                t_pos = data["position"]
                t_s = t_pos[0]
                t_lane = t_pos[2]
                
                # DEBUG: Print checking
                # print(f"   - Checking car at s={t_s:.1f}, lane={t_lane}")

                # Collision Check
                is_colliding = False
                for occ_lane, occ_s in occupied_positions:
                    if abs(t_s - occ_s) < 15 and t_lane == occ_lane:
                        is_colliding = True
                        break
                
                if is_colliding:
                    # print("     -> SKIPPED (Collision)")
                    continue

                bg_name = f"Traffic_{i}"
                catalog_model = data.get("catalog_name", "car_white")
                
                self._add_entity(entities, bg_name, "car", model_override=catalog_model)
                init.add_init_action(bg_name, xosc.TeleportAction(xosc.LanePosition(s=t_s, offset=0, lane_id=t_lane, road_id=0)))
                
                bg_speed = random.uniform(70, 90) / 3.6
                init.add_init_action(bg_name, xosc.AbsoluteSpeedAction(bg_speed, step_time))
                added_count += 1
                
            print(f"[COMPILER] Successfully added {added_count} background vehicles.")
                
        except Exception as e:
            print(f"[ERROR] Traffic generation crashed: {e}")
            import traceback
            traceback.print_exc()