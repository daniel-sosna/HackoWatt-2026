# Family behaviour appliance and heating generation rules

Version 3.0 | 28 September 2026 | Implementation specification

This document specifies the runnable synthetic household generator in this repository. It covers Marek, Ania and their school-age children Kuba and Zosia in Katowice, appliance electricity, direct resistance space heating and a separate electric hot-water tank. It uses the supplied weather, Polish calendars and Polish household time-use reference. There is no photovoltaic generation, battery, heat pump, grid export or financial optimisation.

The output is a complete hourly electricity and activity dataset over the supplied weather period. Internal activity and thermal calculations use one-minute steps. The model is a transparent scenario, not a reconstruction of measured household behaviour. Quantitative assumptions are editable in config/default.json; realised house values are saved with every run.

## Evidence and precedence

[USER] Heating is direct electric, with a separate boiler; children are school-age; the weather timestamps are local Polish time and wind is in km/h. The Eurostat file is reported to match this family composition and to represent the 2010 reference.

[SCENARIO] The organisers specify a detached Silesian family home, an industrial shift worker, a hybrid worker, two children and indicative device consumption. These determine identity and broad routines.

[DATA] activity_time_use_full.csv supplies daily person-level participation and mean time. Weather and calendar files are observations/reference inputs supplied by the user. Their raw copies are retained unchanged.

[ASSUMPTION] Exact schedules, distribution widths, household parameters, device links, correlations, comfort settings and weather responses are engineering choices. Their numerical values are not identified by Eurostat. Default rules below describe the actual code; this version supersedes the previous proposal where they differ.

## Deliverables and reproducibility

hourly.csv contains appliance-level electricity, thermal state, weather and occupancy. residents_hourly.csv contains all primary activity minutes for every resident. Event files, proposal/rejection records, calendar, Eurostat comparison, configuration, sampled house and validation report make the result inspectable. The dashboard filters appliances, residents and dates. Separate random streams isolate house, behaviour and appliance sampling. A seed is not a substitute for recording code and dependency versions.

---

# Weather and calendar alignment

The supplied weather file contains 17,544 nominal hourly labels from 2024-01-01 00:00 to 2025-12-31 23:00, without null values. Generate only this local calendar coverage. Export unique UTC interval starts and their Europe/Warsaw representations. Each output interval is one physical hour; local days can contain 23, 24 or 25 hours.

The raw CSV has 24 labels every day. Remove nonexistent local 02:00 on 2024-03-31 and 2025-03-30. Reuse the provided 02:00 weather for both UTC offsets on 2024-10-27 and 2025-10-26. This is a disclosed normalisation assumption, not two independently measured autumn observations. Preserve raw files and report every changed mapping. Reject ordinary gaps, duplicate source timestamps, nonnumeric values or invalid humidity/cloud ranges.

Temperature is in degrees Celsius; wind is converted from km/h to m/s by division by 3.6. Precipitation is assumed mm and snowfall cm per source hour; radiation is assumed W/m2. These last units must be confirmed against the original export if a different source is used. Preserve cloud cover and relative humidity even when they do not enter a fitted response. Weather is held constant within each model hour. Using instantaneous radiation as an hourly heat-gain proxy is an approximation.

Public holidays and inclusive school-break ranges are read from the supplied text files. Weekends are independent calendar flags. Add Christmas Eve 2025 through calendar_corrections.json, citing the Polish ministry; do not alter the raw text. School-specific closure days, annual leave and replacement days for weekend holidays are not inferred. Calendars must be updated before extending the weather period.

## Weather effect on outdoor activity

Daily walking participation receives additive adjustments: free day +0.06; daily rain above 1 mm -0.06; daily mean temperature below 0 C -0.03; mean wind above 10 m/s -0.03; snowfall above zero -0.03 only when the rain condition is not active. These are assumed probability-point changes, not estimated causal coefficients.

FORMULA: p(d) = clip(p_reference + c + delta(d), 0, 1)

Choose the scalar offset c by bisection so the mean planned probability over scheduling days equals the CSV reference. Boundary scheduling includes two buffer days on each side. Realised participation can be lower after schedule rejection; report that gap. Rain does not automatically create an extra screen-time budget. Humidity and cloud cover have no separate behavioural multipliers in this implementation.

---

# Time use evidence and distributions

The supplied table contains 56 overlapping activity categories, including broad totals. Participation is daily person participation, not a per-minute trigger or the chance that a household starts an appliance. Participant time is total daily human time among those participating. All-person time includes zero-minute nonparticipants.

FORMULA: mean_all approximately equals participation_probability * mean_participants

All 56 supplied rows reconcile within one minute after rounding. Do not sum parent categories with their children. The CSV contains no within-day timing, distribution shape, location, household correlations or machine programme duration. Apply these values as adult soft references; do not assign the very low aggregate school/homework participation to the children. Eurostat metadata describes the 2010 survey wave and lists Polish fieldwork as 2012-2013; exact export filters remain unverified.

