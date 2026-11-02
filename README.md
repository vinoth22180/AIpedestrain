# Accessibility-Aware Dynamic Pedestrian Rerouting System

## Project Objective
This is the **First 10-15% Milestone** (Accessibility-Aware Static Pedestrian Routing) of a broader university research project aimed at building a patent-oriented intelligent pedestrian routing system. This prototype demonstrates that pedestrian paths can be adjusted based on explicit accessibility attributes (stairs, wheelchair accessibility, surface, incline) and user-specific mobility profiles.

## Current Milestone (Prototype)
- Loads real Melbourne pedestrian network geometry.
- Loads OpenStreetMap (OSM) attributes for the same region.
- Evaluates routes using a customizable edge-cost algorithm mapping accessibility penalties to user profiles.
- Profiles: General, Elderly, Pregnant, Mobility-Impaired (Wheelchair).
- Demonstrates altered route recommendations for different profiles on the same origin-destination pair.

## Future Milestones
- Signal-Decay Algorithm implementation
- Predictive congestion mapping
- Pedestrian-count integration & traffic-signal prediction
- Emergency-event and weather prediction
- ESP32 hardware and IoT sensing
- Mobile application frontend

## Setup Instructions

### Dependencies
Python 3 is required. Install the required libraries using:
```bash
python -m venv .venv
# Activate the virtual environment:
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### How to Run
The prototype is bundled with a lightweight Streamlit application for interactive demonstration.

1. Ensure your virtual environment is active.
2. Run the application from the project root:
```bash
streamlit run src/app.py
```
3. The app will open in your browser (usually `http://localhost:8501`). On the first run, it will automatically download the required datasets (Melbourne Pedestrian Network and OSM data) to the `data/` folder.

### Sample Workflow
1. Select the "Source" (e.g., Flinders Street Station).
2. Select the "Destination" (e.g., State Library).
3. Select the "User Profile" (e.g., General, then switch to Mobility-Impaired).
4. Observe the changing Route Length, Route Cost, and the path on the interactive map as the algorithm reroutes to avoid stairs or inaccessible paths for the Mobility-Impaired profile.
