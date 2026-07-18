# Release 1.5.0 - V15 Future Internet candidate

V15 addresses the remaining trace-size and submission-compliance risks while preserving all locked V11--V13 results.

## Retained

- Original strict absolute-SLO result: 0/120 method runs certified.
- V12 exhaustive original-regime audit: 0/2,280 policy-scenario pairs certified.
- V13 low-load confirmation: DR-BGS 6/6, guarded GP 20/20, exhaustive training 6/6 unique method-specific pairs.
- Retrospective noninferiority audit: DR-BGS 50/60 and guarded GP 33/60.

## Added

- Verified that the archived compact slice exactly matches the first 100 rows of the official `BurstGPT_1.csv` file.
- Added a separately locked seven-day trace robustness replication with 11,810 search and 6,086 later certification records.
- Reproduced 0/2,280 certifiable high-load policy-scenario pairs on the larger trace basis.
- Confirmed 18/18 cross-method-distinct low-load scenario-policy pairs in two disjoint 1,200-replay batches.
- Corrected the V13 31-versus-32 wording by explaining cross-method deduplication.
- Reduced the manuscript abstract to 191 words.
- Added Author Contributions, Institutional Review Board Statement, Informed Consent Statement, Data Availability Statement, and Conflicts of Interest.
- Updated the manuscript, cover letter, highlights, special-issue abstract, documentation, and integrated audit.

## Claim boundary

The seven-day study reduces dependence on the compact trace slice. It does not establish full-corpus representativeness or production safety. Privacy labels, pressure conversion, target load, and replay construction remain synthetic; exact risk bounds are conditional on the declared generator.

## Remaining external blocker

Reserve the version DOI in Zenodo, insert it into the Data Availability Statement, publish immutable tag `v1.5.0`, archive the exact release, verify the public links, and then submit.