## Optional adult activity proposals

Make one Bernoulli draw per adult, activity and local day. If successful, draw the total daily duration. The default gamma distribution produces positive, right-skewed durations; it is an assumption about variability, not a fitted Eurostat distribution.

FORMULA: I ~ Bernoulli(p); D | I=1 ~ Gamma(shape=1/CV^2, scale=mean*CV^2)

CV defaults to 0.25; mean is the CSV participant mean. Round to at least one integer minute. The distribution has expected mean equal to the source mean before rounding and schedule rejection. Uniform mode is also available, with half-width mean*CV*sqrt(3), giving the same unrounded mean and variance. Probability itself is not randomly redrawn from an unidentifiable beta distribution.

Implemented optional activities are cooking, washing-up, laundry care, cleaning, shopping, walking, visiting, helping a child, TV, computing and gaming. Their exact reference rows are mapped in behaviour.py. Other CSV rows are retained in the appendix but do not silently create events. Sleep, meals, school and work have explicit scheduling rules instead of independent aggregate participation draws.

Independent adult proposals are an initial assumption, then constrained by availability. Shared viewing and food preparation preserve person-minutes while one device uses elapsed minutes. Children have separate assumptions. Sample house parameters once per run, using bounded triangular or uniform distributions where configured; do not resample the building every day. Triangular low/mode/high are assumed bounds and central preference, not measured quantiles.

---

# Household schedules and activity constraints

Marek follows an assumed weekly morning/evening/night rotation anchored on Monday 2024-01-01. Shifts start Monday-Friday at 06:00, 14:00 or 22:00 and last eight hours. A night shift crosses midnight. On a public holiday retain a scheduled shift with probability 0.60. Ania works 08:00-16:00 on nonholiday weekdays, with two or three randomly selected home-working days per week, capped by eligible days. Her home-work breaks are 10:00-10:10, 12:30-13:00 and 15:00-15:10; only lunch is also reserved on office days.

Worker round-trip commuting time is Uniform(45,73) minutes, centred on the CSV 59-minute participant reference. Split that total between outward and return travel; do not give each leg 59 minutes. Reserve a 30-minute on-shift meal for Marek. No commute is generated for home-working days.

School starts at 08:00 on weekdays outside public/school holidays. School finish is sampled uniformly between 13:30 and 15:00, travel is 10-30 minutes each way, and lunch is 12:00-12:30 at school. These are assumptions. Ages and supervision requirements are unspecified: the model does not validate whether a child may safely stay home without an adult.

Adult sleep has a symmetric triangular daily budget with mean 492 minutes and bounds 462-522, informed by the CSV. Children use mean 540 with bounds 510-570. Place sleep around wake-up/work constraints. After a night shift Marek sleeps from 07:00 for his sampled budget; after an evening shift use a later wake time. Work has precedence over sleep at shift transitions. Record realised sleep instead of forcing a conflicting interval. Two buffer days on each boundary carry overnight activities into the retained period.

Eating is mandatory each day, overriding the 99.5% aggregate participation reference. Sample 78/93/108 minutes with a symmetric triangular distribution; include already scheduled off-site lunches, then place breakfast and remaining meals in free intervals. Personal care uses 41/56/71 minutes for adults and Uniform integer 35-55 for children. It is human care, not the shower duration. School/work meals remain away from home and cannot activate home equipment.

Child homework is 45-75 minutes on school days and 0-45 on free days. Recreational screen participation is 0.70/0.90, with 45-90/60-120 minutes respectively. Select TV, computing or gaming with equal weights. These are not Eurostat adult estimates.

Place optional adult chores in daytime/meal windows, leisure in free time and screens between 08:00 and 23:30, allowing pre-shift viewing. Split daily budgets into available runs of at least five minutes when allowed. Shopping, walks and visits need continuous time. Shopping and away visits also reserve separate round-trip travel, centred on 35 and 57 participant-minutes from the appropriate travel rows. Walking starts at the doorstep. Visiting is assumed equally likely at home or away. Child-help intervals require a child home and awake; they are not a detailed interaction model.

Reject an activity when the complete budget or required travel cannot fit; do not steal sleep or work time. Log proposed and accepted minutes. One resident has exactly one primary activity each minute, plus a separate home/away flag. Remaining minutes are explicitly residual free time, not invented household-care or leisure totals.

---

# Appliance rules and electrical accounting

Electrical power is stored at one-minute resolution. Energy for a full hour is the sum of minute kW divided by 60. Sum the mutually named appliance columns once to obtain total electricity. Passive solar gains warm the room but do not create electrical generation.

FORMULA: E_hour[kWh] = sum(P_minute[kW]) / 60

