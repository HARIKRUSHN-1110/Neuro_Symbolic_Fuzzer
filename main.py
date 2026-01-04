import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

from src.generators.llm_service import GroqLlmService
from src.generators.scenario_compiler import ScenarioCompiler
from src.core.knowledge_graph import KnowledgeGraph
from src.core.config import settings

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

# Initialize App & Services
app = FastAPI(title="Neuro-Symbolic Scenario Fuzzer API")

# Mount Static Folder for UI
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global Service Instances
llm_service = GroqLlmService()
compiler = ScenarioCompiler()
kg = KnowledgeGraph(db_dir="chroma_db")

# --- Request Model ---
class ScenarioRequest(BaseModel):
    prompt: str
    traffic_density: Optional[str] = "low"

# --- Helper Functions ---
def extract_json_from_text(text):
    """ Robust Stack-Based JSON Extractor (Same as run_aiscenario.py) """
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

def validate_blueprint(blueprint):
    """ 
    Safety check for the API. 
    Ensures the LLM didn't forget required fields like 'type'.
    """
    if "actors" not in blueprint: blueprint["actors"] = []
    if "actions" not in blueprint: blueprint["actions"] = []
    
    valid_actions = []
    for action in blueprint["actions"]:
        if "type" in action:
            valid_actions.append(action)
        else:
            logger.warning(f"Skipping malformed action (missing 'type'): {action}")
            
    blueprint["actions"] = valid_actions
    return blueprint

# --- API Endpoints ---

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/generate-scenario")
async def generate_scenario(request: ScenarioRequest):
    user_requirement = request.prompt
    logger.info(f"Received Request: {user_requirement}")

    try:
        # 1. KNOWLEDGE GRAPH RETRIEVAL (Logic from run_aiscenario.py)
        # Determine Map Context
        if "highway:" in user_requirement.lower(): map_key = "highway"
        elif "city:" in user_requirement.lower(): map_key = "city"
        else:
            selected_map_data = kg.get_map_context(user_requirement)
            map_key = "city" if selected_map_data["speed_limit"] == 50 else "highway"

        # Rules from KG
        context_prompt = kg.get_llm_system_prompt_context(user_requirement)
        
        # PROMPT CONSTRUCTION
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
        3. Set "traffic_density" to "{request.traffic_density}".
        4. Output ONLY valid JSON matching the schema below.
        
        ### SCHEMA ###
        {schema_template}
        """

        #LLM GENERATION (With Retry Logic)
        blueprint = None
        for attempt in range(3):
            raw_response = llm_service.generate_code(user_prompt=full_prompt)
            json_str = extract_json_from_text(raw_response)
            
            if json_str:
                try:
                    blueprint = json.loads(json_str)
                    blueprint["map_key"] = map_key # Enforce map consistency
                    
                    # API Specific: Validate to prevent server crash
                    blueprint = validate_blueprint(blueprint)
                    break
                except json.JSONDecodeError:
                    continue
        
        if not blueprint:
            raise HTTPException(status_code=500, detail="LLM failed to generate valid JSON scenario.")

        # COMPILATION
        # Generate a unique filename for the user
        output_filename = f"scenario_{os.urandom(4).hex()}.xosc"
        
        # Ensure output directory exists
        if not os.path.exists("outputs"):
            os.makedirs("outputs")
            
        # Compile
        xosc_path = compiler.compile(blueprint, output_name=output_filename)

        if not os.path.exists(xosc_path):
            raise HTTPException(status_code=500, detail="Compiler failed to write XOSC file.")

        # RETURN FILE (Do not run Esmini here, just download)
        return FileResponse(
            path=xosc_path, 
            filename=output_filename, 
            media_type='application/xml'
        )

    except Exception as e:
        logger.error(f"Pipeline Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Runs the server locally on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)