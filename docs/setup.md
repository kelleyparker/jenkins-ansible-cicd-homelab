# Set up the two existing Ubuntu 24.04 VMs

Run Linux commands below on the indicated VM. Replace `labadmin`, IP addresses,
and credential examples with your actual values. No VM is contacted by merely
cloning this repository or running the default validation build.

## 1. Network and accounts

`cicd-runner` must reach `cicd-target` on SSH TCP 22 and NGINX TCP 8080, and on
TCP 3690 if SVN is enabled. The runner needs outbound access to GitHub and PyPI.
Both names must resolve; use real IPs in inventory and the SVN URL if they do not.

The examples use an existing `labadmin` account on the target with Python 3 and
SSH access. Ansible uses sudo (`become: true`). For a dedicated disposable lab,
configure that account for passwordless sudo using `sudo visudo -f
/etc/sudoers.d/cicd-lab`, with a line such as:

```text
labadmin ALL=(ALL) NOPASSWD: ALL
```

Keep that sudoers file owned by root with mode 0440. This grants broad lab-admin
privileges; select an appropriate account for these dedicated VMs.

On the target, if SSH/Python are missing:

```bash
sudo apt-get update
sudo apt-get install -y openssh-server python3
sudo systemctl enable --now ssh
```

If UFW is enabled, permit TCP 22 and 8080 from the runner's real IP. For example,
replace `192.0.2.10` (a documentation address):

```bash
sudo ufw allow from 192.0.2.10 to any port 22 proto tcp
sudo ufw allow from 192.0.2.10 to any port 8080 proto tcp
```

## 2. Install the runner tools

On `cicd-runner`:

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv openssh-client subversion
git clone https://github.com/kelleyparker/jenkins-ansible-cicd-homelab.git
cd jenkins-ansible-cicd-homelab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Edit `inventories/lab/hosts.ini` for the target address and SSH username. The
initial inventory has one real target name; do not enable the ten-node example
without actually creating those machines and assigning their real addresses.

## 3. SSH credentials and host keys

Create a dedicated SSH key as your administrative user on the runner. Store it
outside the repository and do not commit the private key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cicd_lab -C jenkins-cicd-homelab
ssh-copy-id -i ~/.ssh/cicd_lab.pub labadmin@cicd-target
ssh -i ~/.ssh/cicd_lab labadmin@cicd-target 'sudo -n true'
```

In Jenkins, create **SSH Username with private key**, ID **`lab-ssh`**, with that
username/key and its passphrase if used. Install the **SSH Agent** plugin so the
Jenkinsfile can load it without writing a key into Git or the workspace.

Host-key checking stays enabled. Verify the target's SSH fingerprint using its
Hyper-V console (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`), then establish
the SSH connection as the OS account that runs the Jenkins executor and accept
the matching key. That account needs a writable `~/.ssh/known_hosts`. If its shell
is disabled, an administrator can install a verified known_hosts file for it.
Repeat for every actual inventory hostname/IP. An SSH Agent credential does not
automatically populate known_hosts.

## 4. Run local validation and the one-time bootstrap

From the runner checkout with `.venv` activated:

```bash
bash scripts/validate.sh
ansible -i inventories/lab/hosts.ini nginx -m ansible.builtin.ping --private-key ~/.ssh/cicd_lab
ansible-playbook -i inventories/lab/hosts.ini playbooks/bootstrap.yml --private-key ~/.ssh/cicd_lab
```

The bootstrap intentionally changes the target: it installs NGINX, creates the
web root, and starts the service. It is an initial prerequisite, outside the
application pipeline. It does not install the project NGINX configuration.

## 5. Jenkins job

Use an existing Jenkins installation on the runner (or a controller connected to
an agent there). Install **Pipeline**, **Git**, **Subversion**, **SSH Agent**,
**JUnit**, and **Timestamper** plugins. Give the executor/node the label
**`cicd-runner`**. Install `python3-venv`, Git, SVN and SSH on the actual executor,
including inside its container if Jenkins runs in one.

Create a **Pipeline** job:

| Setting | Value |
| --- | --- |
| Definition | Pipeline script from SCM |
| SCM | Git |
| Repository URL | `https://github.com/kelleyparker/jenkins-ansible-cicd-homelab.git` |
| Branch | `*/main` |
| Script Path | `Jenkinsfile` |

The public Git repository needs no Git credential to clone. Build once manually
to register the Jenkinsfile parameters and SCM polling. The default run uses the
Git homepage seed and performs local validation without SSH or deployment.

Then choose **Build with Parameters**, enable `RUN_DEPLOYMENT`, and leave
`USE_SVN` disabled for the first deployment. In the console:

1. Confirm lint, pytest and both syntax checks pass.
2. Inspect the dry-run diff for all inventory targets.
3. Click **Deploy** within ten minutes. Restrict Jenkins job permissions to the
   people permitted to approve lab deployments.
4. Confirm the smoke-test stage passes and download its JSON artifact.

Check manually from the runner, substituting that Jenkins build number:

```bash
curl --fail http://cicd-target:8080/
curl --fail http://cicd-target:8080/build
```

The build number must equal the Jenkins build you approved. The pipeline manages
the full `/etc/nginx/nginx.conf`; use the dedicated target and do not point this
inventory at a server with an unrelated NGINX configuration.

## 6. Run individual deployment commands for learning

From the runner checkout with your key available in `ssh-agent`:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/cicd_lab
python scripts/prepare_deploy.py --build 1 --content-dir svn-seed/trunk
ansible-playbook playbooks/deploy.yml -e @artifacts/deploy-vars.json --syntax-check
ansible-playbook playbooks/deploy.yml -e @artifacts/deploy-vars.json --check --diff
# Review that diff before running the next command manually:
ansible-playbook playbooks/deploy.yml -e @artifacts/deploy-vars.json --diff
ansible-inventory --list > artifacts/inventory.json
python scripts/smoke_test.py --inventory artifacts/inventory.json --expected-build 1
```

Manual CLI execution does not have a Jenkins approval prompt. Use Jenkins for
the actual gated demonstration and capture its evidence.

## 7. Expand the inventory

`inventories/examples/ten-node.hosts.ini` shows the shape of a ten-target
inventory using documentation-only addresses. Add actual Ubuntu 24.04 machines
to `inventories/lab/hosts.ini`, configure SSH and verified host keys, and bootstrap
every new target. Run `ansible-inventory --graph` to check the membership.
Deployment and smoke tests then automatically cover all hosts in `nginx`.

The two existing Hyper-V VMs are sufficient to demonstrate the workflow on one
target. Neither this repository nor an example inventory proves a ten-node lab.
Vagrant provisioning is not included; record it only if you actually use it.