Fridge compressor runs 20 minutes in each 60-minute cycle with power normalised to 1.0 kWh per 24 physical hours. This regular compressor pattern is a simplified baseline. Router and aggregate standby use 0.012 and 0.040 kW continuously. Standby is an additional household category, not a second copy of configured active power.

Lighting is permitted only with an awake resident at home and low radiation. Switch the darkness state on below 70 W/m2 and off above 100 W/m2. Maximum lighting is 0.16 kW, scaled by awake residents up to three. Radiation is present throughout the supplied file, so no cloud fallback is currently needed.

TV is 0.11 kW while anyone watches or uses the console; console adds 0.15 kW. Desktop uses 0.18 kW for computing, and Ania's work laptop 0.06 kW during home work. Concurrent users are treated as shared device use; the model does not simulate screen ownership disputes. One TV display is counted once when console and TV requests overlap.

At a home breakfast opportunity before 11:00, start one shared kettle with probability 0.80 for 3-5 minutes at 2 kW, and one coffee maker with probability 0.50 for 5-10 minutes at 1.2 kW. These are household opportunities. In each morning/midday/evening cooking window choose cold/hob/oven/microwave with weights 0.10/0.55/0.20/0.15. Operating lengths are Uniform integer 15-35, 25-50 and 3-10 minutes, limited by the longest available household preparation segment. Powers are 2.0, 2.2 and 1.0 kW. Cold meals have no cooking electricity.

Laundry care participation is not a machine probability. On a day with at least ten adult laundry-care minutes, propose one or two sequential loads, limited by ten care minutes per load. Each washing cycle lasts 90 minutes and consumes Uniform(0.6,1.0) kWh. A dishwasher opportunity requires washing-up activity; probability is 0.60, at most one 150-minute programme per day, Uniform(0.8,1.2) kWh. Machine use does not occupy a person for the whole programme. Unloading can wait; precise task-level loading/unloading and inventory queues are simplified. No overlapping programmes on the same machine and no cycle beyond weather coverage are exported.

Cycle profiles use higher initial heating and later reheating phases; normalise the profile to the sampled kWh exactly. Vacuum use occupies 25% of adult cleaning minutes at 0.7 kW [ASSUMPTION: owned]. Each resident's portable device receives one evening charging session when home, 0.005-0.020 kWh over two hours. Boundary sessions are truncated, with only actual energy retained. Appliance event exports cover triggered devices; continuous and activity-mask loads are always available in hourly.csv.

---

# Space heating and building parameters

Represent the house as one well-mixed thermal zone. It is a reduced model, not an EnergyPlus building reconstruction. Fabric loss per floor area, air exchange, thermal capacitance and effective solar aperture are uncertain inputs. The complete default parameter catalogue follows this specification. In sample mode numeric values stay fixed, distributions are drawn once and overrides take precedence. In manual mode every distributed field must be supplied as a number or override; unresolved distributions cause an error.

FORMULA: C_house[kWh/K] = floor_area * capacity_Wh_per_m2K / 1000

FORMULA: H[kW/K] = (floor_area * fabric_W_per_m2K + 0.33 * volume_m3 * ACH) / 1000

Air exchange is base ACH plus wind_ach_per_ms times wind. When someone is awake at home, indoor temperature exceeds 25 C and outdoor air is cooler, add the configured window-opening ACH. This is a deterministic comfort assumption. There is no mechanical cooling. Weather may therefore cause summer overheating.

FORMULA: C * dT/dt = H*(T_out - T) + Q_heater + Q_solar + Q_internal

For each minute solve this linear equation analytically with piecewise-constant inputs. Let T_eq = T_out + Q_total/H. Then T_next = T_eq + (T - T_eq)*exp(-H*dt/C), where dt=1/60 hour. No arbitrary temperature clamp conceals insufficient heating capacity.

Setpoint is 21 C when someone is awake at home, 18.5 C when only sleeping residents are home, and 17 C when vacant. A hysteresis thermostat turns direct electric heating on below setpoint minus 0.3 C and off above setpoint plus 0.3 C; state persists between thresholds. Heat output is electrical power times efficiency, default 1.0. There is no temperature-dependent COP because this is not a heat pump.

The default whole-house heater is capped at 3.5 kW, retaining the upper indicative organiser example. This may be undersized for a detached house. Increase it only as an explicit scenario/manual change; do not automatically size it to hide discomfort. Report occupied shortfall below the lower thermostat band in degree-hours, hours with shortfall, and indoor minima/maxima. A shortfall near recovery periods differs from sustained capacity shortage; inspect the time series.

Solar gain equals effective solar area times instantaneous shortwave radiation, divided by 1000. Apply a shading factor of 0.35 in May-September and 1 otherwise. This includes no PV. Internal sensible gains are 75 W per awake resident, 55 W per sleeping resident, 65% of nonthermal appliance electricity, and tank standing losses. These are explicit approximations, including simplified treatment of equipment heat released outside conditioned space.

