# Gold Set Verification Worksheet

A stratified random sample of **16** cases out of the full 100-case `data/gold_set.json`, covering every category (random seed 42, up to 3 per category).

**Purpose**: independently derive the expected eligibility for each case below, using ONLY the student profile and raw messages shown — not the gold set's own `expected_*` fields, not the database, not `rules/evaluators/*.py` or `reconciliation/temporal_provenance_engine.py`. Apply only the stated rules: higher authority rank wins regardless of recency; among same-rank sources, an explicit correction (or otherwise the latest timestamp) wins; CGPA/percentage thresholds are minimums; backlog limits are maximums; branch lists are exact-match; any criterion with no stated rule is simply not checked; missing student data for a checked criterion means UNKNOWN unless something else already fails outright.

Each case below shows the raw input (student profile + messages) followed by `data/gold_set.json`'s own expected answer and reasoning for that case. To do a **blind** pass, work out your own ELIGIBLE / INELIGIBLE / UNKNOWN answer from the raw input before reading the "Expected answer" section, then compare.

---

## CASE_001

**Drive:** `DRIVE_VERTEXSOFT`  |  **Student:** `1MS22CS001`

### Student profile

- USN: `1MS22CS001`
- Name: Aarav Sharma
- Date of birth: 2003-01-15
- CGPA: 8.72
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 88.4
- 12th percentage: 82.0

### Messages (chronological order)

1. **[2026-10-20T10:00:00] placement_cell_email** (source_id: `email_vertexsoft_001`)

> VertexSoft Solutions — Campus Hiring 2027
> 
> Role: Associate Software Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 7.5 and above
> Branches eligible: CSE, ISE only
> No active backlogs
> 
> Compensation: 6.5 LPA
> Location: Bangalore
> 
> Link to apply: https://forms.gle/vxs2027reg
> Deadline: 23-10-2026, 6 PM
> 
> — Placement Department RIT

2. **[2026-10-21T09:30:00] placement_cell_whatsapp** (source_id: `whatsapp_vertexsoft_001`)

> VertexSoft
> 
> Correction: the CGPA requirement is 7.0, not 7.5, as stated in the earlier email. Branches and backlog rule stay the same (CSE, ISE only, no active backlogs).
> 
> — Placement Cell

3. **[2026-10-23T08:00:00] student_whatsapp** (source_id: `student_whatsapp_vertexsoft_001`)

> Fwd: VertexSoft Solutions — Campus Hiring 2027
> 
> Role: Associate Software Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 7.5 and above
> Branches eligible: CSE, ISE only
> No active backlogs
> 
> Compensation: 6.5 LPA
> Location: Bangalore
> 
> Link to apply: https://forms.gle/vxs2027reg
> Deadline: 23-10-2026, 6 PM

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** temporal_conflict
**Temporal reasoning required:** True
**Provenance reasoning required:** True

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `whatsapp_vertexsoft_001`
- `allowed_branches` in `['CSE', 'ISE']` — authoritative source: `whatsapp_vertexsoft_001`
- `max_backlogs` lte `0` — authoritative source: `whatsapp_vertexsoft_001`

**Description:** WhatsApp correction lowers CGPA to 7.0; old forward (rank5) must be ignored.

**Notes:** Rank-2 WhatsApp correction beats rank-2 email on is_correction; rank-5 forward never wins; backlogs/branches resolve to the chronologically latest rank-2 restatement.


---

## CASE_006

**Drive:** `DRIVE_BRIGHTWAVE`  |  **Student:** `1MS22CS020`

### Student profile

- USN: `1MS22CS020`
- Name: Ishita Banerjee
- Date of birth: 2003-08-14
- CGPA: 8.88
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 89.0
- 12th percentage: 86.5

### Messages (chronological order)

1. **[2026-10-18T09:00:00] official_company_pdf** (source_id: `pdf_brightwave_001`)

