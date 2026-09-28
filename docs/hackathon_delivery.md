# HackoWatt delivery and presentation plan

Source: participant guide supplied by the team, covering 28–30 September 2026.
All organiser times below are CEST (UTC+2). Vilnius is one hour ahead on these dates.

## Submission

**Deadline: Tuesday 29 September 2026, 11:00 CEST / 12:00 Vilnius.**

Submit to the individual team folder sent by the organisers on Monday:

- [ ] Final solution/source and reproducible launch instructions.
- [ ] Approximately five-minute video showing the working solution and key features.
- [ ] Short presentation or document: use `docs/submission_brief.md` as the draft.
- [x] Include the offline application and its separate HTML/PDF methodology handbook.
- [ ] Check the final video opens, has readable text/audio and fits approximately five minutes.
- [ ] Test the copied application on the actual demo computer without network access.
- [ ] Verify all files are in the team's own submission folder before the deadline.

The application and documentation are prepared; this checklist does not imply
that a video has been recorded or that anything has been uploaded to the organisers.
Keep individual submission links and meeting access details out of the public repository.

## Organiser schedule

| Date | CEST | Event |
|---|---|---|
| Monday 28 September | 10:00 | Opening on Microsoft Teams |
| Monday 28 September | 11:00 | Scenarios/API links released; building starts |
| Monday 28 September | 11:00–20:00 | Mentoring on-site and Discord |
| Tuesday 29 September | 11:00 | Submission deadline |
| Tuesday 29 September | 11:00–20:00 | Mentoring; final preparation |
| Wednesday 30 September | 10:00 | Eight finalist teams announced; presentations and Q&A |
| Wednesday 30 September | 13:30 | Results and awards |

Discord is the announcement/mentor channel; Teams is the online backup.
Teams consist of 2–5 individually registered members. On-site location is
SpinPLACE, University of Silesia, Bankowa 5, Katowice. Bring laptops and chargers.
Use the team's supplied Discord and Teams links; no accounts have been joined
or external messages sent as part of this implementation.

## Match the judging criteria

| Criterion | Points | Concrete evidence to show |
|---|---:|---|
| Innovation & creativity | 30 | Connect investment, editable family constraints and heat storage; show one explained decision and a realistic development path |
| Functionality & usability | 30 | Change panel size and immediately show effects; lock a recommendation; use a device view, larger text and tables |
| Technical implementation | 20 | Explain UTC contracts, conservation of energy, forecast error, temperature constraints and reproducible checks |
| Presentation & justification | 20 | Tell one family story, distinguish assumptions from evidence and answer where every constant came from |

Do not claim that the design is unique or superior to unknown competing entries.
Demonstrate the working differences and explain the tradeoffs.

## Five-minute submission video

Use the timed walkthrough in `src/hackowatt/simulator_methodology.html`, section 18:
family problem → useful appliance move → solar A/B comparison → presence/comfort
→ forecast quality → traceable assumptions. Keep the default June replay for a
clear appliance example. State that history is synthetic and the forecast is a
saved validation run. Keep one screen readable rather than rapidly switching tabs.

## Eight-minute finalist presentation + two-minute Q&A

| Time | Focus |
|---|---|
| 0:00–0:45 | The family's problem and the one-sentence product promise |
| 0:45–2:15 | Daily graph, recommendation, user override and device focus |
| 2:15–3:30 | Required solar metrics, multiple capacities and A/B payback |
| 3:30–4:45 | Presence and thermal state: why heating cannot be moved like laundry |
| 4:45–5:45 | Forecast results, visible error and the colleague-model integration contract |
| 5:45–6:45 | Energy accounting, financial assumptions, sources and accessibility |
| 6:45–7:30 | Real deployment: calibration, issued weather, service layer and billing |
| 7:30–8:00 | Return to one concrete family decision and its demonstrated benefit |
| Next 2 minutes | Jury Q&A; keep the handbook ready for formulas and constants |

Assign one presenter to the narrative and one to operate the demo. Rehearse the
timed route and prepare the offline files in case the network fails. Use the
handbook's questions on installation price, TV sharing, optimality, energy versus
cost and live-data limitations as rehearsal prompts.

## Regulations and third-party material

The supplied guide explicitly asks participants to read the official regulations,
especially intellectual property, solution ownership and third-party tools.
The full regulations have not been supplied here or verified in this change.
Before submission, the team should obtain the official text and confirm these
conditions. Do not infer them from an invitation email.

Keep source attribution for organiser PDFs, weather, cited research and external
services. Check the repository/dependency licences and any provider's usage terms
for the team's actual delivery. The handbook links research to the model family
without suggesting endorsement. No external illustration assets were added; the
interface uses authored CSS, SVG icons and computed charts. Disclose AI-assisted
development if the official rules require it.
