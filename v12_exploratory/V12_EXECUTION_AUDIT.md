# V12 Execution Audit

Status: **PASS**

The run used the uploaded V11 release package without editing its source files. V12 scripts and outputs are separately hashed. The original V11 result remains outside this exploratory package and is not overwritten.

## Structural checks

| check                           | passed   |
|:--------------------------------|:---------|
| campaign1_policy_rows_2280      | True     |
| campaign1_190_per_scenario      | True     |
| campaign1_zero_certified        | True     |
| campaign1_zero_mean_feasible    | True     |
| campaign2_config_batches_549    | True     |
| campaign2_physical_settings_325 | True     |
| campaign2_policy_rows_expected  | True     |
| campaign2_method_rows_expected  | True     |
| campaign2_certification_logic   | True     |
| campaign3_rows_expected         | True     |
| campaign3_certification_logic   | True     |
| campaign3_baseline_zero_1200    | True     |
| all_checks_pass                 | True     |

## Source hashes

| item                    | sha256                                                           | path                                                                                         |
|:------------------------|:-----------------------------------------------------------------|:---------------------------------------------------------------------------------------------|
| uploaded_repository_zip | 1f550f7582dd730325047dc796bb4c6ec8f5f679f7f0848c639879d467325094 | /mnt/data/dr-bgs-llm-routing-github-v1.3.0(1).zip                                            |
| primary_v12_script      | 73c4172bef2da707fe48d51011b241848429a84bdd82798fdbba2f8466199a81 | /mnt/data/run_v12_exploratory.py                                                             |
| corrected_v12_script    | a7746415744fe3fff05e796ac527c8a1a279513cbe63e5eae0c137451b18dfc1 | /mnt/data/run_v12_campaign2_v2.py                                                            |
| burstgpt_trace          | a2675f51ec359eec09a97d92e0a861171264c207e99aa462c2815845ce606143 | /mnt/data/drbgs_v13/dr-bgs-llm-routing-github-v1.3.0/trace_data/BurstGPT_first100_public.csv |
| v11_trace_risk_code     | 6c9de6920ff43a04a49a3c4eeaefb7c6073b41b2b34ff498740c72dcbcdc694d | /mnt/data/drbgs_v13/dr-bgs-llm-routing-github-v1.3.0/v11_code/run_trace_risk_study.py        |
| event_simulator_code    | e74a9eea3c8aa797258722c73ef853989c678f3580c71d82b7aad407dff50c91 | /mnt/data/drbgs_v13/dr-bgs-llm-routing-github-v1.3.0/code/run_smpt_campaign.py               |