> BrightWave Technologies — Official Eligibility Criteria (Campus Recruitment 2027)
> 
> This document is the official and final eligibility criteria for the BrightWave Technologies campus drive.
> 
> Eligibility Criteria:
> Minimum CGPA: 7.5 and above
> Eligible Branches: CSE, ISE only
> Backlogs: No active backlogs permitted
> 
> Role: Graduate Engineer Trainee
> Compensation: 9 LPA
> 
> Any communication from other channels that conflicts with this document should be disregarded.
> 
> — BrightWave Technologies, Campus Recruitment Team

2. **[2026-10-19T14:00:00] coordinator_whatsapp** (source_id: `coordinator_whatsapp_brightwave_001`)

> Hi all, heard from a senior that BrightWave is actually open to all branches this year and the CGPA cutoff is only 6.5, no backlog restriction either. Will confirm but thought I'd give you a heads up.
> 
> — Placement Coordinator

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** conflicting_sources
**Temporal reasoning required:** False
**Provenance reasoning required:** True

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.5` — authoritative source: `pdf_brightwave_001`
- `allowed_branches` in `['CSE', 'ISE']` — authoritative source: `pdf_brightwave_001`
- `max_backlogs` lte `0` — authoritative source: `pdf_brightwave_001`

**Description:** Official PDF (rank1) beats conflicting coordinator rumor (rank3).


---

## CASE_019

**Drive:** `DRIVE_SILVERLINE`  |  **Student:** `1MS22EC042`

### Student profile

- USN: `1MS22EC042`
- Name: Mihika Rane
- Date of birth: 2003-02-23
- CGPA: 8.6
- Branch: ECE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 85.0
- 12th percentage: 82.0

### Messages (chronological order)

1. **[2026-10-16T10:00:00] placement_cell_email** (source_id: `email_silverline_001`)

> SilverLine Analytics — Campus Hiring 2027
> 
> Role: Data Analyst
> 
> Eligibility Criteria:
> Minimum CGPA: 7.0 and above
> Branches eligible: CSE, ISE only
> No active backlogs
> 
> Compensation: 7 LPA
> 
> Link to apply: https://forms.gle/silverline2027
> Deadline: 21-10-2026, 5 PM
> 
> — Placement Department RIT

2. **[2026-10-18T12:00:00] placement_cell_whatsapp** (source_id: `whatsapp_silverline_001`)

> SilverLine
> 
> Correction: the full and final list of eligible branches is CSE, ISE and ECE (updated list, replaces the branches mentioned earlier). CGPA (7.0+) and backlog rule (no active backlogs) stay the same.
> 
> — Placement Cell

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** temporal_conflict
**Temporal reasoning required:** True
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `email_silverline_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE']` — authoritative source: `whatsapp_silverline_001`
- `max_backlogs` lte `0` — authoritative source: `email_silverline_001`

**Description:** WhatsApp correction adds ECE to the eligible branch list.


---

## CASE_023

**Drive:** `DRIVE_NIMBUSWORKS`  |  **Student:** `1MS22EC018`

### Student profile

- USN: `1MS22EC018`
- Name: Kavya Pillai
- Date of birth: 2003-09-19
- CGPA: 8.15
- Branch: ECE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 82.0
- 12th percentage: 79.0

### Messages (chronological order)

1. **[2026-10-14T10:00:00] placement_cell_email** (source_id: `email_nimbusworks_001`)

> NimbusWorks Cloud — Campus Hiring 2027
> 
> Role: Cloud Support Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 6.5 and above
> Branches eligible: CSE, ECE, ISE
> 
> Compensation: 6 LPA
> 
> Link to apply: https://forms.gle/nimbusworks2027
> Deadline: 19-10-2026, 5 PM
> 
> — Placement Department RIT

2. **[2026-10-16T15:00:00] placement_cell_whatsapp** (source_id: `whatsapp_nimbusworks_001`)

> NimbusWorks
> 
> Correction: the full and final list of eligible branches is CSE and ECE only — ISE has been removed from eligibility. CGPA requirement (6.5+) is unchanged.
> 
> — Placement Cell

