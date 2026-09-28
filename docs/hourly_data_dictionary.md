# Plausibility check and `hourly.csv` data dictionary

This document describes `results/default/hourly.csv`, generated with seed `20260928`. It is a synthetic scenario. Weather and calendar information are real inputs; electricity demand, resident activities, temperatures, boiler state, and appliance demand are model outputs, not measurements from a home.

## Validation summary

The file contains 17,544 unique physical hours for 2024--2025 and 55 columns. It has no missing or negative energy values. The individual appliances and systems sum exactly to `total_kwh` in every hour; each resident's main-activity minutes total 60 in every hour. An empty `vacation_block` outside a family trip is expected and is not a missing measurement. The data set is therefore internally consistent for development and testing.

The two-year scenario uses 13.00 MWh: 4.05 MWh for space heating, 4.63 MWh for the boiler, and 4.31 MWh for other loads, or 6.50 MWh per year on average. For a 100 m2 home with direct electric heating, the order of magnitude is possible, but the figure is a scenario output, not an observed bill.

Improved insulation and passive night ventilation are represented. There is no air conditioner. During the summer the indoor temperature may still be high; a high temperature while the family is away must be distinguished from comfort while residents are at home. Winter underheating is retained as data rather than corrected artificially. The exact balance and comfort diagnostics are recorded in `validation.json`.

The calendar contains six joint family trips: 10 working days in summer, 5 in winter, and 5 in spring/autumn for each of 2024 and 2025. All four residents are away in every hour of a trip. That is 40 working vacation days per parent over two years. Illness and other long trips are not modelled. Optional activities can still fail to fit the schedule, so Eurostat is a soft reference rather than an exact target.

The base loads are close to deterministic in this version: the fridge is 1.0 kWh/day, the router is 0.012 kW, and standby demand is 0.040 kW. They are useful starting assumptions and must not be treated as a learned profile for a particular home.

## Time handling

`timestamp_utc` is the only canonical time key. It is always UTC, unique, and sorted. `timestamp_local` contains Polish local time with an explicit `+01:00` or `+02:00` offset; at a daylight-saving transition the visible local time 02:00 may occur twice with different offsets. When using pandas, parse with `utc=True` and then convert to `Europe/Warsaw`. Do not use the local-time string as a unique identifier.

Every `_kwh` column is energy for a physical hour, not average power. For a one-hour interval kWh happens to equal the numerical average kW value, but the unit must not be changed. `peak_1min_kw` is the within-hour maximum from the minute model.

## Column dictionary and modelling role

| Column or group | Meaning and unit | Origin | Role in a whole-home load model |
|---|---|---|---|
| `timestamp_utc` | Start of hour in UTC | Index | Required key; derive lags and time features from it. |
| `timestamp_local` | `Europe/Warsaw` time with offset | Derived | Reporting and calendar features; not a unique key. |
| `temperature_2m` | Air temperature, C | Weather | Good feature only when an issued forecast is used for the future hour. |
| `cloud_cover` | Cloud cover, % | Weather | Candidate feature; weaker than temperature for heating. |
| `relative_humidity_2m` | Relative humidity, % | Weather | Candidate feature; do not assume causation without calibration. |
| `wind_speed_10m` | Wind speed, km/h | Weather | Good infiltration and heat-loss feature; choose one wind representation. |
| `precipitation` | Precipitation in the source's hourly unit | Weather | Candidate activity and lighting feature. |
| `snowfall` | Snowfall in the source's hourly unit | Weather | Rare candidate feature. |
| `shortwave_radiation_instant` | Short-wave radiation, W/m2 | Weather | Useful proxy for solar gains and lighting. |
| `wind_ms` | Wind speed, m/s | Derived from km/h | Redundant when `wind_speed_10m` is present; use only one. |
| `fridge_kwh`, `router_kwh`, `standby_kwh` | Base appliance energy per hour | Synthetic appliances | Separate targets only with sub-metering; otherwise target leakage for `total_kwh`. |
| `lighting_kwh`, `tv_kwh`, `console_kwh`, `desktop_kwh`, `laptop_kwh` | Lighting and entertainment energy per hour | Synthetic appliances | Separate targets only with sub-metering; otherwise target leakage. |
| `kettle_kwh`, `coffee_machine_kwh`, `hob_kwh`, `oven_kwh`, `microwave_kwh` | Cooking energy per hour | Synthetic appliances | Separate targets only with sub-metering; otherwise target leakage. |
| `washing_machine_kwh`, `dishwasher_kwh`, `vacuum_kwh`, `charging_kwh` | Flexible appliance energy per hour | Synthetic appliances | Separate targets only with sub-metering; otherwise target leakage. |
| `space_heating_kwh` | Direct electric space-heating energy per hour | Synthetic physical model | Separate target with a heating meter; otherwise target leakage. |
| `water_heater_kwh` | Electric boiler energy per hour | Synthetic physical model | Separate target with a boiler meter; otherwise target leakage. |
| `total_kwh` | Sum of every stated load for the hour | Main synthetic target | Main target; use only past measured values as model inputs. |
| `peak_1min_kw` | Maximum minute-level power within hour, kW | Derived | Peak target/evaluation quantity; never a future input. |
| `mean_kw` | Mean hourly power, kW | Derived | Equal to `total_kwh` for one-hour intervals; do not duplicate as a feature. |
| `indoor_c` | Mean zone temperature, C | Synthetic physical model | Useful past/current sensor feature; never use future actual values. |
| `tank_c` | Mean boiler-tank temperature, C | Synthetic physical model | Useful past/current sensor feature; never use future actual values. |
| `setpoint_c` | Active zone setpoint, C | Model rule | Useful when the future thermostat schedule is known; otherwise diagnostic. |
| `unmet_comfort_degree_minutes` | Comfort shortfall in degree-minutes | Derived control | Quality diagnostic, not a forecasting input. |
| `hot_water_unmet_kwh` | Unserved hot-water heat demand, kWh | Derived control | Diagnostic, not consumed electricity. |
| `heat_loss_kw` | Net fabric/ventilation heat flow, kW | Synthetic physical model | Physical-model or calibration quantity; may be negative when heat arrives from outside. |
| `solar_gain_kw` | Solar heat gain, kW | Synthetic physical model | Physical-model quantity, not an independently measured load. |
| `internal_gain_kw` | Heat from people, appliances, and boiler, kW | Synthetic physical model | Diagnostic/physical-model quantity; it partly derives from demand and leaks `total_kwh`. |
| `thermal_residual_kwh` | Numerical thermal-balance residual, kWh | Technical control | Should remain near zero; never use in ML. |
| `night_ventilation_active_fraction` | Fraction of hour with passive night ventilation, 0--1 | Thermal-model rule | Passive-cooling diagnostic; future realised values must not enter ML. |
| `indoor_min_c`, `indoor_max_c` | Zone-temperature minimum and maximum in the hour, C | Derived | Comfort diagnostics; past sensor observations can be useful. |
| `tank_min_c` | Tank-temperature minimum in the hour, C | Derived | Hot-water diagnostic; past sensor observation can be useful. |
| `hot_water_mixed_l` | Mixed hot-water volume delivered, L | Synthetic behaviour | Separate target only with water metering; otherwise same-hour leakage. |
| `occupancy_mean` | Mean residents at home, 0--4 | Synthetic schedule | Use only past sensor/estimate data; future actual occupancy is unknown. |
| `awake_at_home_mean` | Mean awake residents at home, 0--4 | Synthetic schedule | Use only past estimates; use a schedule model for the future. |
| `public_holiday` | Polish public-holiday flag | Calendar | Good known-in-advance feature. |
| `school_break` | Regional school-break flag | Calendar | Good known-in-advance feature. |
| `school_day` | School-day flag | Derived calendar | Good known-in-advance feature. |
| `family_vacation` | Entire family is on a joint trip | Planned calendar | Good known-in-advance feature; everyone is away when true. |
| `vacation_block` | Vacation block name, such as `summer_2025` | Planned calendar | Scenario audit value; categorical feature only after explicit encoding. |
| `ania_wfh` | Ania's planned work-from-home flag | Synthetic schedule | Useful only when a real plan is known for the forecast horizon. |
| `marek_shift` | Marek's `morning`/`evening`/`night`/`off` shift | Synthetic schedule | Useful only when a real shift plan is known for the forecast horizon. |

