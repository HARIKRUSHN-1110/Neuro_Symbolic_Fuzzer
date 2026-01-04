# master_simulation.py
# this file was only for reference to LLM promt, it is not used to generate the scenario.
import os
import subprocess
import sys
from scenariogeneration import xosc

ESMINI_BIN = r"C:\tools\esmini-demo\bin\esmini.exe" 
# UPDATE THIS TO WHERE YOUR RESOURCES ARE
ESMINI_RESOURCES = r"C:\tools\esmini-demo\resources"

output_file = "master_scenario.xosc"

class CutIn:
    def __init__(self, target_lane, start_time, duration=2.0):
        self.target_lane = target_lane
        self.start_time = start_time
        self.duration = duration

    def add_to(self, storyboard, actor):
        man = xosc.Maneuver(f"{actor}_CutIn")
        evt = xosc.Event(f"{actor}_LaneChange", xosc.Priority.override)
        action = xosc.AbsoluteLaneChangeAction(self.target_lane, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, self.duration))
        trigger = xosc.ValueTrigger(f"{actor}_TimeTrig", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(self.start_time, xosc.Rule.greaterThan))
        
        evt.add_action("ChangeLane", action)
        evt.add_trigger(trigger)
        man.add_event(evt)
        storyboard.add_maneuver(man, actor)