3. **[2026-10-20T21:00:00] student_whatsapp** (source_id: `student_whatsapp_nimbusworks_001`)

> Fwd: NimbusWorks Cloud — Campus Hiring 2027
> 
> Role: Cloud Support Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 6.5 and above
> Branches eligible: CSE, ECE, ISE
> 
> Compensation: 6 LPA
> 
> Link to apply: https://forms.gle/nimbusworks2027
> Deadline: 19-10-2026, 5 PM

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** normal
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `6.5` — authoritative source: `email_nimbusworks_001`
- `allowed_branches` in `['CSE', 'ECE']` — authoritative source: `whatsapp_nimbusworks_001`

**Description:** ECE still eligible after the branch correction.


---

## CASE_024

**Drive:** `DRIVE_NIMBUSWORKS`  |  **Student:** `1MS22IS025`

### Student profile

- USN: `1MS22IS025`
- Name: Aditya Pandey
- Date of birth: 2003-12-15
- CGPA: 7.42
- Branch: ISE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 74.0
- 12th percentage: 71.0

### Messages (chronological order)

1. **[2026-10-14T10:00:00] placement_cell_email** (source_id: `email_nimbusworks_001`)

> NimbusWorks Cloud — Campus Hiring 2027
> 
> Role: Cloud Support Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 6.5 and above
> Branches eligible: CSE, ECE, ISE
> 
> Compensation: 6 LPA
> 
> Link to apply: https://forms.gle/nimbusworks2027
> Deadline: 19-10-2026, 5 PM
> 
> — Placement Department RIT

2. **[2026-10-16T15:00:00] placement_cell_whatsapp** (source_id: `whatsapp_nimbusworks_001`)

> NimbusWorks
> 
> Correction: the full and final list of eligible branches is CSE and ECE only — ISE has been removed from eligibility. CGPA requirement (6.5+) is unchanged.
> 
> — Placement Cell

3. **[2026-10-20T21:00:00] student_whatsapp** (source_id: `student_whatsapp_nimbusworks_001`)

> Fwd: NimbusWorks Cloud — Campus Hiring 2027
> 
> Role: Cloud Support Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 6.5 and above
> Branches eligible: CSE, ECE, ISE
> 
> Compensation: 6 LPA
> 
> Link to apply: https://forms.gle/nimbusworks2027
> Deadline: 19-10-2026, 5 PM

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** outdated_forwarded
**Temporal reasoning required:** True
**Provenance reasoning required:** True

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `6.5` — authoritative source: `email_nimbusworks_001`
- `allowed_branches` in `['CSE', 'ECE']` — authoritative source: `whatsapp_nimbusworks_001`

**Description:** ISE was removed by the official correction; the student-forwarded old email (listing ISE) must be ignored.

**Notes:** Naive forward-trusting logic would wrongly say ELIGIBLE; correct answer is INELIGIBLE.


---

## CASE_027

**Drive:** `DRIVE_PRISMATIC`  |  **Student:** `1MS22CS013`

### Student profile

- USN: `1MS22CS013`
- Name: Siddharth Gupta
- Date of birth: 2003-01-01
- CGPA: 9.5
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 96.0
- 12th percentage: 93.0

### Messages (chronological order)

1. **[2026-10-12T10:00:00] placement_cell_email** (source_id: `email_prismatic_001`)

> Prismatic Dynamics — Campus Hiring 2027
> 
> Role: Product Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 8.5 and above
> Branches eligible: CSE, ISE, ECE, EEE
> No active backlogs
> Minimum 75% in 10th and 12th
> 
> Compensation: 11 LPA
> 
> Link to apply: https://forms.gle/prismatic2027
> Deadline: 16-10-2026, 5 PM
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** multi_condition
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `8.5` — authoritative source: `email_prismatic_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE', 'EEE']` — authoritative source: `email_prismatic_001`
- `max_backlogs` lte `0` — authoritative source: `email_prismatic_001`
- `min_10th_pct` gte `75` — authoritative source: `email_prismatic_001`
- `min_12th_pct` gte `75` — authoritative source: `email_prismatic_001`

