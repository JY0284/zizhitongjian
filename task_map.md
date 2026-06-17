# Task Map (V1)

> One-by-one checklist to implement `design.md` + `data_pipeline.md`.
> Created at: 2026/01/17

## Current repo anchors (so tasks map to code)

- Extraction: `knowledge_extraction.py` → writes `data/store/juan_*.json` via `knowledge_store.py`
- Unification: `entity_resolution.py` → writes `data/unified_knowledge.json`
- Frontend entry: `visualization/src/App.tsx` (currently local state only; not URL-addressable)
- Filters UI: `visualization/src/components/FilterControls.tsx`
- Types: `visualization/src/types/unified.ts` (relations currently lack numeric year fields)

## Phase 0 — Freeze contracts (so work composes)

- [x] 1) **Finalize canonical schemas (doc + types)**
- Output: agreed fields + JSON shape for:
  - `data/segment_year_index.json`
  - `data/juan_year_index.json`
  - `data/location_geocoding.json` (incl. `overrides`)
  - additions to `data/unified_knowledge.json` (relation years; optional event imputed years)
- Success criteria: schemas are written down and referenced by both backend and frontend types.
- Touchpoints:
  - Docs: `data_pipeline.md`
  - Frontend types: `visualization/src/types/unified.ts`
  - Backend models (if any): `model/*`

- [x] 2) **Decide global time policy knobs**
- Output: explicit config values (even if hard-coded for V1):
  - `cutoff_year` for BCE/CE handling
  - accepted regex formats for `segment_start_time`
- Success criteria: documented defaults and failure behavior (“unknown year”).
- Touchpoints:
  - Docs: `data_pipeline.md`

## Phase 1 — Time foundation (segment year + juan year)

- [x] 3) **Implement segment-year parser (deterministic)**
- Output: generator script produces `data/segment_year_index.json` from `adapted_book.json`.
- Success criteria:
  - produces a numeric `year` for most segments with explicit `前NNN` / `公元前NNN`
  - records `parse_method` + `confidence`
- Touchpoints:
  - New script (suggested): `build_segment_year_index.py`
  - Input: `adapted_book.json`

- [x] 4) **Add validation checks for year monotonicity**
- Output: a validator that flags:
  - non-decreasing violations within a juan
  - sequential-on-year violations across juans (start-year order)
- Success criteria: validator exits non-zero and prints actionable cases.
- Touchpoints:
  - Same script as above or `validate_year_index.py`

- [x] 5) **Build juan start-year index**
- Output: generator writes `data/juan_year_index.json` from `data/segment_year_index.json`.
- Success criteria: every juan has a `juan_start_year` (or is flagged).
- Touchpoints:
  - New script (suggested): `build_juan_year_index.py`

## Phase 2 — Unified KB time enrichment (supports global filtering)

- [x] 6) **Extend unified relation schema with numeric years**
- Output: `data/unified_knowledge.json` includes:
  - `relations[*].first_interaction_year`
  - `relations[*].last_interaction_year`
- Success criteria: frontend network can filter edges by `yearRange` without parsing strings.
- Touchpoints:
  - Backend: `entity_resolution.py`
  - Frontend: `visualization/src/utils/unifiedDataProcessing.ts`

- [x] 7) **Derive relation years from segment index when missing**
- Output: for each relation action with `(juan_index, segment_index)`:
  - lookup segment year
  - aggregate min/max per unified relation
- Success criteria: coverage improves vs current “parse only from text time”.
- Touchpoints:
  - Backend: `entity_resolution.py`
  - Inputs: `data/segment_year_index.json`

- [x] 8) **(Recommended) Add event imputed year fields**

## Critical insertion — Separate non-human entities

- [x] **Split polity/state-like extractions out of `Role`**
  - Output: `data/unified_knowledge.json` includes `polities` (e.g. 秦/魏/赵…) and these no longer appear in `roles`.
  - Touchpoints: `model/polity.py`, `model/unified.py`, `entity_resolution.py`
  
- [x] **Expand non-human classification to schools and organizations**
  - Output: `data/unified_knowledge.json` includes:
    - `schools` (e.g. 儒家/法家/道家/墨家…)
    - `organizations` (e.g. 丞相府/太尉/秦军…)
  - LLM prompt updated with `entity_type` field for direct classification
  - Fallback heuristics classify based on name patterns
  - Formal tests: `tests/test_entity_resolution.py` (20 tests passing)
  - Touchpoints:
    - `model/role.py` (added `entity_type` field)
    - `model/school.py`, `model/organization.py` (new models)
    - `model/unified.py` (added `UnifiedSchool`, `UnifiedOrganization`)
    - `prompts/sys_entity_relation_extraction.md` (updated LLM schema)
    - `entity_resolution.py` (entity routing + resolution methods)

## Phase 3 — Location geocoding cache (enables map mode)

- [x] 9) **Define Amap geocoding configuration + secrets handling**
- Output: documented env vars (e.g. `AMAP_KEY`) + rate-limit strategy.
- Success criteria: runs locally without committing secrets.
- Touchpoints:
  - Docs: `README.md` (or a short section in `data_pipeline.md`)