class ReactiveBrake:
    def __init__(self, trigger_dist, stop_speed=0):
        self.trigger_dist = trigger_dist
        self.stop_speed = stop_speed

    def add_to(self, storyboard, actor, trigger_entity):
        man = xosc.Maneuver(f"{actor}_AutoBrake")
        evt = xosc.Event(f"{actor}_BrakeEvent", xosc.Priority.override)
        
        # Action: Brake Hard
        action = xosc.AbsoluteSpeedAction(self.stop_speed, xosc.TransitionDynamics(xosc.DynamicsShapes.linear, xosc.DynamicsDimension.time, 3.0))
        
        # Trigger: Distance < X
        cond = xosc.RelativeDistanceCondition(self.trigger_dist, xosc.Rule.lessThan, entity=trigger_entity, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
        trig = xosc.EntityTrigger(f"{actor}_DistTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor)
        
        evt.add_action("Brake", action)
        evt.add_trigger(trig)
        man.add_event(evt)
        storyboard.add_maneuver(man, actor)

class ReactiveOvertake:
    def __init__(self, target_lane, trigger_dist):
        self.target_lane = target_lane
        self.trigger_dist = trigger_dist

    def add_to(self, storyboard, actor, trigger_entity):
        man = xosc.Maneuver(f"{actor}_AutoOvertake")
        evt = xosc.Event(f"{actor}_PassEvent", xosc.Priority.override)
        
        # Action: Swerve to pass
        action = xosc.AbsoluteLaneChangeAction(self.target_lane, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, 2.0))
        
        # Trigger: Distance < X (Closing in)
        cond = xosc.RelativeDistanceCondition(self.trigger_dist, xosc.Rule.lessThan, entity=trigger_entity, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
        # Time guard: Don't do this at the very start, wait 8 seconds
        time_cond = xosc.SimulationTimeCondition(8.0, xosc.Rule.greaterThan)
        
        trig_dist = xosc.EntityTrigger(f"{actor}_ProxTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor)
        trig_time = xosc.ValueTrigger("TimeGuard", 0, xosc.ConditionEdge.none, time_cond)

        evt.add_action("Pass", action)
        evt.add_trigger(trig_dist)
        evt.add_trigger(trig_time)
        man.add_event(evt)
        storyboard.add_maneuver(man, actor)

class ResumeSpeed:
    def __init__(self, target_speed, safe_dist):
        self.target_speed = target_speed / 3.6
        self.safe_dist = safe_dist

    def add_to(self, storyboard, actor, trigger_entity):
        man = xosc.Maneuver(f"{actor}_Resume")
        evt = xosc.Event(f"{actor}_AccelEvent", xosc.Priority.override)
        
        action = xosc.AbsoluteSpeedAction(self.target_speed, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, 4.0))
        
        # Trigger: Distance > X (Road Clear)
        cond = xosc.RelativeDistanceCondition(self.safe_dist, xosc.Rule.greaterThan, entity=trigger_entity, dist_type=xosc.RelativeDistanceType.longitudinal, coordinate_system=xosc.CoordinateSystem.entity)
        time_cond = xosc.SimulationTimeCondition(5.0, xosc.Rule.greaterThan)
        
        trig_dist = xosc.EntityTrigger(f"{actor}_ClearTrig", 0, xosc.ConditionEdge.rising, cond, triggerentity=actor)
        trig_time = xosc.ValueTrigger("TimeGuard", 0, xosc.ConditionEdge.none, time_cond)

        evt.add_action("Accel", action)
        evt.add_trigger(trig_dist)
        evt.add_trigger(trig_time)
        man.add_event(evt)
        storyboard.add_maneuver(man, actor)

def generate_scenario():
    print("--- Building Master Scenario ---")
    
    # ROAD
    road_file = os.path.join(ESMINI_RESOURCES, "xodr/e6mini.xodr")
    scene_graph = os.path.join(ESMINI_RESOURCES, "models/top_view.osgb")
    road = xosc.RoadNetwork(roadfile=road_file, scenegraph=scene_graph)

    # ENTITIES
    entities = xosc.Entities()
    
    # EGO (Fast, Right Lane)
    ego = xosc.Vehicle("Ego", xosc.VehicleCategory.car, xosc.BoundingBox(2,5,1.8,2,0,0), xosc.Axle(0.5,0.8,1.68,2.9,0.35), xosc.Axle(0,0.8,1.68,0,0.35), 69, 10, 10)
    ego.add_property("model_id", "0")
    ego.add_property("osgb", "../resources/models/car_white.osgb")
    entities.add_scenario_object("Ego", ego)

    # TARGET (Slow, Left Lane -> Will Cut In)
    target = xosc.Vehicle("Target", xosc.VehicleCategory.car, xosc.BoundingBox(2,5,1.8,2,0,0), xosc.Axle(0.5,0.8,1.68,2.9,0.35), xosc.Axle(0,0.8,1.68,0,0.35), 69, 10, 10)
    target.add_property("model_id", "1")
    target.add_property("osgb", "../resources/models/car_red.osgb")
    entities.add_scenario_object("Target", target)

    # INIT
    init = xosc.Init()
    # Ego at 0m, 100km/h, Lane -3
    init.add_init_action("Ego", xosc.TeleportAction(xosc.LanePosition(0, 0, -3, 0)))
    init.add_init_action("Ego", xosc.AbsoluteSpeedAction(100/3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))
    
    # Target at 50m, 60km/h, Lane -2
    init.add_init_action("Target", xosc.TeleportAction(xosc.LanePosition(50, 0, -2, 0)))
    init.add_init_action("Target", xosc.AbsoluteSpeedAction(60/3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))

    # STORYBOARD
    sb = xosc.StoryBoard(init, xosc.ValueTrigger("stop",0,xosc.ConditionEdge.none,xosc.SimulationTimeCondition(30, xosc.Rule.greaterThan), "stop"))
    
    # 1. Target Cuts In (Aggressive)
    CutIn(target_lane=-3, start_time=2.0).add_to(sb, "Target")
    
    # 2. Ego Brakes if Target gets too close (< 25m)
    ReactiveBrake(trigger_dist=25, stop_speed=0).add_to(sb, "Ego", trigger_entity="Target")

    # 3. Ego Resumes Speed if Target gets far away (> 40m)
    ResumeSpeed(target_speed=100, safe_dist=40).add_to(sb, "Ego", trigger_entity="Target")
    
    # 4. Ego Overtakes if it catches up again (< 20m)
    ReactiveOvertake(target_lane=-2, trigger_dist=20).add_to(sb, "Ego", trigger_entity="Target")

    scn = xosc.Scenario("MasterSim", "FinalAttempt", xosc.ParameterDeclarations(), entities=entities, storyboard=sb, roadnetwork=road, catalog=xosc.Catalog())
    scn.write_xml(output_file)
    print(f"Scenario generated: {output_file}")
    return output_file

def run_esmini(osc_file):
    if not os.path.exists(ESMINI_BIN):
        print(f"ERROR: Cannot find esmini at {ESMINI_BIN}")
        return
    
    print("Launching Esmini...")
    cmd = [
        ESMINI_BIN,
        "--window", "60", "60", "800", "400",
        "--osc", osc_file,
        "--follow_object", "0"
    ]
    subprocess.run(cmd)