**Description:** Meets all 5 criteria.


---

## CASE_030

**Drive:** `DRIVE_PRISMATIC`  |  **Student:** `1MS22EC026`

### Student profile

- USN: `1MS22EC026`
- Name: Shreya Menon
- Date of birth: 2003-03-11
- CGPA: 8.35
- Branch: ECE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 84.0
- 12th percentage: 81.0

### Messages (chronological order)

1. **[2026-10-12T10:00:00] placement_cell_email** (source_id: `email_prismatic_001`)

> Prismatic Dynamics — Campus Hiring 2027
> 
> Role: Product Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 8.5 and above
> Branches eligible: CSE, ISE, ECE, EEE
> No active backlogs
> Minimum 75% in 10th and 12th
> 
> Compensation: 11 LPA
> 
> Link to apply: https://forms.gle/prismatic2027
> Deadline: 16-10-2026, 5 PM
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** multi_condition
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `8.5` — authoritative source: `email_prismatic_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE', 'EEE']` — authoritative source: `email_prismatic_001`
- `max_backlogs` lte `0` — authoritative source: `email_prismatic_001`
- `min_10th_pct` gte `75` — authoritative source: `email_prismatic_001`
- `min_12th_pct` gte `75` — authoritative source: `email_prismatic_001`

**Description:** CGPA 8.35 < 8.5 -- narrow miss.


---

## CASE_033

**Drive:** `DRIVE_QUANTUMEDGE`  |  **Student:** `1MS22IS017`

### Student profile

- USN: `1MS22IS017`
- Name: Amit Tiwari
- Date of birth: 2003-05-03
- CGPA: 7.78
- Branch: ISE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 77.5
- 12th percentage: 74.8

### Messages (chronological order)

1. **[2026-10-08T00:00:00] student_portal** (source_id: `portal_SIS_QUANTUMEDGE_001`)

> === QuantumEdge Systems ===
> 
> Position: Platform Engineer
> Role: Platform Engineer
> Type: Full Time Employment
> Package: 8.5 LPA
> 
> Eligibility Criteria:
> CGPA 7.0 and above. Open to all branches.
> 
> Application Deadline: 20-10-2026 05:00 PM
> Event Date: 01-11-2026
> 
> Work Mode: Onsite
> Preferred Skills: Distributed Systems, Go, Kubernetes
> 
> Status: OPEN
> Posted: 2 days ago

2. **[2026-10-10T09:00:00] official_company_pdf** (source_id: `pdf_quantumedge_001`)

> QuantumEdge Systems — Official Eligibility Criteria (Campus Recruitment 2027)
> 
> This document is the official and final eligibility criteria for the QuantumEdge Systems campus drive.
> 
> Eligibility Criteria:
> Minimum CGPA: 7.0 and above
> Eligible Branches: CSE, ISE only
> Backlogs: No active backlogs permitted
> 
> Role: Platform Engineer
> Compensation: 8.5 LPA
> 
> Any communication from other channels that conflicts with this document should be disregarded.
> 
> — QuantumEdge Systems, Campus Recruitment Team

3. **[2026-10-15T20:00:00] student_whatsapp** (source_id: `student_whatsapp_quantumedge_001`)

> heard from a friend that quantumedge cutoff is only 6.0 CGPA and its open to all branches this time, can anyone confirm?

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** conflicting_sources
**Temporal reasoning required:** False
**Provenance reasoning required:** True

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `pdf_quantumedge_001`
- `allowed_branches` in `['CSE', 'ISE']` — authoritative source: `pdf_quantumedge_001`
- `max_backlogs` lte `0` — authoritative source: `pdf_quantumedge_001`

**Description:** PDF wins over portal's 'open to all' and the rumor's CGPA 6.0, regardless of recency.


---

## CASE_034

**Drive:** `DRIVE_QUANTUMEDGE`  |  **Student:** `1MS22CS016`

