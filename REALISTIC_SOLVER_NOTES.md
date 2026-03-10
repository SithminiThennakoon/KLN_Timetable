## Full Realistic Dataset: What Was Required To Make Generation Work

### Final Outcome

The full cleaned realistic dataset now generates successfully through the real `generate_timetables(...)` flow.

Verified working result on a clean temporary SQLite database:

- status: `optimal`
- solutions found: `1`
- solver engine: `decomposed_exact`
- task count: `442`
- room assignment retries: `0`
- total runtime: about `8.7s`
- solve time: about `6.8s`

Successful generation configuration:

- `performance_preset = "balanced"`
- `max_solutions = 1`
- `preview_limit = 1`
- `time_limit_seconds = 45`

### What Was Wrong Initially

The first failures were a mix of real data problems and solver/model problems.

#### 1. The dataset was over-modeling EC / BECS demand

The realistic builder was treating some BECS registrations as mandatory weekly timetable load for the full cohort.

That produced impossible parent-cohort weekly loads such as:

- `EC Y1 Batch 2022 Path 1` -> `52h`
- `EC Y2 Batch 2021 Path 1` -> `60h`

#### 2. BECS lab inference was too broad

The builder was inferring labs from the `BECS` prefix as if all BECS modules had labs.

Public curriculum evidence showed that only explicit BECS lab modules should create lab sessions.

#### 3. The realistic room seed was far too small

The earlier seed effectively modeled a faculty-wide timetable with:

- one chemistry lab
- one physics lab
- one electronics lab
- too few lecture and computing/statistics rooms

That was not realistic for the actual faculty scale.

#### 4. The decomposed solver was generating impossible day layouts

The large-dataset decomposed solver originally let stage 1 place tasks into day/time slots without enough exact room-capacity knowledge.

That meant exact room assignment kept failing later even when the time assignment looked feasible.

### What We Changed

#### Data interpretation fixes

In [backend/app/services/enrollment_inference.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/services/enrollment_inference.py):

- filtered audited optional BECS modules out of the default mandatory realistic dataset
- removed blanket synthetic BECS lab generation
- replaced it with explicit BECS lab-module mapping

#### Realistic room inventory fixes

The realistic seed was expanded to a more credible faculty-scale inventory.

Current seed:

- `15` lecture rooms
- `5` electronics labs
- `4` computer labs
- `3` chemistry labs
- `3` physics labs
- `2` statistics labs
- `1` biology lab

These changes were driven by:

- measured exact room-assignment failures in produced day layouts
- public faculty context showing the original single-lab-per-discipline seed was too pessimistic

#### Solver safety and diagnostics

In [backend/app/services/timetable_v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/services/timetable_v2.py):

- added resource-limited guardrails so generation fails safely instead of risking uncontrolled OOM
- added generation stats for:
  - assignment/candidate counts
  - slot-variable counts
  - solver engine
  - room-assignment retry counts
  - room-assignment timing
  - domain reduction ratio

Related schema/UI changes:

- [backend/app/schemas/v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/schemas/v2.py)
- [frontend/src/pages/GenerateStudio.jsx](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/pages/GenerateStudio.jsx)

#### Large-dataset solver refactor

The large realistic dataset now uses the decomposed exact solver path:

- stage 1 solves on day/time slot variables
- stage 2 performs exact room assignment

Important solver changes:

- aggregated student-group conflict handling
- singleton-room capacity constraints in stage 1
- exact room-pool capacity constraints where a task’s eligible rooms all belong to one room pool
- improved room-matching search heuristic
- improved CP-SAT decision ordering for tight tasks

This combination is what finally allowed the full realistic dataset to solve.

### Compromises We Made

These are the deliberate compromises/tradeoffs that got the full dataset working.

#### 1. We cleaned the dataset interpretation instead of treating raw enrollment as ground truth

Compromise:

- the default realistic demo no longer treats every observed enrollment as mandatory timetable demand

Why:

- raw enrollment data was overloading cohorts in ways that did not match actual weekly timetable commitment

Impact:

- the dataset is still realistic, but it is a curated timetable-demand dataset rather than a literal registration dump

#### 2. We made the room seed more generous than the original demo

Compromise:

- the realistic demo room inventory is no longer minimal

Why:

- the original room seed was clearly too small for faculty-wide scheduling and caused artificial infeasibility

Impact:

- generation now reflects a more plausible faculty-scale room model
- but the exact room names/counts are still a modeled approximation, not a formally audited estate register

#### 3. We optimized for one feasible timetable, not exhaustive enumeration

Compromise:

- the successful path is a feasible-first, bounded solve
- we are not enumerating large numbers of solutions on the full dataset

Why:

- full enumeration at this scale is unnecessary for operational success and is much more expensive

Impact:

- generation is practical and fast for the full realistic dataset
- but the system is currently optimized for obtaining a valid timetable, not proving or listing many alternatives

#### 4. We rely on the decomposed exact solver path for large datasets

Compromise:

- large datasets are solved with a staged time-then-room approach rather than the original flat room-time model

Why:

- the flat large model was much more memory-hungry and less tractable on this machine

Impact:

- semantics are preserved for exact room assignment
- but the internal solver architecture is now more complex

### What Finally Worked

The final working combination was:

1. clean the realistic dataset interpretation
2. remove fake BECS labs
3. expand the faculty room seed to a plausible scale
4. use the decomposed exact solver
5. add exact safe room-pool capacity constraints in stage 1
6. run the full solve with the normal API path using the `balanced` preset

The final verified successful generation call was effectively:

```python
run = generate_timetables(
    db,
    [],
    1,
    1,
    45,
    performance_preset="balanced",
)
```

### Files Touched For This Work

- [backend/app/services/enrollment_inference.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/services/enrollment_inference.py)
- [backend/app/services/timetable_v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/services/timetable_v2.py)
- [backend/app/schemas/v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/app/schemas/v2.py)
- [backend/tests/test_timetable_v2.py](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/backend/tests/test_timetable_v2.py)
- [frontend/src/pages/GenerateStudio.jsx](/home/sasindu/Documents/Projects/UOK Sithu Timetable/KLN_Timetable/frontend/src/pages/GenerateStudio.jsx)

### Residual Caveats

- The old enrollment inference semester test still needs updating if it should reflect the intended single-semester realistic builder behavior.
- The realistic room seed is now much better, but it is still a modeled approximation.
- The solver is now good enough to generate a valid full timetable on this machine, but very large future dataset changes may still require more tuning.
