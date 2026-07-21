# Historical Archive Policy

The clean default branch contains only the current presentation and
purpose-based artifacts. Earlier experiment stages are not copied into folders
named after development versions.

Scientific history is preserved through:

1. immutable Git tags;
2. GitHub Releases;
3. the version-specific Zenodo archive; and
4. the source-artifact map in `audit/source_artifact_map.csv`.

Do not delete or retag the existing public release. A clean repository
reorganization should be published as a new release, while the earlier tag
remains immutable and citable.

This separation is deliberate:

- `main` shows the current professional repository;
- tags preserve historical snapshots;
- Zenodo preserves the exact cited archive;
- the migration map retains provenance without cluttering the default branch.