### Student profile

- USN: `1MS22CS016`
- Name: Meera Iyer
- Date of birth: 2003-11-12
- CGPA: 6.8
- Branch: CSE
- Backlogs: 1
- Has prior offer: False
- 10th percentage: 68.0
- 12th percentage: 65.0

### Messages (chronological order)

1. **[2026-10-08T00:00:00] student_portal** (source_id: `portal_SIS_QUANTUMEDGE_001`)

> === QuantumEdge Systems ===
> 
> Position: Platform Engineer
> Role: Platform Engineer
> Type: Full Time Employment
> Package: 8.5 LPA
> 
> Eligibility Criteria:
> CGPA 7.0 and above. Open to all branches.
> 
> Application Deadline: 20-10-2026 05:00 PM
> Event Date: 01-11-2026
> 
> Work Mode: Onsite
> Preferred Skills: Distributed Systems, Go, Kubernetes
> 
> Status: OPEN
> Posted: 2 days ago

2. **[2026-10-10T09:00:00] official_company_pdf** (source_id: `pdf_quantumedge_001`)

> QuantumEdge Systems — Official Eligibility Criteria (Campus Recruitment 2027)
> 
> This document is the official and final eligibility criteria for the QuantumEdge Systems campus drive.
> 
> Eligibility Criteria:
> Minimum CGPA: 7.0 and above
> Eligible Branches: CSE, ISE only
> Backlogs: No active backlogs permitted
> 
> Role: Platform Engineer
> Compensation: 8.5 LPA
> 
> Any communication from other channels that conflicts with this document should be disregarded.
> 
> — QuantumEdge Systems, Campus Recruitment Team

3. **[2026-10-15T20:00:00] student_whatsapp** (source_id: `student_whatsapp_quantumedge_001`)

> heard from a friend that quantumedge cutoff is only 6.0 CGPA and its open to all branches this time, can anyone confirm?

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** conflicting_sources
**Temporal reasoning required:** False
**Provenance reasoning required:** True

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `pdf_quantumedge_001`
- `allowed_branches` in `['CSE', 'ISE']` — authoritative source: `pdf_quantumedge_001`
- `max_backlogs` lte `0` — authoritative source: `pdf_quantumedge_001`

**Description:** Fails CGPA and backlog under the authoritative PDF rule.


---

## CASE_037

**Drive:** `DRIVE_HALCYON`  |  **Student:** `1MS22IS032`

### Student profile

- USN: `1MS22IS032`
- Name: Simran Kaur
- Date of birth: 2003-06-30
- CGPA: 7.6
- Branch: ISE
- Backlogs: 0
- Has prior offer: **(not on record)**
- 10th percentage: 76.0
- 12th percentage: 73.0

### Messages (chronological order)

1. **[2026-10-11T10:00:00] placement_cell_email** (source_id: `email_halcyon_001`)

> Halcyon Robotics — Campus Hiring 2027
> 
> Role: Robotics Engineer Trainee
> 
> Eligibility Criteria:
> Minimum CGPA: 7.0 and above
> Branches eligible: CSE, ISE, ECE, MECH
> No active backlogs
> Minimum 65% in 10th and 12th
> Students with an existing offer are not eligible to apply
> 
> Compensation: 7.5 LPA
> 
> Link to apply: https://forms.gle/halcyon2027
> Deadline: 15-10-2026, 5 PM
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** UNKNOWN
**Expected UNKNOWN case:** True
**Category:** missing_info
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `email_halcyon_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE', 'MECH']` — authoritative source: `email_halcyon_001`
- `max_backlogs` lte `0` — authoritative source: `email_halcyon_001`
- `min_10th_pct` gte `65` — authoritative source: `email_halcyon_001`
- `min_12th_pct` gte `65` — authoritative source: `email_halcyon_001`
- `no_prior_offer` eq `False` — authoritative source: `email_halcyon_001`

**Description:** has_prior_offer is null -> UNKNOWN.


---