## Data a real home can import and learn from

Store every reading with `timestamp_utc`, measurement quality, and source. Keep measured data separate from synthetic data and never overwrite either one. The following feeds are useful for an hourly model.

| Import feed | Granularity | What it improves | Replaces or calibrates |
|---|---|---|---|
| Main smart meter: imported kWh and, when available, minute-level power | 1--15 min, then aggregate hourly | Main `total_kwh` target, peaks, seasonality, 1/24/168-hour lags | Entire synthetic `total_kwh`. |
| Separate heating and boiler meter | 1--15 min | Separation of major loads and thermostat switching | `space_heating_kwh`, `water_heater_kwh`. |
| Circuit clamps for kitchen, sockets, and laundry | 1--15 min | Load attribution, peaks, and appliance rules | Synthetic appliance columns. |
| Indoor temperature, preferably in several zones | 5--15 min | Heat loss, thermal capacity, solar gains, and comfort | `indoor_c`, min/max values, and thermal model. |
| Thermostat setpoint, mode, relay/power | Events plus 1--15 min | Heating rules and power forecast | `setpoint_c`, `space_heating_kwh`. |
| Boiler top/bottom temperature, or at least power and water meter | 1--15 min | Tank volume, losses, and hot-water schedule | `tank_c`, `hot_water_mixed_l`, `water_heater_kwh`. |
| Outdoor temperature and issued weather forecasts | Hourly | Forecasting ahead rather than after the fact | Weather features used in training. |
| School calendar, holidays, voluntary real shift/WFH plan | Day/hour | Expected occupancy and household rhythm | `school_day`, `marek_shift`, `ania_wfh`. |
| Optional aggregate motion/CO2 occupancy data, without video | 5--15 min | Occupancy feature | `occupancy_mean`, `awake_at_home_mean`. |
| Mains parameters: phase count, main breaker, voltage/current | Minute/hour | Plausible peaks and demand constraint | `peak_1min_kw`, allowed simultaneous demand. |

For a day-ahead model, use only data known before the hour: calendar, published weather forecast, known setpoints and plans, and past meter readings. `total_kwh` lags, especially 1, 24, and 168 hours, become useful after a real meter is installed. Never provide future `total_kwh`, future appliance columns, future indoor temperature, actual occupancy, or `internal_gain_kw`; each contains the answer and causes data leakage.

The synthetic set is appropriate for testing code, training users on the interface, validating the schema, and creating an initial physics-informed baseline. Retrain a real model on measurements and compare it on a later held-out period. Three to six months including a heating period is an initial minimum; a full year is better for seasonality. Store actual weather separately from the weather forecast used to make each prediction, otherwise day-ahead performance will look too optimistic.
