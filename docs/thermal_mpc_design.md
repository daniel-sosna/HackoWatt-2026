# Thermal digital twin and predictive control design

## Decision

Use a hybrid, grey-box digital twin: physical heat balances provide safe and
explainable behaviour, while recent measurements continuously identify the
parameters that differ from one house to another. Run a 24-hour model
predictive controller (MPC) every hour and apply only its first action before
refreshing weather, occupancy, demand, tariff, and sensor inputs.

The default HackoWatt scenario remains direct electric heating with a separate
electric boiler. A heat-pump mode is an explicit user choice and must include a
temperature-dependent manufacturer performance map; it must not be inferred
silently.

## What the repository already contains

`src/hackowatt/thermal.py` is a stateful physical simulator running at one-minute
resolution. It includes:

- an analytic one-zone resistance-capacitance (1R1C) building balance;
- fabric, infiltration, and wind-dependent heat loss;
- solar and occupant/electrical internal gains;
- occupied, sleeping, and away temperature setpoints;
- thermostat hysteresis and heating capacity;
- a well-mixed domestic hot-water tank with draw, incoming cold water, standing
  loss, heater power, setpoint, and deadband;
- comfort, hot-water shortfall, and energy-balance diagnostics.

The renewable dashboard uses the same model family with hourly decisions and
four 15-minute state updates per hour. A bounded beam search (120 states) tests
0/50/100% heater and boiler duty fractions. Candidates with checked comfort or
hot-water-service violations are rejected; endpoint room and tank temperatures
must preserve the thermostat baseline's reserve to within 0.05 °C. A feasible
baseline remains a candidate. If no feasible plan is found, the interface shows
a thermostat fallback and makes no comfort/saving claim.

Tank draws include a cold-water depletion model; tank losses enter room gains.
The experiment is separate from annual appliance/PV savings. It uses an
approximate starting state and a hybrid of direct-total and modular-component
forecasts, which must be reconciled before deployment. It is a bounded advisory
plan, not a globally optimal schedule or a live MPC service. The minute simulator
remains the reference for future controller validation. Full equations and
limitations are in `src/hackowatt/simulator_methodology.html`.

## Recommended model hierarchy

### Space heating: 2R2C grey-box model

For control, use two temperature states: indoor air `T_air` and effective
building mass `T_mass`. A discrete state-space form is:

```text
x[k+1] = A x[k] + B_heat Q_heat[k] + B_weather w[k]
y[k]   = T_air[k]

x = [T_air, T_mass]
w = [T_outdoor, solar_gain, internal_gain, wind]
```

The resistances represent heat transfer to outdoors and between air and the
building fabric. The capacitances represent stored heat in the air/furnishings
and walls/floors. This preserves the current model's physical meaning while
representing delayed heat release from the building mass, which a 1R1C model
cannot separate.

Start from `resolved_house.json`, then identify bounded parameters from measured
indoor temperature, outdoor weather, and heater state. Re-estimate them on a
rolling recent window. Research on residential MPC identifies a 3R2C model as a
useful accuracy/complexity trade-off and shows that adaptive parameters reduce
comfort errors as weather changes.

For direct resistance heating:

```text
electric_power = delivered_heat / heating_efficiency
```

For an explicitly selected heat pump:

```text
electric_power = delivered_heat / COP(T_outdoor, supply_temperature, part_load)
```

COP means coefficient of performance: delivered heat divided by electrical
input. It is not a constant. Use the selected unit's manufacturer map or a
documented performance curve, including capacity limits and defrost behaviour.

### Domestic hot water: three-node stratified tank

The current single-temperature tank is suitable for generation and a first MPC
version. A product controller should use at least three vertical nodes (top,
middle, bottom):

```text
C_i * dT_i/dt = heater_i + mixing_i + conduction_i
                - standing_loss_i - draw_displacement_i
```

Cold inlet water enters the bottom, usable hot water leaves the top, and heat
moves between layers. The controller must keep the predicted top temperature
above the user's service minimum before likely draws. Laboratory work reports
that a three-node MPC represents real stratification better than a one-node
controller and achieved materially larger cost reductions in the tested water
heaters.

Hygiene and equipment limits are hard constraints supplied by the appliance or
local operating policy. The product must expose their source and must not let a
cost objective override them.

## MPC objective and constraints

At each run, minimise over the next 24 hours:

```text
grid_import[t] * buy_tariff[t]
- grid_export[t] * export_value[t]
+ comfort_penalty[t]
+ hot_water_shortfall_penalty[t]
+ switching_penalty[t]
+ peak_demand_penalty[t]
```

Subject to:

- the 2R2C building equations;
- the stratified tank equations;
- PV and household electricity balances;
- heater/boiler power and cycling limits;
- occupied, sleep, and away comfort bands;
- minimum usable tank temperature and required hot-water reserve;
- user appliance deadlines and one physical unit per appliance;
- no use of observations that occur after the forecast issue time.

Comfort and hot-water service are hard constraints under normal operation. A
clearly labelled fallback may use slack variables only when the forecast problem
would otherwise be infeasible; every predicted violation must be visible to the
user.

Use a deterministic linear or mixed-integer formulation first. Add several
weather/occupancy/draw scenarios or safety margins for forecast uncertainty.
Reinforcement learning is not needed for the hackathon and is harder to validate
and explain.

## Inputs and evidence hierarchy

