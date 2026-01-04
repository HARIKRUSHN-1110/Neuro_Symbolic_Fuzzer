# src/generators/llm_service.py
import os
import re
import logging
from groq import Groq
from src.interfaces.llm_interface import ILlmInterface
from src.core.config import settings

logger = logging.getLogger(__name__)

class GroqLlmService(ILlmInterface):
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set!")
        
    def generate_code(self, user_prompt: str, system_prompt: str = "") -> str:
        logger.info(f"Sending request to Groq ({self.model})...")
        if not system_prompt:
            system_prompt = "You are an expert Python Simulation Engineer."

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=6000,
            )
            return self._clean_output(chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Groq API Error: {e}")
            return ""

    def _clean_output(self, raw_text: str) -> str:
        code_match = re.search(r'```python(.*?)```', raw_text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        return raw_text.strip()

    def save_to_file(self, logic_code: str, filename="generated_scenario.py"):
        # 1. Clean Imports
        lines = logic_code.splitlines()
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def generate", "return", "import xosc", "from scenariogeneration", "story =", "scenario =", "stop =")):
                continue
            cleaned_lines.append(line)
        
        # 2. Indent
        def indent_text(text, spaces=8):
            return "\n".join([" " * spaces + line if line.strip() else line for line in text.splitlines()])
        
        indented_logic = indent_text("\n".join(cleaned_lines), spaces=8)

        # 3. THE DYNAMIC TEMPLATE
        # Note: We keep the Entities (Skins) hardcoded for safety, but Init is now gone.
        full_file_content = f"""
import os
from scenariogeneration import xosc
from src.core.models import ScenarioParameters
from src.core.config import settings

class AI_Generated_Scenario:
    def __init__(self, params: ScenarioParameters):
        self.params = params
        # Dynamic Map Selection
        if self.params.map_name == "fabriksgatan":
            self.road_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/xodr/fabriksgatan.xodr")
            self.scenegraph_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/models/fabriksgatan.osgb")
        else:
            self.road_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/xodr/e6mini.xodr")
            self.scenegraph_file = os.path.join(settings.ESMINI_BIN_PATH, "../resources/models/top_view.osgb")

    def generate(self) -> str:
        # --- AI GENERATED LOGIC STARTS HERE ---
        # The AI must now define:
        # 1. The RoadNetwork (road = ...)
        # 2. The Entities (cars, pedestrians)
        # 3. The Init (positions)
        # 4. The StoryBoard
{indented_logic}
        # --- AI GENERATED LOGIC ENDS HERE ---

        # Boilerplate to save the file
        # Note: The AI MUST define specific variables names: 'scn', 'entities', 'sb', 'road'
        
        # Fallback if AI forgot to define 'scn' but defined the parts
        if 'scn' not in locals():
            scn = xosc.Scenario("AI_Scenario", "GenAI", xosc.ParameterDeclarations(), entities=entities, storyboard=sb, roadnetwork=road, catalog=xosc.Catalog())
        
        # We rely on the AI having defined 'init' above
        sb = xosc.StoryBoard(init, stop_trigger)
        
        if 'ego_man' in locals():
            sb.add_maneuver(ego_man, "Ego")
        if 'target_man' in locals():
            sb.add_maneuver(target_man, "Target")

        scn = xosc.Scenario("AI_Scenario", "GenAI", xosc.ParameterDeclarations(), entities=entities, storyboard=sb, roadnetwork=road, catalog=xosc.Catalog())
        
        filename = "ai_scenario.xosc"
        full_path = os.path.join(settings.OUTPUT_DIR, filename)
        scn.write_xml(full_path)
        return full_path
"""
        output_path = os.path.join("src", "generators", filename)
        with open(output_path, "w") as f:
            f.write(full_file_content)
        logger.info(f"Code saved to {output_path}")
        return output_path