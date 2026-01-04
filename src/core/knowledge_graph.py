# src/core/knowledge_graph.py
import os
import logging
# Optional: import vector DB libraries if you have them, otherwise we simulate the RAG logic
# from langchain_chroma import Chroma 

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    The Single Source of Truth.
    Maps User Intent -> Physical Constraints & Rules.
    """
    
    def __init__(self, db_dir="chroma_db"):
        # PHYSICAL ASSETS (The "World")
        self.static_maps = {
            "city": {
                "file": "fabriksgatan_traffic_lights.xodr", 
                "model_file": "fabriksgatan.osgb",
                "lanes": [-1], # Center lane
                "speed_limit": 50
            },
            "highway": {
                "file": "e6mini.xodr",
                "model_file": "top_view.osgb", 
                "lanes": [-2, -3], # -2=Left(Fast), -3=Right(Slow)
                "speed_limit": 110
            }
        }

        # LOGIC RULES (The "Laws of Physics")
        # In a full RAG system, these would come from vector DB.
        self.maneuver_rules = {
            "cut_in": """
                - AGGRESSOR must be FASTER than VICTIM (delta_v > 20 km/h).
                - AGGRESSOR must start BEHIND VICTIM (s_diff = -15m) to perform an overtake-cut-in.
                - Trigger: Use 'trigger_time' calculated by distance/speed, or 'trigger_dist' < 15m.
            """,
            "brake_check": """
                - AGGRESSOR overtakes VICTIM first.
                - AGGRESSOR cuts in front (distance < 10m).
                - AGGRESSOR brakes hard (target_speed = 0 or much lower than Victim).
            """,
            "overtake": """
                - PASSING_CAR must be in a faster lane (e.g., lane -2).
                - SLOW_CAR must be in a slower lane (e.g., lane -3).
                - PASSING_CAR speed > SLOW_CAR speed + 15 km/h.
            """
        }

    def get_map_context(self, request_text):
        """
        Determines the best map based on keywords.
        """
        req = request_text.lower()
        if "city" in req or "light" in req or "pedestrian" in req:
            return self.static_maps["city"]
        return self.static_maps["highway"] # Default to highway for safety

    def get_llm_system_prompt_context(self, user_requirement):
        """
        Retrieves the RELEVANT knowledge for the specific request.
        This is the RAG step.
        """
        # Determine Map
        map_data = self.get_map_context(user_requirement)
        
        # Determine Relevant Maneuver Rules
        req = user_requirement.lower()
        active_rules = []
        if "cut" in req: active_rules.append(self.maneuver_rules["cut_in"])
        if "brake" in req: active_rules.append(self.maneuver_rules["brake_check"])
        if "pass" in req or "overtake" in req: active_rules.append(self.maneuver_rules["overtake"])
        
        rules_text = "\n".join(active_rules) if active_rules else "Standard Driving Rules apply."

        return f"""
        ### KNOWLEDGE GRAPH CONTEXT ###
        
        1. **ACTIVE MAP**: "{map_data['file']}"
           - Valid Lanes: {map_data['lanes']}
           - Speed Limit: {map_data['speed_limit']} km/h
           
        2. **PHYSICS & LOGIC RULES (Strict Adherence Required)**:
           {rules_text}
           
        3. **ASSETS**:
           - Ego Vehicle: "car_white" (Catalog ID: 0)
           - Target/Traffic: "car_red", "truck_yellow"
        """