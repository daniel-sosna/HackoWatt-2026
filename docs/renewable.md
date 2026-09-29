# Renewable planning

The unified dashboard's **PV planning** view evaluates a selected photovoltaic
capacity against the generated household demand. It is a planning calculation,
not a roof survey or financial offer.

## Inputs and boundaries

- `hourly.csv` provides household demand and the hourly daylight shape.
- `shortwave_radiation_instant` is used only as a shape. It is normalised to the
  selected annual specific yield because it is not plane-of-array energy.
- `appliance_events.csv` provides observed washing-machine and dishwasher runs
  for conservative shifting candidates. The current MVP identifies candidates;
  it does not automatically shift household demand.
- Economic assumptions are the centralized `ECONOMIC_MODES` constants in
  `hackowatt.renewable`.

## Energy-flow calculation

```text
hourly PV = normalised daylight shape × capacity
self-use  = min(load, PV)
import    = max(load - PV, 0)
export    = max(PV - load, 0)
grid cost = sum(import × purchase price - export × export value)
```

The dashboard reports total PV generation, self-consumption, demand coverage,
CAPEX, first-year savings, and simple payback. The tariff uses Polish local time
while `timestamp_utc` remains the physical-hour index.

## Limits

- Demand and appliance events are synthetic and uncalibrated.
- Hourly matching can overstate settlement-period self-consumption.
- Poland-mode values are editable planning defaults, not market advice.
- Real PV/weather providers should be implemented in the relevant provider
  module without changing these energy-balance calculations or the UI contract.