1. Live measurements: indoor temperature, heater state/power, tank/top-water
   temperature, smart-meter power, and optional flow/draw events.
2. Issued forecasts: outdoor temperature, wind, humidity, and global/tilted
   solar radiation from Open-Meteo; PV forecast from PVGIS, forecast.solar, or a
   calibrated irradiance-to-power model.
3. Known plans: occupancy, sleep/away preferences, appliance deadlines, and
   exceptional events.
4. Learned distributions: occupancy and hot-water demand conditional on hour,
   weekday, season, and recent behaviour.
5. Static house/appliance inputs: floor area, heating type and capacity, tank
   volume and power, insulation/age class, PV orientation and capacity.
6. Documented defaults with uncertainty ranges when the user does not know a
   parameter.

The system should never present a sampled default as a measured house property.
It should show `measured`, `learned`, `user supplied`, or `assumed` next to every
important input.

## Current data audit

- `hourly-2.csv`: 17,544 hourly rows, no duplicate rows. The only missing field
  is `vacation_block` when no named vacation block applies.
- `silesia_weather_full.csv`: 17,544 rows, no nulls or duplicate rows.
- `residents_hourly-2.csv`: 70,176 person-hours, no nulls or duplicate rows. The
  sum of mutually exclusive activity minutes never exceeds 60 for any person-hour.
- Annual generated electricity is about 6.47 MWh in 2024 and 6.53 MWh in 2025.
  Space heating is about 1.98 and 2.07 MWh; water heating is about 2.34 and
  2.30 MWh respectively.
- The simulated indoor range is 16.70-35.15 degrees C and the tank minimum is
  28.15 degrees C. There are comfort and hot-water shortfall events. These are
  important controller test cases, not evidence of real-house accuracy.
- Indoor and tank temperatures are outputs of the same synthetic model. They
  cannot be used as independent validation measurements.

## Calibration and validation

For a real home, collect two to four weeks of indoor temperature, heater state
or power, and weather. Deliberate thermostat changes improve parameter
identifiability. Fit only physically plausible positive resistances,
capacitances, gain factors, and efficiencies.

Use chronological validation periods and report:

- 1-hour and 24-hour indoor-temperature MAE;
- tank top-temperature MAE and hot-water availability errors;
- load forecast MAE/WAPE for 24 hours, 3 days, and 7 days;
- energy-balance residual;
- occupied discomfort degree-hours;
- hot-water shortfall volume or energy;
- cost, grid import, PV self-consumption, peak demand, and device starts;
- performance against thermostat/rule-based control on identical forecasts.

Benchmark the controller in simulation with BOPTEST, EnergyPlus, or NREL OCHRE
before connecting actuators. BOPTEST exposes high-fidelity building emulators
and standard control KPIs through an API; OCHRE is residential and includes HVAC,
water heaters, PV, batteries, and external controllers.

## Product experience

The main screen should answer four questions in plain language:

1. What will happen? Show the next 24 hours of demand, PV, temperature, tank
   reserve, and grid exchange with uncertainty bands.
2. What should move? Show a chronological schedule with original time, proposed
   time, reason, constraint, expected saving, and an approve/lock control.
3. Will the family notice? Show lowest predicted room and water temperature and
   state `No comfort change expected` only when constraints prove it.
4. Why should the user trust it? Show forecast issue time, data freshness,
   model confidence, and whether each key parameter is measured, learned,
   user-supplied, or assumed.

Provide `Comfort`, `Balanced`, and `Maximum savings` presets that change visible
comfort margins and automation permissions. Keep heating and water heating in
advisory mode until the stateful model has valid sensor state and passes the
comfort checks. Recompute after every new measurement or forecast, but apply only
approved actions.

## Implementation order

1. Connect a scheduled service that refreshes the implemented issued forecast
   and sensor-state contracts before each control run.
2. Add bounded parameter fitting when real sensor data is available.
3. Upgrade the building to 2R2C and the tank to three nodes; compare out-of-sample
   prediction and controller KPIs before adoption.
4. Add an explicit heat-pump mode with a supplied performance map.
5. Validate with OCHRE or BOPTEST and run replay tests for forecast errors,
   missing sensors, DST, outages, and unusual occupancy.

## Sources

- HackoWatt Common Challenge Assumptions and Silesian Family Home PDFs supplied
  with the repository.
- [EnergyPlus Engineering Reference: heat balances and water thermal tanks](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v24.2.0/EngineeringReference.pdf)
- [NREL OCHRE residential energy model](https://github.com/NatLabRockies/OCHRE)
- [US DOE BOPTEST overview](https://www.energy.gov/cmei/buildings/boptest-building-operations-testing-framework)
- [BOPTEST user guide](https://ibpsa.github.io/project1-boptest/docs-userguide/introduction.html)
- [Adaptive grey-box residential MPC comparison](https://doi.org/10.1016/j.buildenv.2024.111391)
- [Grey-box building model for MPC](https://doi.org/10.1016/j.enbuild.2023.113624)
- [Domestic hot-water MPC with demand forecasting](https://doi.org/10.1016/j.ecmx.2022.100254)
- [Experimental one-node versus three-node water-heater MPC](https://arxiv.org/abs/2312.04102)
- [Open-Meteo forecast API](https://open-meteo.com/en/docs)
- [European Commission PVGIS hourly API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en)
- [ASHRAE Standard 55 overview](https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy)
