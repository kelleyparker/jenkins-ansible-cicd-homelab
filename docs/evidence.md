# Demonstration evidence

Fill this in with actual runs. The repository initially supplies implementation
and examples; it does not certify that the VMs or ten targets have been tested.

| Item | Result / link / date |
| --- | --- |
| Jenkins URL and job name | Pending lab setup |
| Runner OS | Ubuntu 26.04 LTS; confirmed by VM terminal output |
| Actual target count | Initial inventory: one; deployment not yet recorded |
| Git commit tested | Pending |
| Successful validation build | Jenkins build #1 succeeded on October 22, 2026; screenshot reviewed |
| Dry-run diff reviewed | Pending |
| Approval recorded | Pending |
| Successful deployment + smoke artifact | Pending |
| SVN revision and polling-triggered build | Pending |
| Ten actual nodes all verified | Pending; do not claim this from the sample inventory |

## Local verification on October 22, 2026

Validated under Ubuntu in WSL with Python 3.12.3 and the pinned tools in
`requirements-dev.txt`:

- YAML lint passed.
- Ansible lint passed the production profile with zero rule failures/warnings.
- All 38 unit tests passed.
- Both additional loopback HTTP integration tests passed, covering a matching
  build (exit 0) and a stale build (exit 1).
- Ansible syntax checks passed for bootstrap and deployment playbooks.
- Bash syntax checks passed for both shell scripts.

These checks did not connect to the Hyper-V targets, execute the SVN bootstrap,
or run this Jenkinsfile in a live Jenkins instance. Those demonstrations remain
pending above.

## Failure demonstrations

Use temporary Git branches/commits and dedicated lab VMs. Revert the deliberate
fault afterwards and keep evidence of the failing stage and the corrected build.

1. Introduce a YAML indentation error; show that the lint stage fails before SSH.
2. Introduce an Ansible lint violation; show the stopped pipeline.
3. Break an actual Python assertion; show the unit-test report.
4. Abort the approval prompt; show that deployment never executes.
5. Run the smoke CLI with an incorrect `--expected-build`; show its exit code 1
   and failed report without making any deployment changes.
6. For a multi-node lab, stop NGINX on one dedicated target and run the smoke CLI;
   show that it checks the other targets too but returns failure overall. Restore
   the service afterwards.
7. Commit an SVN homepage change; show the new revision, polling trigger,
   approval, changed homepage and matching Jenkins number.

Keep screenshots and console excerpts free of passwords/private keys. Link
sanitized evidence here rather than marking unperformed checks as complete.
