# Product and data strategy

## Product promise

The application should answer one household question:

> What will my home consume tomorrow, why, and what can I safely change to pay
> less, use more of my solar power, and reduce the evening grid peak?

This preserves the team plan of forecast, explanation, optimisation, before/after
comparison, and PV investment while making the result usable outside the
hackathon.

## Real-world data availability

| Input | No hardware | Connected source | User control | Product fallback |
|---|---|---|---|---|
| Weather forecast | Open-Meteo API | Same | Location | Last successful forecast with freshness warning |
| Historical weather | Open-Meteo archive | Same | Location and period | Supplied Silesia history |
| PV production forecast | PVGIS typical history or irradiance model | forecast.solar or inverter API | kWp, tilt, azimuth, losses | Explicit specific-yield assumption |
| Whole-home consumption | Bill or provider CSV | Smart meter, TAURON eLicznik/account export when available, Home Assistant | Tariff and import/export mapping | Synthetic scenario history |
| Appliance consumption | Rated power and duration | Smart plug, relay, appliance API, Home Assistant | Quantity, power, duration, deadline, permission | Challenge values and learned events |
| Occupancy | Weekly schedule | Presence sensors, phone/geofence, home platform | People home by hour and exceptions | Learned weekday/weekend profile |
| Indoor temperature | Manual current reading | Thermostat or room sensor | Comfort bands | Simulated state marked assumed |
| Heating state/power | Equipment rating | Thermostat, relay, heat meter, smart plug | Heating type, capacity, automation permission | Direct-electric challenge default |
| Hot-water state | Tank rating and manual temperature | Tank/top-temperature and flow sensors | Volume, power, service temperature, draw plans | Well-mixed simulated tank marked assumed |
| Tariff | Manual bill entry | Supplier feed or market-price integration | Buy/sell rates and tariff type | Organiser tariff in Hackathon mode |
| PV investment cost | Installer quote | None required | Cost, subsidy, tax, OPEX, degradation | Organiser assumptions |

Every important value should show one provenance label: `live`, `forecast`,
`learned`, `user supplied`, or `assumed`, plus its update time. Missing data
should reduce confidence rather than make the screen fail.

Official evidence:

- TAURON eLicznik provides near-current monitoring for customers with a remote
  meter: <https://www.tauron-dystrybucja.pl/liczniki-zdalnego-odczytu/elicznik>
- Poland's regulator describes remote meters as the basis for detailed remote
  consumption data and dynamic tariffs: <https://www.ure.gov.pl/pl/konsumenci/faq-czesto-zadawane-py/energia-elektryczna/12226>
- Home Assistant can combine utility meters, solar inverters, batteries, smart
  plugs, relays, and individual-device energy: <https://www.home-assistant.io/docs/energy>
- Open-Meteo supplies hourly weather and solar-radiation forecasts:
  <https://open-meteo.com/en/docs>
- PVGIS provides location- and installation-specific hourly PV simulations:
  <https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en>

## User-controllable settings

Keep the first screen short. Ask for these only when they change a decision:

1. Goal: lowest bill, maximum direct solar use, or grid-peak reduction.
2. Comfort preset: Comfort, Balanced, or Maximum savings, with visible
   temperature and hot-water limits behind each preset.
3. People home tomorrow and exceptional events.
4. Appliance job: ready time, deadline, interruptible yes/no, and automatic or
   approval-required permission.
5. Household grid limit, especially when several high-power devices may overlap.
6. Heating type and whether advisory or automatic control is allowed.
7. PV size, roof tilt/azimuth, and investment assumptions.

Put technical building and economic parameters under Advanced settings. Never
ask a resident for a thermal resistance or capacitance; estimate it and show a
confidence range.

The offline simulator presents the current controls across Overview, Smart
plan, Household, Solar investment, and Data & terms tabs. URL hashes preserve
the selected page, so the demo can link directly to a workflow step.

## Differentiators worth building

### P0: complete and demonstrable

- One coherent `Tomorrow` story: demand and PV forecast, peak explanation,
  chronological smart plan, before/after result, and uncertainty.
- Explain every move with the triggering data and the respected constraint.
- Show bill, grid import, peak kW, PV self-consumption, and comfort together.
- Keep the organiser's Hackathon mode reproducible and separate from the
  editable Poland planning mode.
- Compare PV payback with current habits and with the smart plan, as required.

### P1: strongest competitive additions

- **Household control centre:** optimise for bill, self-consumption, or grid
  peak; the first version is implemented in the renewable dashboard.
- **Data confidence:** provenance and freshness for each critical input.
- **Comfort guarantee:** predicted minimum room temperature and usable hot-water
  reserve beside every heating/tank recommendation.
- **Robust schedule:** show a recommendation only when it remains useful under
  several plausible weather and occupancy forecasts; otherwise request
  confirmation.
- **Counterfactual explanation:** `Without this move, the 19:00 peak is 4.8 kW;
  with it, 3.7 kW. Room temperature stays above 20.5 C.`
- **Learning with control:** history proposes defaults, the user corrects them,
  and the correction becomes tomorrow's constraint.

### P2: development potential

- Home Assistant adapter for vendor-neutral meters, plugs, inverters, and
  thermostats.
- EV and battery modules only when the scenario or user enables them.
- Community/grid view that aggregates many anonymised homes and shows avoided
  coincident peak, without exposing individual routines.
- Carbon-intensity objective when a trustworthy regional hourly source is
  available.

## What not to prioritise during the hackathon

- A long settings wizard before the first useful result.
- Automatic heating or boiler commands without current sensor state.
- Deep learning solely for presentation value when a simpler model validates
  better.
- Battery, EV, and 100-home simulation before the required household flow is
  complete.
- Savings claims without a baseline, time period, tariff, and comfort check.

## Judging alignment

| Criterion | Evidence in the demo |
|---|---|
| Innovation and creativity | Adaptive household digital twin, comfort-aware MPC, three user-selectable objectives, confidence-aware recommendations |
| Functionality and usability | Editable constraints, chronological plan, plain-language reasons, approvals, before/after comparison |
| Technical implementation | Leakage-safe forecasts, physical thermal state, explicit optimisation objective and constraints, reproducible assumptions and tests |
| Presentation and justification | One household story, visible source for every value, metrics mapped directly to challenge requirements |

## Five-minute demo path

1. `40 seconds` - introduce the family and tomorrow's weather.
2. `50 seconds` - show the forecast and explain the evening peak by appliance.
3. `80 seconds` - set occupancy/deadlines, choose a goal, and generate the smart
   plan.
4. `50 seconds` - show before/after bill, peak, grid import, PV use, and comfort.
5. `70 seconds` - compare PV sizes and payback with and without optimisation.
6. `30 seconds` - show data provenance, real-life connection path, and the next
   product step.
