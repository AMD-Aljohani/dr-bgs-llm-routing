# V15 Integrated Validity and Package Audit

**Status: FAIL. 61/65 checks passed.**

## Scope

This audit preserves the V11 hierarchy and verifies the separately locked seven-day BurstGPT robustness replication, trace provenance, numerical claims, manuscript compliance, compilation, and PDF preflight.

## Key verified results

- Original V11 strict result remains 0/120 method runs certified.

- V15 seven-day high-load audit finds 0/2,280 certifiable policy-scenario pairs.

- V15 low-load confirmation passes 6/6 DR-BGS, 12/12 guarded-GP, and 6/6 exhaustive-training method-specific unique pairs.

- Cross-method deduplication leaves 18/18 confirmed pairs with no batch reversal.

- The abstract contains 191 words and required MDPI back-matter sections are present.

## Checks

- PASS - v11_audit_passes
- PASS - checksum_manifest_integrity
- PASS - lock_schema_validity
- PASS - lock_timestamp_validity
- PASS - lock_v15_seven_day_robustness_V15_SEVEN_DAY_PROTOCOL_md
- PASS - lock_v15_seven_day_robustness_V15_SEVEN_DAY_CONFIG_json
- PASS - lock_trace_data_BurstGPT_first7days_csv
- PASS - lock_trace_data_BURSTGPT_PROVENANCE_V15_json
- PASS - lock_v11_code_run_trace_risk_study_py
- PASS - lock_code_run_smpt_campaign_py
- PASS - lock_v15_seven_day_robustness_run_v15_seven_day_robustness_py
- PASS - required_final_artifact_integrity
- PASS - immutable_provenance_integrity
- PASS - official_source_rows
- PASS - official_source_hash_recorded
- PASS - seven_day_hash
- PASS - compact_hash
- PASS - compact_matches_seven_day_head
- PASS - seven_day_rows_19431
- PASS - seven_day_positive_17896
- PASS - search_rows_11810
- PASS - cert_rows_6086
- PASS - v15_status_completed
- PASS - high_load_2280
- PASS - high_load_zero_certified
- PASS - high_load_zero_scenarios
- PASS - high_drbgs_0_60
- PASS - high_gp_0_60
- PASS - high_exhaustive_0_12
- PASS - low_drbgs_6_6
- PASS - low_gp_12_12
- PASS - low_exhaustive_6_6
- PASS - low_cross_union_18
- PASS - low_cross_confirmed_18
- PASS - low_no_reversals
- PASS - low_max_upper_0_00307
- PASS - raw_high_rows_2280
- PASS - raw_high_all_zero
- PASS - raw_low_all_confirmed
- PASS - raw_low_no_reversal
- PASS - abstract_at_most_200
- PASS - claim_first_100_chronological_rows_of_the_official
- PASS - claim_11_810_search_and_6_086_later_certification_records
- PASS - claim_0_of_2_280_high_load_certifiable_pairs
- PASS - claim_all_18_cross_method_distinct_low_load_scenario_policy_pairs
- PASS - claim_these_method_specific_counts_sum_to_32
- PASS - claim_31_distinct_scenario_policy_pairs_because_dr_bgs_and_exhaust
- PASS - claim_author_contributions
- PASS - claim_institutional_review_board_statement
- PASS - claim_informed_consent_statement
- PASS - claim_data_availability_statement
- PASS - claim_conflicts_of_interest
- PASS - forbidden_groundbreaking_absent
- PASS - forbidden_revolutionary_absent
- PASS - forbidden_breakthrough_absent
- PASS - forbidden_publicly_absent
- PASS - python_sources_compile
- FAIL - latex_compiles
- PASS - latex_no_undefined_references
- PASS - latex_no_overfull_boxes
- FAIL - candidate_pdf_present
- FAIL - pdf_pages_reasonable
- FAIL - pdf_fonts_embedded
- PASS - cover_letter_one_page
- PASS - v15_figure_present

## Notes

- v11_audit_passes: PASS {'checks_total': 56, 'checks_passed': 56, 'checks_failed': 0, 'strict_absolute_certified_runs': 0, 'dr_noninferiority_certified_runs': 50, 'gp_noninferiority_certified_runs': 33, 'trace_work_reduction': 0.8395061728395061, 'manuscript_sha256': 'fb24480a9393926368a80aff4f4db8b92a366b46d428b6a5600384a457b87148', 'pdf_sha256': 'f3933914807ed226d1bbc30027d018af3da9fe5755a562213478b8623ea00989'}

- checksum_manifest_integrity: Parsed SHA256SUMS.txt
- lock_schema_validity: Parsed lock JSON
- lock_timestamp_validity: 2026-07-18T06:02:07.316977+00:00
- lock_v15_seven_day_robustness_V15_SEVEN_DAY_PROTOCOL_md: Verified
- lock_v15_seven_day_robustness_V15_SEVEN_DAY_CONFIG_json: Verified
- lock_trace_data_BurstGPT_first7days_csv: Verified
- lock_trace_data_BURSTGPT_PROVENANCE_V15_json: Verified
- lock_v11_code_run_trace_risk_study_py: Verified
- lock_code_run_smpt_campaign_py: Verified
- lock_v15_seven_day_robustness_run_v15_seven_day_robustness_py: Verified
- required_final_artifact_integrity: All post-result artifacts verified
- immutable_provenance_integrity: Aggregate of inputs and final artifacts
- abstract_at_most_200: words=191
- claim_first_100_chronological_rows_of_the_official: first 100 chronological rows of the official
- claim_11_810_search_and_6_086_later_certification_records: 11,810 search and 6,086 later certification records
- claim_0_of_2_280_high_load_certifiable_pairs: 0 of 2,280 high-load certifiable pairs
- claim_all_18_cross_method_distinct_low_load_scenario_policy_pairs: all 18 cross-method-distinct low-load scenario--policy pairs
- claim_these_method_specific_counts_sum_to_32: These method-specific counts sum to 32
- claim_31_distinct_scenario_policy_pairs_because_dr_bgs_and_exhaust: 31 distinct scenario--policy pairs because DR-BGS and exhaustive training select the same policy in scenario C06
- claim_author_contributions: Author Contributions
- claim_institutional_review_board_statement: Institutional Review Board Statement
- claim_informed_consent_statement: Informed Consent Statement
- claim_data_availability_statement: Data Availability Statement
- claim_conflicts_of_interest: Conflicts of Interest
- latex_compiles: may duplicate other messages):
  pdflatex: Command for 'pdflatex' gave return code 1
      Refer to 'FutureInternet_manuscript_submission_v15.log' and/or above output for details

Latexmk: Sometimes, the -f option can be used to get latexmk
  to try to force complete processing.
  But normally, you will need to correct the file(s) that caused the
  error, and then rerun latexmk.
  In some cases, it is best to clean out generated files before rerunning
  latexmk after you've corrected the files.

- candidate_pdf_present: BLOCKED by latex_compiles: no PDF was produced after compilation failed
- pdf_pages_reasonable: pages=0
