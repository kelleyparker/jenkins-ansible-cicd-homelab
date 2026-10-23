#!/usr/bin/env bash
# Run on the SVN host (cicd-target), once, from this repository checkout.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $EUID -ne 0 ]]; then
    echo 'Run with sudo bash scripts/setup_svn.sh' >&2
    exit 1
fi
if [[ -e /srv/svn/cicd-site || -e /etc/systemd/system/cicd-svn.service ]]; then
    echo 'Repository or service already exists; refusing to overwrite it.' >&2
    exit 1
fi
read -r -s -p 'Password for jenkins-read (16+ letters/digits): ' reader_password
printf '\n'
read -r -s -p 'Password for lab-writer (16+ letters/digits): ' writer_password
printf '\n'
if [[ ! $reader_password =~ ^[A-Za-z0-9]{16,}$ || ! $writer_password =~ ^[A-Za-z0-9]{16,}$ ]]; then
    echo 'Use passwords with at least 16 ASCII letters/digits.' >&2
    exit 1
fi
apt-get update
apt-get install -y subversion
if ! id cicd-svn >/dev/null 2>&1; then
    adduser --system --group --home /srv/svn --no-create-home cicd-svn
fi
install -d -o cicd-svn -g cicd-svn -m 0750 /srv/svn
svnadmin create /srv/svn/cicd-site
svn mkdir file:///srv/svn/cicd-site/trunk file:///srv/svn/cicd-site/branches \
    file:///srv/svn/cicd-site/tags -m 'Create trunk, branches and tags'
svn import svn-seed/trunk file:///srv/svn/cicd-site/trunk -m 'Seed lab website'
cat > /srv/svn/cicd-site/conf/svnserve.conf <<'EOF'
[general]
anon-access = none
auth-access = write
password-db = passwd
authz-db = authz
realm = cicd-homelab
EOF
(
    umask 077
    printf '[users]\njenkins-read = %s\nlab-writer = %s\n' \
        "$reader_password" "$writer_password" > /srv/svn/cicd-site/conf/passwd
)
unset reader_password writer_password
cat > /srv/svn/cicd-site/conf/authz <<'EOF'
[/]
jenkins-read = r
lab-writer = rw
* =
EOF
chown -R cicd-svn:cicd-svn /srv/svn/cicd-site
chmod 0600 /srv/svn/cicd-site/conf/passwd
cat > /etc/systemd/system/cicd-svn.service <<'EOF'
[Unit]
Description=Home lab Subversion repository
After=network.target

[Service]
Type=simple
User=cicd-svn
Group=cicd-svn
ExecStart=/usr/bin/svnserve --daemon --foreground --root /srv/svn
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/svn

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now cicd-svn.service
echo 'SVN ready at svn://cicd-target/cicd-site/trunk (TCP 3690).'
