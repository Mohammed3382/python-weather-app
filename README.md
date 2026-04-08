# Skyline Forecast

Skyline Forecast is a Streamlit weather application focused on practical day-to-day decisions instead of just raw forecast data. It combines current conditions, multi-day forecasts, clothing guidance, activity recommendations, live map layers, nearby place suggestions, comparison tools, and export workflows in a single interface.

The app is designed for fast interactive use. It stores lightweight local state, works without API keys, and builds CSV, Excel, PDF, and trip-planner PDF exports directly inside the project.

## Why I Built This

I built this project as a student with a practical goal in mind: automate useful weather-based decisions instead of creating a basic forecast app that only shows raw data.

At first, I considered building everything more manually with only small step-by-step help from ChatGPT. That approach is not wrong, but for this project it would likely have led to a much more limited result and a weaker final product.

I decided it made more sense to fully lean into AI-assisted development and treat that as part of the skill I am trying to show. Instead of forcing a mediocre web app just to say it was built more manually, I used AI to move faster, iterate more, and build something more complete.

For me, this project is not only about the final weather app. It is also about showing that I can use AI properly: giving clear direction, refining ideas, reviewing outputs, fixing bugs, and turning assistance into a working product.

## What The App Includes

- Current weather with time-aware interpretation
- 10-day forecast with expanded day dialogs
- Decision Mode for quick yes/no style weather questions
- Clothing guidance with visual outfit recommendations
- Activity suggestions based on current and near-term conditions
- Nearby place recommendations with Google Maps handoff
- Live weather map with switchable layers
- City-to-city comparison tools
- Export panel for CSV, Excel, and PDF forecast bundles
- Trip planner PDF export with destination and comparison cities
- Local preference persistence and last-viewed weather state

## Data Sources

The app currently uses public data providers directly from the codebase:

- Open-Meteo geocoding and forecast APIs
- Open-Meteo historical forecast API for past export windows
- MET Norway forecast API as a fallback provider
- Overpass API for nearby place recommendations
- Google Maps search links for place handoff

No API keys are required for the current implementation.

## Tech Stack

- Python 3.12
- Streamlit
- Requests
- Custom HTML/CSS/JavaScript search component in `ui/search_component`
- Custom in-repo CSV, XLSX, and PDF exporters

## Project Structure

```text
app.py                         Main Streamlit application flow
services/weather_client.py     Weather fetching, fallback logic, caching, persistence
services/exporters.py          CSV, Excel, PDF, and trip-plan PDF generation
services/decision_engine.py    Decision Mode scoring and recommendation logic
services/place_recommendations.py Nearby place lookup and Google Maps links
services/user_preferences.py   Local user preference persistence
services/clothing_catalog.py   Clothing visuals and outfit bundle helpers
ui/components.py               Shared UI rendering helpers and styling
ui/search_component/           Custom search component used across the app
images/                        App imagery, weather visuals, and branding assets
data/                          Background and asset configuration files
```

## Getting Started

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the app

```powershell
streamlit run app.py
```

By default, Streamlit will open the app in your browser and serve it locally.

## Runtime Files

The app creates a few local files while running:

- `user_preferences.json` for saved preference settings
- `last_weather_state.json` for the last loaded weather view

These files are generated locally and are not required to be committed.

## Main App Sections

### Overview

The overview surfaces the strongest current weather signal first, then gives short practical next-action recommendations.

### Insights

The insights section explains the weather in a more decision-ready way, including scores and time-aware recommendations.

### What To Wear

This section combines written outfit guidance with weather-specific clothing visuals.

### Activities

This includes Decision Mode, weather-weighted activity recommendations, nearby place suggestions, and the trip planner PDF workflow.

### Map

The map section provides inline live weather layers such as clouds, temperature, rain, wind, pressure, radar, and satellite.

### Compare

The compare section lets you contrast cities side by side using the same weather interpretation logic.

## Export Support

The app currently supports:

- CSV weather exports
- Excel weather exports
- PDF weather exports
- Trip planner PDF exports

Export windows include present and past date ranges, with mixed historical and forward-looking ranges handled inside the weather client.

## Notes

- The project currently has no formal automated test suite.
- Quick validation can be done with `python -m py_compile app.py services\exporters.py services\weather_client.py ui\components.py`.
- Place recommendations depend on third-party Overpass availability and may return fewer results during rate limits or service slowdowns.
- The live map is intentionally inline only; the expandable map flow has been removed.

## License

This project is licensed under the MIT License.

The full license text is available in [LICENSE](/C:/Users/mohdb/Downloads/Personal%20Info/Python%20Weather%20APP/LICENSE).
