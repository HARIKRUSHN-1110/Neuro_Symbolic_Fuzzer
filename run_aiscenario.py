# run_aiscenario.py
# this file is for development & debugging. It generates the scenario and immediately runs it in Esmini machine.
import sys
import os
import json
import logging
import asyncio
import subprocess
import re

from src.generators.llm_service import GroqLlmService 
from src.generators.scenario_compiler import ScenarioCompiler
from src.core.knowledge_graph import KnowledgeGraph
from src.core.config import settings

logging.basicConfig(level=logging.INFO)

def extract_json_from_text(text):
    """ Robust JSON Extractor (Stack Method) """
    try:
        start_index = text.find('{')
        if start_index == -1: return None
        brace_count = 0
        in_string = False
        escape = False
        for i, char in enumerate(text[start_index:], start=start_index):
            if char == '"' and not escape: in_string = not in_string
            elif char == '\\' and in_string: escape = not escape; continue
            elif not in_string:
                if char == '{': brace_count += 1
                elif char == '}': 
                    brace_count -= 1
                    if brace_count == 0: return text[start_index : i+1]
            if escape: escape = False
        return None
    except Exception: return None

async def main():
    # INIT
    llm = GroqLlmService()
    compiler = ScenarioCompiler()
    kg = KnowledgeGraph(db_dir="chroma_db") 
    
    # USER REQUEST
    #user_requirement = "highway: target car cuts in suddenly before ego and ego must apply break to avoid collisions and then ego continues to speed up again at 120 km/h."
    user_requirement = "highway: Both are on the 'same lane' and Target car must be 'ahead of the ego' and faster than ego. Target car first brakes on the same lane and after reacting to the braking that ego also must apply emergency brake and stop before minimum safe distance, to avoid collision."
    print(f"\n--- USER GOAL: {user_requirement} ---")

    # KNOWLEDGE GRAPH RETRIEVAL
    print("Querying Knowledge Graph for map and physics rules...")
    context_prompt = kg.get_llm_system_prompt_context(user_requirement)
    
    # Identify map key for the compiler later
    selected_map_data = kg.get_map_context(user_requirement)
    map_key = "city" if "city" in user_requirement.lower() else "highway"
    
    print(f"Retrieved Context:\n{context_prompt}")

    # PROMPT ENGINEERING
    # feed the KG rules into the prompt so the LLM gets the math right.
    schema_template = """
    {
      "map_key": "highway",
      "traffic_density": "low",
      "actors": [
        {"name": "Ego", "type": "car", "lane": -2, "s": 0, "speed": 100},
        {"name": "Target", "type": "car", "lane": -3, "s": 0, "speed": 130}
      ],
      "actions": [
        { "type": "lane_change", "actor": "Target", "target_lane": -2, "trigger_time": 5.0, "duration": 2.0 },
        { "type": "brake", "actor": "Ego", "target_speed": 60, "trigger_dist": 15, "trigger_entity": "Target" }
      ]
    }
    """

    full_prompt = f"""
    You are an AI Scenario Architect.
    
    ### REQUEST ###
    "{user_requirement}"
    
    ### KNOWLEDGE GRAPH RULES (MUST FOLLOW) ###
    {context_prompt}
    
    ### INSTRUCTIONS ###
    1. Read the "PHYSICS & LOGIC RULES" above carefully.
    2. If the user asks for a Cut-In, ensure the Aggressor is FASTER and starts BEHIND or PARALLEL to the victim.
    3. Output ONLY valid JSON matching the schema below.
    
    ### SCHEMA ###
    {schema_template}
    """

    # GENERATE & COMPILE
    print("\nAI: Designing Scenario based on KG Rules...")
    try:
        raw_response = llm.generate_code(user_prompt=full_prompt)
        json_str = extract_json_from_text(raw_response)
        
        if not json_str:
            print("[ERROR] LLM failed to generate JSON.")
            return

        blueprint = json.loads(json_str)
        
        # Ensure map key matches what KG decided
        blueprint["map_key"] = map_key 
        
        print("\nAI: Blueprint Generated:")
        print(json.dumps(blueprint, indent=2))
        
        print("\nCOMPILER: Building OpenSCENARIO (.xosc)...")
        # The compiler will now use the Official Traffic Logic if traffic_density="high"
        # and standard logic for the specific actors.
        xosc_file = compiler.compile(blueprint)
        print(f"SUCCESS! Scenario saved to: {xosc_file}")
        
        print("\nLaunching Simulation...")
        esmini_bin = settings.ESMINI_BIN_PATH
        if not os.path.exists(esmini_bin):
            print(f"ERROR: Esmini not found at {esmini_bin}")
            return

        cmd = [
            esmini_bin, 
            "--window", "60", "60", "800", "400",
            "--osc", xosc_file, 
            "--follow_object", "Ego",
            "--pause"
        ]
        subprocess.run(cmd)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())