# General Analysis Playbook

**Purpose**
Provide a deterministic first-pass analysis skeleton for Firefox Profiler sessions. This document specifies what must be verified; it is implementation-agnostic.

## Base Checks (MUST, in order)
1. **Load profile and validate schema.**
   - Outcome: version, schema validity, and load success noted.
2. **Detect which content process media/playback scenario occurs.**
   - Outcome: content process pid(s) or names where playback activity is observed.
3. **Identify the rendering/compositor/decoder processes.**
   - Outcome: process identifiers captured for compositor and decoder processes.
4. **Identify the time range in which media playback occurs.**
   - Outcome: start/end timestamps recorded for later correlation.

> These checks are policy requirements (the *what*), not algorithms (the *how*). Implementation details belong in code or separate notes.

## Tooling Expectations (non-binding but explicit)
- Base Checks must be performed via data access to the profile (markers, threads, processes)—not by inference.
- Each check produces short, verifiable evidence (IDs, counts, and timestamps) suitable for trace logging.

## Evidence to Capture (for each check)
- **Timestamps/ranges** relevant to detection
- **Process/Thread identifiers** used
- **Key markers** referenced
- **One-sentence note** of any obvious anomalies

## Output Template
- **Summary (3–5 bullets)**
- **Base Check Summary (per step):**
  - What was validated
  - Evidence (IDs, counts, timestamps)
  - Any anomalies

## Notes
- Branching rules are **TBD** and will be introduced in a later revision. This version focuses solely on Base Checks to ensure determinism and testability.
