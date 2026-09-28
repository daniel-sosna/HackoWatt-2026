# HackoWatt — energy decisions that fit a family's day

## Problem and solution

A household needs to understand when electricity is expensive, whether rooftop
solar is worthwhile and which changes fit its routine. HackoWatt combines a
household demand forecast, an interactive solar investment simulator and
explainable scheduling suggestions in one accessible interface.

The prototype uses the supplied Silesian family scenario: four residents, direct
electric heating and a separate electric hot-water tank. The household data is
synthetic. All assumptions and model limitations are exposed in the application.

## What users can do

- Compare a past day before and after activity shifting, or inspect a separate
  24-hour, 3-day or 7-day forecast with visible error information.
- Choose solar size, financial assumptions and an objective: lower bills, more
  solar use or reduced household grid peaks.
- Compare annual production, demand coverage, avoided grid purchases, savings
  and payback for current habits and flexible activities at six panel sizes.
- Inspect a device's use, edit hourly presence and decide which activities may
  move. Keep any recommendation at its original time and see the plan update.
- Explore a separate temperature-based heating/hot-water plan that rejects
  checked comfort violations and preserves terminal heat reserve.
- Use larger text, higher contrast, keyboard controls and data tables alongside
  charts. These features support accessibility; formal certification is not claimed.

## Example result

With 4 kWp, an assumed yield of 1,000 kWh/kWp/year and the organiser's economics,
the generated 2024–2025 household produces an average 4,000 kWh of solar annually.
It uses about 1,267 kWh directly with current habits, covering 19.5% of household
demand. Annual savings after maintenance are approximately €553 with current
habits and €590 with permitted activity shifts. Simple package payback changes
from 9.4 to 8.8 years. These are scenario estimates, not measured field savings.

Moving a washing cycle on the example June day saves about €0.20 while preserving
its energy and duration. Moving activities reduces cost or grid imports; it does
not itself reduce appliance consumption. Thermal experiments report energy and
cost separately and are excluded from the annual investment saving.

## Implementation and evidence

Python prepares validated UTC-hour data and forecasts. An offline HTML/CSS/
JavaScript application performs energy balances, greedy constrained event
scheduling, investment cash flows and a bounded thermal search using a one-zone
house and well-mixed tank. CSV/JSON contracts let the team's models replace the
input forecast without replacing the interface.

The current demand model has high validation error: about 79.9% 24-hour WAPE.
The application shows this limitation. It is an advisory prototype, with no
automatic weather refresh or real appliance actuation. Poland mode is an
editable financial scenario, not a full statutory net-billing settlement.

The presentation handbook documents equations, constants, literature, worked
examples, sources, limitations and jury questions. Its generated version is
`results/renewable/simulator_methodology.html`; the designed PDF edition is
`output/pdf/HackoWatt_Simulator_Handbook.pdf`.

## Run the demonstration

From the repository root in the project virtual environment:

```powershell
python main.py renewable-dashboard
```

Open `results/renewable/renewable_energy_simulator.html` in a browser. Copy its
companion `simulator_methodology.html` with it. The application and handbook
work offline. If generated household/forecast results are absent, run
`python main.py generate` and `python main.py forecast` first.