## CASE_038

**Drive:** `DRIVE_HALCYON`  |  **Student:** `1MS22CS033`

### Student profile

- USN: `1MS22CS033`
- Name: Harsh Vardhan
- Date of birth: 2003-08-17
- CGPA: 8.1
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: **(not on record)**
- 12th percentage: 79.0

### Messages (chronological order)

1. **[2026-10-11T10:00:00] placement_cell_email** (source_id: `email_halcyon_001`)

> Halcyon Robotics — Campus Hiring 2027
> 
> Role: Robotics Engineer Trainee
> 
> Eligibility Criteria:
> Minimum CGPA: 7.0 and above
> Branches eligible: CSE, ISE, ECE, MECH
> No active backlogs
> Minimum 65% in 10th and 12th
> Students with an existing offer are not eligible to apply
> 
> Compensation: 7.5 LPA
> 
> Link to apply: https://forms.gle/halcyon2027
> Deadline: 15-10-2026, 5 PM
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** UNKNOWN
**Expected UNKNOWN case:** True
**Category:** missing_info
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.0` — authoritative source: `email_halcyon_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE', 'MECH']` — authoritative source: `email_halcyon_001`
- `max_backlogs` lte `0` — authoritative source: `email_halcyon_001`
- `min_10th_pct` gte `65` — authoritative source: `email_halcyon_001`
- `min_12th_pct` gte `65` — authoritative source: `email_halcyon_001`
- `no_prior_offer` eq `False` — authoritative source: `email_halcyon_001`

**Description:** 10th% is null -> UNKNOWN.


---

## CASE_044

**Drive:** `DRIVE_FERROLINE`  |  **Student:** `1MS22ET023`

### Student profile

- USN: `1MS22ET023`
- Name: Nikhil Rao
- Date of birth: 2003-06-21
- CGPA: 7.55
- Branch: ETE
- Backlogs: 1
- Has prior offer: False
- 10th percentage: 75.0
- 12th percentage: 72.0

### Messages (chronological order)

1. **[2026-10-13T10:00:00] placement_cell_email** (source_id: `email_ferroline_001`)

> FerroLine Industries — Campus Hiring 2027
> 
> Role: Manufacturing Engineer
> 
> Eligibility Criteria:
> Minimum CGPA: 7.65 and above
> Branches eligible: CSE, ISE, ECE
> Maximum 2 active backlogs allowed
> Minimum 60% in 10th and 12th
> 
> Compensation: 6.8 LPA
> 
> Link to apply: https://forms.gle/ferroline2027
> Deadline: 17-10-2026, 5 PM
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** multi_condition
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.65` — authoritative source: `email_ferroline_001`
- `allowed_branches` in `['CSE', 'ISE', 'ECE']` — authoritative source: `email_ferroline_001`
- `max_backlogs` lte `2` — authoritative source: `email_ferroline_001`
- `min_10th_pct` gte `60` — authoritative source: `email_ferroline_001`
- `min_12th_pct` gte `60` — authoritative source: `email_ferroline_001`

**Description:** CGPA 7.55 narrow miss, and ETE not in the allowed branch list.


---

## CASE_062

**Drive:** `DRIVE_NVIDIA`  |  **Student:** `1MS22CS016`

### Student profile

- USN: `1MS22CS016`
- Name: Meera Iyer
- Date of birth: 2003-11-12
- CGPA: 6.8
- Branch: CSE
- Backlogs: 1
- Has prior offer: False
- 10th percentage: 68.0
- 12th percentage: 65.0

### Messages (chronological order)

1. **[2026-10-23T00:00:00] student_portal** (source_id: `portal_SIS_NVIDIA_001`)

> === NVIDIA ===
> 
> Position: System Software Engineering Intern
> Role: Software Engineering Intern
> Type: Internship
> Package: 12.0 LPA
> 
> Eligibility Criteria:
> CGPA 7.5 and above. Branches: CSE, ECE, EEE, EE. Graduating in 2027.
> 
> Application Deadline: 26-10-2026 02:00 PM
> Event Date: 30-10-2026
> 
> Work Mode: Onsite
> Preferred Skills: C/C++, Python, Operating Systems, System Programming
> 
> Status: OPEN
> Posted: 6 days ago

2. **[2026-10-24T11:50:00] placement_cell_email** (source_id: `email_nvidia_001`)

> NVIDIA - System Software Engineering Intern | 6 Month full-time Spring Internship (Jan - June) Program 2027
> 
> We are looking to hire students graduating in 2027 to join our System Software Engineering Teams as Intern.
> 
> Position: System Software Engineering Intern
> Qualification: B. Tech, M.Tech, Dual Degree
> Branch: CSE, ECE, EEE, EE
> CGPA Required: 7.8 and above
> Pass-out Batch: 2027
> 
> Internship Stipend: INR 1,00,000 per month
> Tentative Location: Pune / Bangalore / Hyderabad
> 
> Assessment Details:
> Assessment Type & Platform: Mix of Aptitude and Technical (Online) on HackerRank
> Online Assessment Date: 30th October 9:00 AM
> Skills to be Assessed: C/C++, Python, Programming, Datastructure, Operating System, System SW Knowledge, Algorithm, AI & Problem Solving
> 
> The last date to submit the list of applicants: 26th October 2026, 2 PM
> https://forms.gle/6kkKttAaZdtToibY7
> 
> Note: This is a full-time, in-office internship. The Pre-Placement Offer will be extended based on their performance.
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** temporal_conflict
**Temporal reasoning required:** True
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_cgpa` gte `7.8` — authoritative source: `email_nvidia_001`
- `allowed_branches` in `['CSE', 'ECE', 'EEE', 'EE']` — authoritative source: `email_nvidia_001`

