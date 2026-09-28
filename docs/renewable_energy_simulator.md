# Renewable Energy Simulator

The `renewable-dashboard` component turns the generated household history into
an offline, interactive rooftop-PV investment simulator. It covers the five
challenge outputs for a selected installation capacity and compares current
habits with learned, user-editable activity shifting.

```powershell
python main.py generate
python main.py renewable-dashboard
```

Open `results/renewable/renewable_energy_simulator.html`. The file contains its
data and code, needs no server, makes no network requests and can be copied to a
demo computer.

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

Space heating and the hot-water tank are available as disabled-by-default proxy
optimisations. The proxy exposes only 15% of hourly heating and 50% of hourly
tank energy as potentially movable and preserves their total kWh. It is clearly
marked **model validation required** because final dispatch must be checked by a
stateful model against indoor comfort, heater capacity, tank temperature and
hot-water demand. Proxy results must not be presented as a validated controller.
The dashboard states that control hardware/software cost is not included in
package payback.

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