- [x] 10) **Implement unified-location geocoding stage (cached)**
- Output: script generates/updates `data/location_geocoding.json` keyed by unified location id.
- Success criteria:
  - does not erase existing entries
  - writes `[lng, lat]` in WGS84
  - marks `needs_review` for ambiguous matches
- Touchpoints:
  - New script (suggested): `geocode_locations_amap.py`
  - Input: `data/unified_knowledge.json`

- [x] 11) **Merge geocoding results back into unified KB**
- Output: `locations[*].coordinates` filled in `data/unified_knowledge.json`.
- Success criteria: frontend reads coordinates only from unified KB.
- Touchpoints:
  - Backend: `entity_resolution.py` (post-pass) or a dedicated merge script

## Phase 4 — Frontend: global context + navigation semantics

- [x] 12) **Make Global Context URL-addressable**
- Output: `tab`, `juanRange`, `yearRange`, and focus/selection encoded in URL.
- Success criteria:
  - refresh restores context
  - shareable links reproduce the same view
- Touchpoints:
  - Frontend router/state: `visualization/src/App.tsx`

- [x] 13) **Implement push/replace history policy (commit semantics)**
- Output:
  - replace for high-frequency intermediate updates
  - push on commit (blur/enter/mouseup)
- Success criteria: browser Back/Forward feels like context navigation (not spammy).
- Touchpoints:
  - `visualization/src/components/FilterControls.tsx`
  - timeline interactions: `visualization/src/components/Timeline.tsx`

- [x] 14) **Apply `yearRange` filtering to network tab**
- Output: edges filtered by relation numeric years; nodes derived from remaining edges.
- Success criteria: network view matches global context constraints.
- Touchpoints:
  - `visualization/src/components/NetworkGraph.tsx`
  - `visualization/src/utils/unifiedDataProcessing.ts`

  Verified: `cd visualization && npm run build`

- [x] 15) **Add juan↔year sync policy UI**
- Output: when changing one range, offer/default update of the other (per `design.md`).
- Success criteria: user can navigate by juan or year without confusion.
- Touchpoints:
  - `visualization/src/components/FilterControls.tsx`
  - new read of `data/juan_year_index.json` (or embedded in unified KB)

  Verified: `cd visualization && npm run build`

## Phase 5 — Frontend: locations list mode → map mode → trajectory

- [x] 16) **Locations list mode fully driven by Global Context**
- Output: location list + detail reflect `juanRange`/`yearRange`.
- Success criteria: locations shown are “in-range relevant”.
- Touchpoints:
  - `visualization/src/components/DetailPanels.tsx` (location panels)
  - `visualization/src/utils/unifiedDataProcessing.ts`

  Verified: `cd visualization && npm run build`

- [x] 17) **Add map mode (graceful fallback for null coordinates)**
- Output: toggle/dual-mode implementation inside locations tab:
  - plot only in-range locations with coordinates
  - keep list for missing coordinates
- Success criteria: no blank screen when coords are missing.
- Touchpoints:
  - locations UI: `visualization/src/...` (new component likely needed)

  Implementation: Moved map to separate top-level tab using Leaflet + OpenStreetMap tiles.
  - New component: `visualization/src/components/MapView.tsx`
  - Uses `react-leaflet` with OSM tiles (neutral, shows rivers/mountains, no border issues)
  - LocationsView simplified to list-only with max-height scroll
  - Merged geocoding coordinates into `unified_knowledge.json` (195 locations)
  
  Verified: `cd visualization && npm run build`

- [ ] 18) **Finish entity trajectory UX and fallback behavior**
- Current state: partial `MapView` trajectory implementation exists.
- Remaining output: add UX entry points for selected role/event/power and show ordered event-location paths when both year + coords exist.
- Success criteria: trajectory only appears when data supports it; otherwise explain why it is absent.
- Touchpoints:
  - timeline/event detail + locations view
  - `visualization/src/utils/unifiedDataProcessing.ts`

## Phase 6 — Build orchestration & repeatability

- [ ] 19) **Add a single “build data” entrypoint**
- Output: one command that runs stages in order:
  - Extract (optional)
  - Segment year index
  - Juan year index
  - Unify
  - Geocode
  - Merge
- Success criteria: reproducible outputs; incremental caching respected.
- Touchpoints:
  - `main.py` (if used as CLI) or a new `scripts/` driver

- [ ] 20) **Add smoke validations for artifacts**
- Output: validators for:
  - schema shape
  - coordinates format `[lng, lat]`
  - year ranges sanity
- Success criteria: failures are caught before shipping to `visualization/public/data/`.

## Phase 7 — Ship loop (data → UI)

- [ ] 21) **Publish updated `data/unified_knowledge.json` to frontend**
- Output: frontend serves the new data file(s) correctly.
- Success criteria: visualization loads with no runtime errors and filters behave as designed.
- Touchpoints:
  - `visualization/public/data/*`
  - `visualization/src/hooks/useUnifiedData.ts`