**Description:** CSE branch ok but CGPA 6.8 fails the real (higher) requirement.


---

## CASE_090

**Drive:** `DRIVE_ERICSSON`  |  **Student:** `1MS22ET012`

### Student profile

- USN: `1MS22ET012`
- Name: Pooja Rao
- Date of birth: 2003-12-08
- CGPA: 6.5
- Branch: ETE
- Backlogs: 3
- Has prior offer: False
- 10th percentage: 60.0
- 12th percentage: 58.0

### Messages (chronological order)

1. **[2026-10-27T13:03:00] placement_cell_email** (source_id: `email_ericsson_001`)

> Ericsson NextGen Innovate 2026-27: 10 Internships + ₹7.15 LPA PPO Pathway
> 
> WHY THIS MATTERS FOR YOUR STUDENTS:
> - 10 internships with Ericsson's Automation & AI team (AI, cloud and automation)
> - 6-month internship in Bengaluru with a stipend of ₹35,000 per month
> - Pathway to a full-time role: fixed CTC of ₹7.15 LPA + 8.5% variable pay + ₹75,000 joining bonus on conversion*
> 
> *Subject to successful completion of the internship and performance.
> 
> WHO CAN PARTICIPATE:
> - B.E. / B.Tech, all streams
> - Final-year students currently in 7th semester
> - Minimum 60% in Class 10, Class 12 and B.E. / B.Tech
> - No active backlogs
> - Individual participation only (no teams)
> 
> THE SELECTION JOURNEY (all phases are elimination rounds):
> 26 Oct – 10 Nov: Registrations
> 4 Nov: Webinar
> 11 – 16 Nov: Phase 1, Logical Reasoning Assessment
> 19 – 24 Nov: Phase 2, Coding Challenge
> 27 Nov – 7 Dec: Phase 3, Case Study Submission
> 15 – 18 Dec: Case Study Presentations
> 21 Dec: Final Results
> 
> Registration link: https://www.naukri.com/campus/contests/ericsson-build-for-impact
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** INELIGIBLE
**Expected UNKNOWN case:** False
**Category:** normal
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_10th_pct` gte `60` — authoritative source: `email_ericsson_001`
- `min_12th_pct` gte `60` — authoritative source: `email_ericsson_001`
- `max_backlogs` lte `0` — authoritative source: `email_ericsson_001`

**Description:** Fails 10th/12th% and backlogs.


---

## CASE_093

**Drive:** `DRIVE_ERICSSON`  |  **Student:** `1MS22CS033`

### Student profile

- USN: `1MS22CS033`
- Name: Harsh Vardhan
- Date of birth: 2003-08-17
- CGPA: 8.1
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: **(not on record)**
- 12th percentage: 79.0

### Messages (chronological order)

1. **[2026-10-27T13:03:00] placement_cell_email** (source_id: `email_ericsson_001`)

> Ericsson NextGen Innovate 2026-27: 10 Internships + ₹7.15 LPA PPO Pathway
> 
> WHY THIS MATTERS FOR YOUR STUDENTS:
> - 10 internships with Ericsson's Automation & AI team (AI, cloud and automation)
> - 6-month internship in Bengaluru with a stipend of ₹35,000 per month
> - Pathway to a full-time role: fixed CTC of ₹7.15 LPA + 8.5% variable pay + ₹75,000 joining bonus on conversion*
> 
> *Subject to successful completion of the internship and performance.
> 
> WHO CAN PARTICIPATE:
> - B.E. / B.Tech, all streams
> - Final-year students currently in 7th semester
> - Minimum 60% in Class 10, Class 12 and B.E. / B.Tech
> - No active backlogs
> - Individual participation only (no teams)
> 
> THE SELECTION JOURNEY (all phases are elimination rounds):
> 26 Oct – 10 Nov: Registrations
> 4 Nov: Webinar
> 11 – 16 Nov: Phase 1, Logical Reasoning Assessment
> 19 – 24 Nov: Phase 2, Coding Challenge
> 27 Nov – 7 Dec: Phase 3, Case Study Submission
> 15 – 18 Dec: Case Study Presentations
> 21 Dec: Final Results
> 
> Registration link: https://www.naukri.com/campus/contests/ericsson-build-for-impact
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** UNKNOWN
**Expected UNKNOWN case:** True
**Category:** missing_info
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `min_10th_pct` gte `60` — authoritative source: `email_ericsson_001`
- `min_12th_pct` gte `60` — authoritative source: `email_ericsson_001`
- `max_backlogs` lte `0` — authoritative source: `email_ericsson_001`

**Description:** 10th% null -> UNKNOWN.


---

## CASE_095

**Drive:** `DRIVE_OPUS`  |  **Student:** `1MS22CS024`

### Student profile

- USN: `1MS22CS024`
- Name: Riya Kapoor
- Date of birth: 2003-01-30
- CGPA: 8.92
- Branch: CSE
- Backlogs: 0
- Has prior offer: False
- 10th percentage: 90.0
- 12th percentage: 87.5

### Messages (chronological order)

1. **[2026-10-23T15:28:00] placement_cell_email** (source_id: `email_opus_001`)

> Opus Technologies Campus Hiring
> 
> For over 29 years, Opus Technologies has been at the forefront of innovation & serving as a trusted engineering partner to leading payment providers, banks, and fintechs worldwide.
> 
> NOTE – We need only Engineers – CS & IT, DATA & AI
> 
> Interested students can register by 24th-10-2026(11am)
> https://forms.gle/zdALSaazQg8LpAQJ7
> 
> Compensation Structure:
> Cost to Company: 7 LPA + Benefits
> On Internship – Stipend will be 15,000 Per month
> 
> — Placement Department RIT

### Expected answer (from `data/gold_set.json`)

**Eligibility:** ELIGIBLE
**Expected UNKNOWN case:** False
**Category:** normal
**Temporal reasoning required:** False
**Provenance reasoning required:** False

**Expected current rules (the reconciled winner per criterion):**
- `allowed_branches` in `['CSE', 'CSE(AI&ML)', 'ISE']` — authoritative source: `email_opus_001`

**Description:** Eligible CSE student.


---