Warm up the building and tank using the first seven available days once, then restart the weather sequence for the retained simulation with those final thermal states. Warm-up energy is discarded. This synthetic conditioning segment is not extra observed weather. Thermal state is continuous through all retained hours and across New Year.

---

# Electric boiler and hot water

Use a well-mixed tank, default sampled volume 120-200 litres with triangular mode 150, a 2 kW resistance element, 1.6 W/K standing-loss coefficient and 55 C thermostat setpoint. Turn on below 50 C and off at 55 C. One-minute hysteresis may produce a small overshoot; do not reset tank temperature after draws.

FORMULA: C_tank[kWh/K] = volume_litres * 0.001163

Shower participation is an assumed 0.85 per resident-day. Sample a triangular 4/7/10-minute length at 6 litres/minute, limited to a contiguous existing personal-care segment. Add up to three litres of washbasin use per resident-day and up to six litres of kitchen wash-up water within washing-up activity. These hot-water rules are assumptions; the time-use table does not identify litres or shower rates.

Requested delivery temperature is 40 C. Mains temperature is an assumed annual sinusoid: 10 + 5*sin(2*pi*(day_of_year-120)/365.25). It is not fitted to supplied outdoor temperatures. The mixing valve supplies the requested energy while tank temperature exceeds delivery temperature; after that, pure tank draws mix with cold replenishment and the tank cools exponentially with draw volume. Report the energy deficit relative to requested 40 C delivery. Water and energy are conserved in this approximation; no infinite supply of hot water is assumed.

FORMULA: requested_heat[kWh] = mixed_litres * 0.001163 * (40 - T_mains)

After the draw, solve tank heating and ambient losses analytically for the minute. Ambient temperature is the current indoor zone temperature. Add actual tank standing loss to zone internal heat. Export tank mean/minimum temperature, water-heater electricity, requested mixed litres and unmet hot-water heat. The unmet quantity is a diagnostic, never an additional electricity load.

---

# Validation and limits of interpretation

Check unique uninterrupted UTC hours, nonnegative finite electricity, exact summation of device categories, 60 exclusive activity minutes for each resident-hour, finite temperatures and equipment capacity limits. Unit tests additionally check DST day lengths, ordinary missing-weather rejection, fixed manual parameters, deterministic schedules, exact cycle energy and analytic RC time-step consistency. These checks establish internal consistency, not empirical realism.

For each adult and implemented reference activity, compare realised daily participation, all-day mean minutes and participant-day mean minutes against Eurostat. Include zero-minute days. Source means are population references, not exact targets for this employed family. Report rejected optional minutes and keep daily proposals. Do not quietly increase every activity probability until incompatible budgets appear to match. Children are not benchmarked against adult rates.

Use the dashboard to inspect individual devices, aggregate peaks, sleep and activity patterns, occupancy, annual seasonality, cold-weather saturation, tank recovery, and source-reference deviations. Redesign assumptions if the scenario is implausible. A plausible annual total alone cannot validate timing or individual appliances.

Material limits include a single thermal zone; no cooling plant; assumed shift roster and work attendance; no sickness or annual leave; no age-specific child supervision; independent adult proposals; simplified shared devices, loading/unloading and fridge cycling; no observed duration distribution; outdated technology behaviour in the survey reference; and approximate conversion of instantaneous radiation to hourly heat gain. Parameters and data must be calibrated before claiming a validated digital twin.

## Sources

User-supplied activity_time_use_full.csv, silesia_weather_full.csv, public/school calendar text files and user confirmations. Source hashes are saved in validation.json.

HackoWatt-Scenario-2-A-Silesian-Family-Home.pdf; HackoWatt-Common-Challenge-Assumptions.pdf; HackoWatt_Two_Model_Architectures.pdf; Richardson_Lekhel_HackoWatt_Guide_v2.pdf; RULES_FOR_ENGY_CONSUMP.docx. Pensioner example schedules do not define this family's behaviour. Challenge renewable-generation instructions are deferred by the user's explicit current scope.

Eurostat HETUS metadata, indicator definitions and wave context: https://ec.europa.eu/eurostat/cache/metadata/en/tus_00_esms.htm

Polish Ministry, Christmas Eve holiday from 2025: https://www.gov.pl/web/rodzina/wolna-wigilia-od-przyszlego-roku

EnergyPlus Engineering Reference, zone heat balance and mixed water thermal storage, conceptual reference only; this code implements a reduced model: https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v24.2.0/EngineeringReference.pdf

The following parameter catalogue is generated directly from config/default.json and the source appendix directly from the supplied CSV. Edit those files and rerun tools/build_rules.py to keep the PDF consistent.
