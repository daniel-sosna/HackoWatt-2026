# Renewable Energy Simulator

The `renewable-dashboard` component turns the generated household history into
an offline, interactive rooftop-PV investment simulator. It covers the five
challenge outputs for a selected installation capacity and compares current
habits with learned, user-editable activity shifting.

```powershell
python main.py generate
python main.py forecast
python main.py renewable-dashboard
```

Open `results/renewable/renewable_energy_simulator.html`. The file contains its
data and code, needs no server, makes no network requests and can be copied to a
demo computer.

The interface is organised like a consumer energy application with five
bookmarkable tabs:

- **Overview** for headline PV, flow, savings and payback metrics;
- **Smart plan** for device permissions, learned habits and recommendations;
- **Household** for optimisation goals, grid limit, resident count and hourly
  presence;
- **Solar investment** for capacity comparison and editable financial inputs;
- **Data & terms** for connection readiness, provenance and explanations.

## Two economic modes

**Hackathon mode** uses the common organiser assumptions: €1,300/kWp capital
cost, €0.08/kWh export value, 1% annual operating cost and the stated four
time-of-use purchase prices. Its payback is deliberately simple so team results
remain comparable.

The €1,300/kWp value is not a market quote. It comes directly from
`docs/HackoWatt-Common-Challenge-Assumptions.pdf` and is shown with that source
inside the interface. Poland mode deliberately labels its starting installation
price as an illustrative editable planning value.

**Poland mode** exposes planning inputs for retail purchase price, net-billing
export value, subsidy, effective tax benefit, PV degradation, discount rate,
tariff growth, analysis horizon and inverter replacement. These values are
editable because the applicable contract, market settlement, programme and tax
eligibility change. Subsidy and tax benefit default to zero to avoid claiming
that a household qualifies.

The interface defines PV, kWp, kWh, self-consumption, demand coverage, grid
import/export, CAPEX, OPEX, payback, NPV, net-billing and COP. COP is included to
prevent confusion with a heat pump: the current scenario has direct electric
heating with efficiency 1.0 and does not apply a heat-pump COP.

## Production and energy balance

The supplied `shortwave_radiation_instant` is horizontal instantaneous
radiation, not measured plane-of-array hourly energy. The simulator therefore
uses it only for the hourly daylight shape and normalizes that shape to the
explicit `specific yield` assumption, initially 1,000 kWh/kWp/year:

```text
hourly PV = radiation shape × capacity × stated annual specific yield
self-use  = min(load, PV)
import    = max(load - PV, 0)
export    = max(PV - load, 0)
grid cost = sum(import × purchase price - export × export value)
```

This is reproducible and explicit about the missing roof/module specification.
The user can change the specific yield. A future version can replace the shape
with a validated tilted-irradiance or forecast.solar provider without changing
the balance or economic model.

## Learned habits and constraints

The simulator reads cycle records from `appliance_events.csv`, currently
washing-machine and dishwasher cycles. For each physical appliance it learns
the 10th percentile, median and 90th percentile of local start time. The
observed window becomes a default only. The user can edit:

- whether that appliance may be shifted;
- earliest start;
- latest finish;
- maximum shift from the historical start.

The same interface exposes opt-in recommendations for cooking, TV/console and
computer use. These are marked **ask first** because moving them changes a human
activity rather than an unattended appliance cycle. A device selector shows its
typical 24-hour energy profile, annual energy, busiest hour and event count.

The recommendations panel reports concrete historical examples as
`original time -> proposed time`, together with the moved kWh, reason and
estimated value. Results can be filtered by device.

The browser optimiser moves complete non-interruptible cycle profiles, preserves
their kWh and prevents overlapping cycles on the same physical appliance. It
uses an editable 24-hour presence plan for weekdays and weekends so cooking,
screen and computer recommendations occur only while somebody is home. Changing
presence constrains recommendations; it does not invent a new consumption
profile by itself.

The household control centre lets the user choose the optimisation goal:

- lowest electricity bill uses the tariff and export value;
- use the most rooftop solar prioritises reductions in grid import, with cost as
  the tie-breaker;
- avoid household grid peaks prioritises staying below an editable hourly grid
  limit, with cost as the tie-breaker.

The number of residents caps the editable hourly presence plan. Input cards
label whether a value can come from an automatic API, a meter or CSV, learned
history, user input, or a sensor.

