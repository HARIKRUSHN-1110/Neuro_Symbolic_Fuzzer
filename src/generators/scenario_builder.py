# src/generators/scenario_builder.py
import os
import logging
from scenariogeneration import xosc #type: ignore
from src.core.models import ScenarioParameters
from src.core.config import settings

logger = logging.getLogger(__name__)

class CutInGenerator:
    def __init__(self, params: ScenarioParameters):
        self.params = params
        self.road_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/xodr/e6mini.xodr")
        self.scenegraph_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/models/top_view.osgb")

    def generate(self) -> str:
        # 1. Road
        road = xosc.RoadNetwork(roadfile=self.road_file, scenegraph=self.scenegraph_file)

        # 2. Entities (Low Z-height to touch the ground)
        bb = xosc.BoundingBox(2.0, 5.0, 1.8, 2.0, 0.0, 0.0)
        # Wheels at 0.35m height with 0.35m radius = Touching ground perfectly
        fa = xosc.Axle(0.5, 0.8, 1.68, 2.9, 0.35) 
        ra = xosc.Axle(0.0, 0.8, 1.68, 0.0, 0.35)

        ego_veh = xosc.Vehicle("Ego", xosc.VehicleCategory.car, bb, fa, ra, 69, 10, 10)
        target_veh = xosc.Vehicle("Target", xosc.VehicleCategory.car, bb, fa, ra, 69, 10, 10)

        entities = xosc.Entities()
        entities.add_scenario_object("Ego", ego_veh)
        entities.add_scenario_object("Target", target_veh)

        # 3. Init
        init = xosc.Init()

        # --- THE FIX: road_id=0 (Not 1) ---
        
        # Ego: Lane -2 (Right Lane)
        init.add_init_action("Ego", xosc.TeleportAction(xosc.LanePosition(s=50, offset=0, lane_id=-3, road_id=0))) 
        init.add_init_action("Ego", xosc.AbsoluteSpeedAction(self.params.ego_speed / 3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))

        # Target: Lane -2 (Left Lane)
        target_start_s = 30 + self.params.cut_in_distance
        init.add_init_action("Target", xosc.TeleportAction(xosc.LanePosition(s=target_start_s, offset=0, lane_id=-2, road_id=0)))
        init.add_init_action("Target", xosc.AbsoluteSpeedAction(self.params.target_speed / 3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0)))

        # 4. Maneuvers
        
        # Ego: Just Drive
        ego_man = xosc.Maneuver("EgoKeepSpeed")
        ego_event = xosc.Event("EgoDrive", xosc.Priority.override)
        ego_event.add_action("Drive", xosc.AbsoluteSpeedAction(self.params.ego_speed / 3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 1.0)))
        ego_event.add_trigger(xosc.ValueTrigger("EgoStart", 0, xosc.ConditionEdge.none, xosc.SimulationTimeCondition(0, xosc.Rule.greaterThan)))
        ego_man.add_event(ego_event)

        # Target: Cut In to Lane -2
        target_man = xosc.Maneuver("TargetCutIn")
        
        # Step 1: Maintain Speed
        target_drive = xosc.Event("TargetDrive", xosc.Priority.override)
        target_drive.add_action("Drive", xosc.AbsoluteSpeedAction(self.params.target_speed / 3.6, xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 1.0)))
        target_drive.add_trigger(xosc.ValueTrigger("TargetStart", 0, xosc.ConditionEdge.none, xosc.SimulationTimeCondition(0, xosc.Rule.greaterThan)))
        
        # Step 2: Cut In
        cut_in_event = xosc.Event("CutIn", xosc.Priority.override)
        # Target moves to Lane -2 (Ego's lane)
        cut_in_event.add_action("LaneChange", xosc.AbsoluteLaneChangeAction(-3, xosc.TransitionDynamics(xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, 3.0)))
        # Trigger after 2 seconds
        cut_in_event.add_trigger(xosc.ValueTrigger("CutInStart", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(2.0, xosc.Rule.greaterThan)))
        
        target_man.add_event(target_drive)
        target_man.add_event(cut_in_event)

        # 5. StoryBoard
        stop_trigger = xosc.ValueTrigger("StopSim", 0, xosc.ConditionEdge.rising, xosc.SimulationTimeCondition(10, xosc.Rule.greaterThan), "stop")
        
        sb = xosc.StoryBoard(init, stop_trigger)
        sb.add_maneuver(ego_man, "Ego")
        sb.add_maneuver(target_man, "Target")

        # 6. Scenario
        scn = xosc.Scenario(
            self.params.scenario_name,
            "NeuroSymbolicAI",
            xosc.ParameterDeclarations(),
            entities=entities,
            storyboard=sb,
            roadnetwork=road,
            catalog=xosc.Catalog()
        )

        filename = f"{self.params.scenario_name}.xosc"
        full_path = os.path.join(settings.OUTPUT_DIR, filename)
        scn.write_xml(full_path)
        logger.info(f"Generated XOSC file at: {full_path}")
        return full_path