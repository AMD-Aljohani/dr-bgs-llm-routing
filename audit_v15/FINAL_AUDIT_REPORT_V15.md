# V15 Integrated Validity and Package Audit

**Status: PASS. 61/61 checks passed.**

## Scope

This audit preserves the V14 hierarchy and verifies the separately locked seven-day BurstGPT robustness replication, trace provenance, numerical claims, manuscript compliance, compilation, and PDF preflight.

## Key verified results

- Original V11 strict result remains 0/120 method runs certified.

- V15 seven-day high-load audit finds 0/2,280 certifiable policy-scenario pairs.

- V15 low-load confirmation passes 6/6 DR-BGS, 12/12 guarded-GP, and 6/6 exhaustive-training method-specific unique pairs.

- Cross-method deduplication leaves 18/18 confirmed pairs with no batch reversal.

- The abstract contains 191 words and required MDPI back-matter sections are present.

## Checks

- PASS - v14_audit_passes
- PASS - lock_v15_seven_day_robustness_v15_seven_day_protocol_md
- PASS - lock_v15_seven_day_robustness_v15_seven_day_config_json
- PASS - lock_trace_data_burstgpt_first7days_csv
- PASS - lock_trace_data_burstgpt_provenance_v15_json
- PASS - lock_v11_code_run_trace_risk_study_py
- PASS - lock_code_run_smpt_campaign_py
- PASS - lock_v15_seven_day_robustness_run_v15_seven_day_robustness_py
- PASS - lock_precedes_execution
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
- PASS - latex_compiles
- PASS - latex_no_undefined_references
- PASS - latex_no_overfull_boxes
- PASS - candidate_pdf_present
- PASS - pdf_pages_reasonable
- PASS - pdf_fonts_embedded
- PASS - cover_letter_one_page
- PASS - v15_figure_present

## Notes

- v14_audit_passes: 67d21fe4a9c6188ab62ec560dcb19dba51d4b1443fd9'}\n",
    "manuscript_claim_1: none of the 2,280 policy--scenario combinations",
    "manuscript_claim_2: 135 of 190 nominations",
    "manuscript_claim_3: guarded GP 140 of 190",
    "manuscript_claim_4: all six unique DR-BGS scenario--policy pairs",
    "manuscript_claim_5: all twenty unique guarded-GP pairs",
    "manuscript_claim_6: all 31 unique pairs pass both batches",
    "manuscript_claim_7: 92.9\\%--94.4\\% load reduction",
    "manuscript_claim_8: not a practical deployment recommendation",
    "pdf_page_count_reasonable: pages=37"
  ]
}

- lock_v15_seven_day_robustness_v15_seven_day_protocol_md: v15_seven_day_robustness/V15_SEVEN_DAY_PROTOCOL.md
- lock_v15_seven_day_robustness_v15_seven_day_config_json: v15_seven_day_robustness/V15_SEVEN_DAY_CONFIG.json
- lock_trace_data_burstgpt_first7days_csv: trace_data/BurstGPT_first7days.csv
- lock_trace_data_burstgpt_provenance_v15_json: trace_data/BURSTGPT_PROVENANCE_V15.json
- lock_v11_code_run_trace_risk_study_py: v11_code/run_trace_risk_study.py
- lock_code_run_smpt_campaign_py: code/run_smpt_campaign.py
- lock_v15_seven_day_robustness_run_v15_seven_day_robustness_py: v15_seven_day_robustness/run_v15_seven_day_robustness.py
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
- latex_compiles: Rc files read:
  NONE
Latexmk: This is Latexmk, John Collins, 11 Dec. 2024. Version 4.86.
Latexmk: Nothing to do for 'FutureInternet_manuscript_candidate_v15.tex'.
Latexmk: All targets (FutureInternet_manuscript_candidate_v15.pdf) are up-to-date


- pdf_pages_reasonable: pages=37