Space heating and the hot-water tank are removed from appliance shifting. The
Household tab instead runs a 24-hour stateful controller with the repository's
one-zone RC heat balance and well-mixed tank equations. It carries indoor and
tank temperature between hours, tests heater/boiler actions, penalises comfort
or service shortfall, and compares the selected plan with thermostat control.
The result remains advisory because the supplied temperatures and house
parameters are synthetic. The dashboard states that control hardware/software
cost is not included in package payback.

## Forecast and live-data contracts

`python main.py forecast` supplies the default Tomorrow view from the latest
rolling-origin validation horizon. The page shows demand, PV, tariff, an
empirical 10--90% residual interval, forecast issue time, WAPE, peak-time error,
and the components driving the largest predicted peaks. Recorded weather in
this validation output is clearly labelled as a perfect-weather assumption.

A real provider or team service can replace that backtest without changing the
interface:

```powershell
python main.py renewable-dashboard `
  --issued-forecast results/team/issued_forecast.csv `
  --sensor-state results/team/sensor_state.json
```

The issued forecast requires hourly, increasing `timestamp_utc`, `load_kwh`,
`outdoor_c`, `wind_ms`, and `radiation_wm2` for at least 24 hours. Optional
columns are `issued_at_utc`, `model_id`, `lower_kwh`, `upper_kwh`, `base_kwh`,
`behaviour_kwh`, `space_heating_kwh`, `water_heating_kwh`, and
`hot_water_draw_l`. Sensor JSON accepts `indoor_c`, `tank_c`, and an optional
`issued_at_utc`. The active source and uncertainty status remain visible.

## Colleague model contract

A forecast or controller from another team member can replace the dashboard's
load and occupancy input without changing the UI:

```powershell
python main.py renewable-dashboard --model-profile results/team/model_profile.csv
```

The CSV contract is:

| Column | Requirement |
|---|---|
| `timestamp_utc` | Required, unique, same physical-hour timeline as `hourly.csv` |
| `load_kwh` | Required, finite nonnegative predicted or controlled load |
| `occupancy_people` | Optional, 0--4 people |
| `model_id` | Optional, one model identifier shown in the interface |
| `issued_at_utc` | Optional provenance field reserved for forecast issue time |

Exact timestamp matching prevents a model result from being silently shifted by
an hour or joined across the wrong daylight-saving transition.

## Investment formulas

Simple annual savings equal the no-PV bill minus the PV bill and annual OPEX.
Scenario B uses the original no-PV household as the comparison, so it reports
the value of the complete PV plus scheduling package. Poland-mode NPV uses:

```text
PV production in year y = year-1 production × (1 - degradation)^(y-1)
NPV = -net initial cost + sum(net cash flow y / (1 + discount rate)^y)
```

The selected inverter replacement cost is subtracted in its selected year.
The tax field is an effective benefit rate applied only to expenditure left
after subsidy; users must enter a value appropriate to their eligibility.

## Limitations

- Household consumption and appliance events are synthetic and uncalibrated.
- Annual specific yield is a stated scenario input, not a roof survey.
- Hourly matching can overstate self-consumption relative to finer settlement.
- The scheduling algorithm is a transparent greedy optimiser for the demo, not
  a proof of the global optimum.
- The thermal controller uses a transparent 1R1C building and one-node tank with
  hourly binary actions. A calibrated 2R2C/three-node model remains the product
  upgrade after real sensors are available.
- Poland-mode defaults are illustrative editable values, not a financial offer.

## Reviewed sources

- `docs/HackoWatt-Common-Challenge-Assumptions.pdf` controls Hackathon tariffs,
  export value, installation cost and annual OPEX.
- Polish net-billing overview:
  <https://www.gov.pl/web/klimat/prosument-netbilling>
- Polish thermomodernisation tax relief:
  <https://podatki.gov.pl/ulgi-i-odliczenia/ulga-termomodernizacyjna-pit>
- NREL historical PV degradation review:
  <https://www.nrel.gov/docs/fy12osti/51664.pdf>
- IEA PVPS operation and maintenance guidance, including inverter replacement:
  <https://iea-pvps.org/wp-content/uploads/2022/11/IEA-PVPS-Report-T13-25-2022-OandM-Guidelines.pdf>
- European Commission cost-benefit analysis guide for discounting concepts:
  <https://ec.europa.eu/regional_policy/sources/studies/cba_guide.pdf>
