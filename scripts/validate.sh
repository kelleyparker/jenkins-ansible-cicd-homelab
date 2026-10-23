#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts
yamllint .
ansible-lint playbooks/ roles/
python -m pytest tests/unit/ -q --junitxml=artifacts/unit-tests.xml
ansible-playbook -i inventories/lab/hosts.ini playbooks/bootstrap.yml --syntax-check
ansible-playbook -i inventories/lab/hosts.ini playbooks/deploy.yml --syntax-check
