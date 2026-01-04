# AutoScenario AI: Automated Validation for Autonomous Driving

**Deployment URL:** [https://neurosymbolicfuzzer.onrender.com](https://neurosymbolicfuzzer.onrender.com)

## Project Overview

**AutoScenario AI** is a Neuro-Symbolic fuzzing application designed to accelerate the validation process for Autonomous Advanced Driving Systems (ADAS).

Creating standard OpenSCENARIO (.xosc) files for simulation is traditionally a manual, error-prone, and time-intensive process requiring deep knowledge of XML schemas and coordinate systems. This project solves that problem by bridging the gap between natural language requirements and rigid engineering standards.

By leveraging a **Neuro-Symbolic Architecture**, the system combines the semantic understanding of Large Language Models (LLMs) with the deterministic safety of rule-based compilation and Retrieval-Augmented Generation(RAG). This ensures that generated scenarios are not only creative and diverse but also physically valid and executable in standard simulators.

## Key Features

* **Natural Language Interface:** Converts complex textual descriptions (e.g., "Aggressive cut-in on a highway with heavy traffic") into machine-readable code.
* **Neuro-Symbolic Compiler:** Uses a hybrid approach where an LLM drafts the scenario blueprint and a deterministic Python compiler enforces physics constraints (speed, distance, timing).
* **Knowledge Graph Integration (RAG):** Retrieves domain-specific rules (ODD - Operational Design Domains) from a vector database to ensure scenarios adhere to safety standards.
* **Standard Compliance:** Outputs valid OpenSCENARIO 1.0 XML files compatible with major automotive simulators.
* **Zero-Footprint Simulation:** Architected for client-side execution, allowing the simulation to run locally on the user's machine without requiring expensive server-side GPU resources.

## System Architecture & Technologies

This application follows a modern microservices-inspired architecture, separating the generation logic from the simulation execution.

### 1. Frontend (User Interface)
* **Technologies:** HTML5, CSS3, Vanilla JavaScript.
* **Role:** Handles user input, traffic parameter configuration, and asynchronous communication with the backend API.
* **Design:** Responsive layout with a professional aesthetic, featuring real-time status updates and video previews.

### 2. Backend (Core Logic)
* **Framework:** FastAPI (Python) for high-performance, asynchronous API handling.
* **AI Logic:** * **LLM Service:** Groq API (Llama-3-70b) for rapid blueprint generation.
    * **RAG Pipeline:** ChromaDB for retrieving context-aware engineering rules.
* **Compiler:** Custom Python-based `ScenarioCompiler` that translates abstract blueprints into rigorous XML structures using the `scenariogeneration` library.

### 3. Deployment & Infrastructure
* **Platform:** Render (Web Service).
* **CI/CD:** Automated deployment pipeline connected to GitHub.
* **Environment Management:** Docker-compatible runtime with optimized dependency management for CPU-only environments (utilizing lightweight PyTorch builds).

## How to Run the Generated Scenarios

**Important Note:** The web application generates the scenario file (`.xosc`), but it does **not** run the simulation in the browser. You must run the simulation locally on your own computer.

This architecture is intentional: high-fidelity autonomous driving simulations require GPU acceleration, which is best handled by your local hardware rather than a remote web server.

### Prerequisites (One-Time Setup)

You need a simulator that supports the OpenSCENARIO standard. We use **Esmini** because it is lightweight, open-source, and widely used in the industry.

1.  **Download Esmini:** * Go to the official releases page: [https://github.com/esmini/esmini/releases](https://github.com/esmini/esmini/releases)
    * Download the zip file for your OS (e.g., `esmini-bin_Windows_x64.zip` or Linux equivalent).
2.  **Install:**
    * Unzip the downloaded folder to a location you can easily access (e.g., `C:\tools\esmini` or `~/tools/esmini`).
    * You do not need to run an installer; just extracting the folder is enough.

### Execution Steps

1.  **Generate a Scenario:**  Navigate to [https://neurosymbolicfuzzer.onrender.com](https://neurosymbolicfuzzer.onrender.com).
    * Enter your prompt (e.g., "highway: ego overtakes a slow truck") and click **Generate**.
    * A file named `ai_scenario.xosc` will download to your computer.

2.  **Move the File:** * Move `ai_scenario.xosc` into the `bin` folder inside your unzipped Esmini directory (where `esmini.exe` is located).

3.  **Run the Simulation:**
    * Open your Command Prompt (Windows) or Terminal (Linux/Mac).
    * Navigate to the Esmini `bin` folder:
      ```powershell
      cd C:\tools\esmini\bin
      ```
    * Run the simulation command:
      ```powershell
      .\esmini.exe --window 60 60 800 600 --osc ai_scenario.xosc
      ```
      *(Note: On Linux/Mac, use `./esmini` instead of `.\esmini.exe`)*

4.  **Visualize:**
    * A window will pop up showing the scenario you just generated.
    * The simulation runs automatically based on the physics defined by the AI.

---

**Author:** Harikrushn Dudhat
