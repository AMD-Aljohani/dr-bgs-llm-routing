# BurstGPT source note for V15

The original compact CSV is an exact row-for-row match to the first 100 rows of the official `BurstGPT_1.csv` release.

- Official source file SHA-256: `46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a`
- Compact 100-row CSV SHA-256: `a2675f51ec359eec09a97d92e0a861171264c207e99aa462c2815845ce606143`
- Seven-day subset SHA-256: `68130aef7579045f0e8cedefe9fccd288f2008c5821ff979d92c11995b14a1b6`
- Seven-day window: `0 <= Timestamp < 604800` seconds.
- Search pool: positive-token rows before 432000 seconds.
- Certification pool: positive-token rows from 432000 through 604800 seconds.

The source dataset is described by the BurstGPT paper cited in the manuscript and distributed by the authors' public BurstGPT repository.
