# Jenkins + Ansible CI/CD Home Lab

A practical Ubuntu 24.04 / Hyper-V lab: validate infrastructure code, preview the
changes, approve a deployment, and verify the Jenkins build number on every target.

The initial inventory contains **one target**, `cicd-target`. A ten-node inventory
example is included; ten running nodes have not been provisioned or verified by
this repository. Record actual results in [docs/evidence.md](docs/evidence.md).

```text
GitHub: Jenkinsfile, Ansible role, Python tests
                  |
                  v
cicd-runner: Jenkins + Python tools + Ansible + SVN client
                  |
          lint -> tests -> syntax
                  |
          content checkout (Git seed or SVN trunk)
                  |
          Ansible --check --diff
                  |
             manual approval
                  |
          deploy -> HTTP /build checks on ALL targets
                  |
cicd-target: NGINX :8080 + optional SVN :3690
```

## What the pipeline demonstrates

| Stage | Command / behavior |
| --- | --- |
| YAML lint | `yamllint .` |
| Ansible lint | `ansible-lint playbooks/ roles/` |
| Python unit tests | `python -m pytest tests/unit/ -q` |
| Ansible syntax | `ansible-playbook playbooks/deploy.yml --syntax-check` |
| Preview | `ansible-playbook playbooks/deploy.yml -e @artifacts/deploy-vars.json --check --diff` |
| Approval | Jenkins `input`, with a ten-minute timeout |
| Deploy | Same playbook and extra-vars, without `--check` |
| Verify | `python scripts/smoke_test.py --inventory artifacts/inventory.json --expected-build "$BUILD_NUMBER"` |

Jenkins runs all local checks before the first remote Ansible call. A failed stage
stops subsequent stages. Dry-run and deployment output, the resolved inventory,
tool versions, test results, and smoke-test JSON are retained as build artifacts.
The pipeline disables concurrent builds so one build cannot overwrite another
while it is waiting for approval or testing its deployed build number.

## Start here

1. Follow [docs/setup.md](docs/setup.md) for runner packages, SSH, Jenkins
   credentials, the initial NGINX bootstrap, and the first build.
2. Set `ansible_user` and `ansible_host` in
   [inventories/lab/hosts.ini](inventories/lab/hosts.ini).
3. Create a Jenkins **Pipeline script from SCM** job pointing to this Git repository,
   with script path `Jenkinsfile`, on a Linux executor labelled `cicd-runner`.
4. Run the validation build with the defaults. Deployment is disabled initially.
5. Bootstrap the target once, then build with `RUN_DEPLOYMENT=true`. Inspect the
   dry-run output before clicking **Deploy**.
6. Follow [docs/svn.md](docs/svn.md) to enable the separate, lab-hosted SVN source.

The `cicd-runner` label can identify a Jenkins agent on that VM, or the executor on
an all-in-one Jenkins lab VM. This project assumes Jenkins already exists; it does
not install Jenkins, create Hyper-V VMs, or claim to provision them with Vagrant.

## Run the checks yourself

On Ubuntu 24.04, from the repository root:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv git openssh-client subversion
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
bash scripts/validate.sh
# Optional additional tests against a local HTTP test server (no VM needed):
python -m pytest tests/integration/ -q
```

These commands do not deploy. Use the [setup guide](docs/setup.md) for remote steps.
Direct tool dependencies are pinned; pip resolves their transitive dependencies.
Jenkins records the resulting full environment in `artifacts/python-packages.txt`.

## Deployment details

- The NGINX role owns the **entire `/etc/nginx/nginx.conf`** on the lab targets.
  It uses port **8080** by default and does not include Ubuntu's default site.
  Use dedicated lab targets, and change `nginx_http_port` if needed.
- Before replacing the configuration, Ansible runs `nginx -t -c <temporary-file>`.
  It backs up the previous configuration and reloads after a successful change.
- `/build` returns only the current Jenkins build number; `/` serves `index.html`
  from the selected Git seed or SVN checkout.
- Smoke tests use resolved `ansible-inventory --list` data, including child groups
  and host-specific HTTP ports. They retry briefly, check every host even when one
  fails, reject redirects and stale builds, and refuse to pass an empty inventory.
- Check mode is a simulation. The first run needs the separate bootstrap because
  a simulated installation cannot create NGINX or its filesystem prerequisites.
- This is a gated deployment with failure detection, not automatic rollback or an
  atomic transaction across multiple servers. A failure can leave a partial rollout.

## SVN and Git

Git remains the source of the pipeline, role, and tests. SVN supplies the website's
`index.html`. The setup creates `trunk`, `branches`, and `tags` on a lab VM, with a
read-only Jenkins account and a separate writer account. Jenkins polls the checked
out Git/SVN sources every two minutes. Polling may combine multiple commits into
one build; it does not guarantee one build for each commit.

Default parameters keep both deployment and SVN off for the first validation run.
Before demonstrating automatic SVN-triggered deployments, update their Jenkinsfile
defaults as described in [docs/svn.md](docs/svn.md).

## References

- [Jenkins declarative syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)
- [Jenkins Subversion checkout and polling](https://www.jenkins.io/doc/pipeline/steps/subversion/)
- [Ansible check and diff modes](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
- [Ansible template validation](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/template_module.html)
- [Ansible lint usage](https://docs.ansible.com/projects/lint/usage/)

MIT licensed; see [LICENSE](LICENSE).
