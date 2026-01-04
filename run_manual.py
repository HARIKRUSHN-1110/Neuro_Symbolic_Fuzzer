# run_manual.py
# this file is only for manual testing and is not part of the active pipeline. It is kept for reference.
import sys
import os
import subprocess
import re
from scenariogeneration import xosc

from src.generators.llm_service import GroqLlmService 


# CONFIGURATION 

ESMINI_BIN = r"C:\tools\esmini-demo\bin\esmini.exe" 
ESMINI_RESOURCES = r"C:\tools\esmini-demo\resources"
OUTPUT_FILE = "hybrid_scenario.xosc"

class LogicLibrary:
    """
    The collection of verified maneuvers.
    The LLM selects which ones to use and with what.
    """
    @staticmethod
    def add_cut_in(sb, actor, lane, start, duration):
        man = xosc.Maneuver(f"{actor}_CutIn")
        evt = xosc.Event(f"{actor}_LaneChange", xosc.Priority.override)
        action = xosc.AbsoluteLaneChangeAction(lane, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, duration))
        trigger = xosc.ValueTrigger(f"{actor}_TimeTrig", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(start, xosc.Rule.greaterThan))
        evt.add_action("ChangeLane", action)
        evt.add_trigger(trigger)
        man.add_event(evt)
        sb.add_maneuver(man, actor)

    @staticmethod
    def add_brake(sb, actor, trigger_entity, dist, stop_speed):
        man = xosc.Maneuver(f"{actor}_AutoBrake")
        evt = xosc.Event(f"{actor}_BrakeEvent", xosc.Priority.override)
        action = xosc.AbsoluteSpeedAction(stop_speed, xosc.TransitionDynamics(xosc.DynamicsShapes.linear, xosc.DynamicsDimension.time, 3.0))
        cond = xosc.RelativeDistanceCondition(dist, xosc.Rule.lessThan, entity=trigger_entity, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
        trig = xosc.EntityTrigger(f"{actor}_DistTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor)
        evt.add_action("Brake", action)
        evt.add_trigger(trig)
        man.add_event(evt)
        sb.add_maneuver(man, actor)

    @staticmethod
    def add_overtake(sb, actor, target_lane, trigger_entity, dist):
        man = xosc.Maneuver(f"{actor}_AutoOvertake")
        evt = xosc.Event(f"{actor}_PassEvent", xosc.Priority.override)
        action = xosc.AbsoluteLaneChangeAction(target_lane, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, 2.0))
        cond = xosc.RelativeDistanceCondition(dist, xosc.Rule.lessThan, entity=trigger_entity, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
        time_cond = xosc.SimulationTimeCondition(8.0, xosc.Rule.greaterThan)
        trig_dist = xosc.EntityTrigger(f"{actor}_ProxTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor)
        trig_time = xosc.ValueTrigger("TimeGuard", 0, xosc.ConditionEdge.none, time_cond)
        evt.add_action("Pass", action)
        evt.add_trigger(trig_dist)
        evt.add_trigger(trig_time)
        man.add_event(evt)
        sb.add_maneuver(man, actor)

def get_parameters_from_llm(user_input):
    """
    Asks the LLM to categorize the user's intent.
    Returns a DICTIONARY of safe numbers, not code.
    """
    llm = GroqLlmService()
    
    prompt = f"""
    Analyze the user's request for an autonomous driving scenario.
    User Request: "{user_input}"
    
    Determine the "Aggressiveness" level.
    1. AGGRESSIVE (Dangerous, close calls, hard braking)
    2. NORMAL (Standard driving)
    3. CAUTIOUS (Safe distances, slow maneuvers)
    
    Reply with ONE WORD ONLY: AGGRESSIVE, NORMAL, or CAUTIOUS.
    """
    
    print("Analyzing Intent...")
    try:
        response = llm.generate_code(user_prompt=prompt).upper()
        # Clean response (remove punctuation/extra words)
        if "AGGRESSIVE" in response: mode = "AGGRESSIVE"
        elif "CAUTIOUS" in response: mode = "CAUTIOUS"
        else: mode = "NORMAL"
        
        print(f"[AI]: Detected Mode -> {mode}")
        return mode
        
    except Exception as e:
        print(f"[AI]: Error ({e}). Defaulting to NORMAL.")
        return "NORMAL"

def get_physics_profile(mode):
    """
    Maps the simple LLM keyword to complex, crash-proof physics numbers.
    """
    if mode == "AGGRESSIVE":
        return {
            "cut_in_dist": 10,  # Very close
            "cut_in_dur": 1.0,  # Jerky lane change
            "brake_dist": 15,   # Late braking
            "overtake_dist": 10 # Tailgating before pass
        }
    elif mode == "CAUTIOUS":
        return {
            "cut_in_dist": 60,  # Far away
            "cut_in_dur": 4.0,  # Slow lane change
            "brake_dist": 50,   # Early braking
            "overtake_dist": 40 # Safe passing distance
        }
    else: # NORMAL
        return {
            "cut_in_dist": 25,
            "cut_in_dur": 2.5,
            "brake_dist": 30,
            "overtake_dist": 25
        }

def main():
    #  GET USER INPUT
    print("\n--- HYBRID SCENARIO GENERATOR ---")
    user_input = "I want a crazy dangerous scenario where the guy cuts me off instantly! but after emergency brake i just want to countinue at earliest same speed"
    print(f"USER: {user_input}")

    #  GET CONFIG 
    mode = get_parameters_from_llm(user_input)
    params = get_physics_profile(mode)

    print("Generating Building Scenario")
    
    road_file = os.path.join(ESMINI_RESOURCES, "xodr/e6mini.xodr")
    scene_graph = os.path.join(ESMINI_RESOURCES, "models/top_view.osgb")
    road = xosc.RoadNetwork(roadfile=road_file, scenegraph=scene_graph)

    entities = xosc.Entities()
    
    # Setup Actors
    ego = xosc.Vehicle("Ego", xosc.VehicleCategory.car, xosc.BoundingBox(2,5,1.8,2,0,0), xosc.Axle(0.5,0.8,1.68,2.9,0.35), xosc.Axle(0,0.8,1.68,0,0.35), 69, 10, 10)
    ego.add_property("model_id", "0")
    entities.add_scenario_object("Ego", ego)

    target = xosc.Vehicle("Target", xosc.VehicleCategory.car, xosc.BoundingBox(2,5,1.8,2,0,0), xosc.Axle(0.5,0.8,1.68,2.9,0.35), xosc.Axle(0,0.8,1.68,0,0.35), 69, 10, 10)
    target.add_property("model_id", "1")
    target.add_property("osgb", "../resources/models/car_red.osgb")
    entities.add_scenario_object("Target", target)

    init = xosc.Init()
    # Ego (Fast)
    init.add_init_action("Ego", xosc.TeleportAction(xosc.LanePosition(0, 0, -3, 0)))
    init.add_init_action("Ego", xosc.AbsoluteSpeedAction(100/3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))
    # Target (Slow, Ahead)
    init.add_init_action("Target", xosc.TeleportAction(xosc.LanePosition(60, 0, -2, 0)))
    init.add_init_action("Target", xosc.AbsoluteSpeedAction(60/3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))

    sb = xosc.StoryBoard(init, xosc.ValueTrigger("stop",0,xosc.ConditionEdge.none,xosc.SimulationTimeCondition(30, xosc.Rule.greaterThan), "stop"))

    #LOGIC WITH AI PARAMETERS 
    
    #  Target Cuts In (Using AI Duration)
    LogicLibrary.add_cut_in(sb, "Target", lane=-3, start=2.0, duration=params["cut_in_dur"])
    
    # Ego Brakes (Using AI Distance)
    LogicLibrary.add_brake(sb, "Ego", trigger_entity="Target", dist=params["brake_dist"], stop_speed=0)
    
    # Ego Overtakes (Using AI Distance)
    LogicLibrary.add_overtake(sb, "Ego", target_lane=-2, trigger_entity="Target", dist=params["overtake_dist"])

    scn = xosc.Scenario("HybridSim", "AI_Configured", xosc.ParameterDeclarations(), entities=entities, storyboard=sb, roadnetwork=road, catalog=xosc.Catalog())
    scn.write_xml(OUTPUT_FILE)
    
    print(f"Generated: {OUTPUT_FILE}")
    
    if os.path.exists(ESMINI_BIN):
        subprocess.run([ESMINI_BIN, "--window", "60", "60", "800", "400", "--osc", OUTPUT_FILE, "--follow_object", "0"])
    else:
        print("Esmini not found.")

if __name__ == "__main__":
    main()