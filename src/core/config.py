# src/core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict #type: ignore

class Settings(BaseSettings):
    # App Config
    PROJECT_NAME: str = "Neuro-Symbolic ADAS Fuzzer"
    VERSION: str = "1.0.0"

    # Paths (Update these to where you actually extract Esmini)
    
    ESMINI_BIN_PATH: str = "C:/tools/esmini-demo/bin/esmini.exe" # Or ./bin/esmini on Linux
    OUTPUT_DIR: str = os.path.join(os.getcwd(), "data", "scenarios")
    LOG_DIR: str = os.path.join(os.getcwd(), "data", "logs")

    class Config:
        env_file = ".env"

# Singleton instance
settings = Settings()