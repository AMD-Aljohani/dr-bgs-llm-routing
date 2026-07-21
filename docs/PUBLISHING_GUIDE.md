# Publishing the Clean Repository

## Recommended safe procedure

1. Preserve the current public repository and its existing tag.
2. Create a temporary branch from the current default branch:

   ```bash
   git switch -c clean-main
   ```

3. Remove the old working-tree files from that branch, then copy the contents
   of this package into the repository root. Do not copy the outer folder.
4. Verify:

   ```bash
   python tools/verify_repository.py
   git diff --check
   git status --short
   ```

5. Commit:

   ```bash
   git add -A
   git commit -m "Reorganize repository into clean reproducibility layout"
   git push -u origin clean-main
   ```

6. Inspect the branch on GitHub. Confirm that the manuscript, results, scripts,
   and checksums open correctly.
7. Merge `clean-main` into `main` or make it the default branch.
8. Create a new release. A major layout release such as `v2.0.0` is appropriate
   because paths have changed, even though the scientific results have not.
9. Archive the new release with Zenodo.
10. Update the manuscript Data Availability Statement with the new version DOI,
    then compile the manuscript once more.

## Do not rewrite history

Do not force-push over the existing public tag or replace its Zenodo deposit.
Old paths remain available through the immutable release even though they no
longer clutter the default branch.
