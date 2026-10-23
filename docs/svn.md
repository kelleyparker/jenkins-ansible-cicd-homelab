# Host SVN and trigger Jenkins builds

This is a separate repository on your VM. It does not use GitHub as an SVN server.
Git holds the pipeline and infrastructure code; SVN holds the deployable homepage.

## 1. Create the SVN repository on cicd-target

Clone this Git repository on `cicd-target`, then run:

```bash
git clone https://github.com/kelleyparker/jenkins-ansible-cicd-homelab.git
cd jenkins-ansible-cicd-homelab
sudo bash scripts/setup_svn.sh
sudo systemctl status cicd-svn --no-pager
```

The script asks for two different passwords (16+ ASCII letters/digits) and does
not print them. It installs Subversion, creates a dedicated system account,
creates `/srv/svn/cicd-site`, and starts `cicd-svn.service` on TCP 3690. It refuses
to overwrite an existing repository/service.

```text
svn://cicd-target/cicd-site/
├── trunk/index.html
├── branches/
└── tags/
```

- `jenkins-read`: read-only, for Jenkins checkout/polling.
- `lab-writer`: read/write, for your commits, branches and tags.

Passwords live in a mode-0600 file owned by the service account, outside Git.
Use the native `svn://` service only on the private lab network; it does not
provide TLS transport encryption. If UFW is enabled, allow 3690 from the runner
and whichever private workstation you use for SVN commits, using their real IPs.

## 2. Add Jenkins SVN credentials

Create a **Username with password** credential:

| Field | Value |
| --- | --- |
| ID | `lab-svn` |
| Username | `jenkins-read` |
| Password | Password entered during setup |

Build the pipeline manually with `USE_SVN=true` and the correct `SVN_URL`.
`RUN_DEPLOYMENT=false` is enough to test checkout and register SVN for polling.
The Subversion plugin reads the credential; no password is written in Jenkinsfile.
The CLI `svn info` step reads the local checkout's revision without network access.

## 3. Enable unattended polling with the intended parameters

SCM-triggered builds use parameter **defaults**, not a guarantee of the values
you selected on the previous manual build. Once SVN checkout works, change this
line in `Jenkinsfile` and commit it:

```groovy
booleanParam(name: 'USE_SVN', defaultValue: true,
```

To make polled changes proceed through the dry run and manual approval too,
also change `RUN_DEPLOYMENT` to `defaultValue: true` after SSH/bootstrap works.
Deployment still waits for approval every time. To keep automatic runs as
validation-only, leave `RUN_DEPLOYMENT` false and trigger deployment manually.

Run the job once after changing the defaults to update its job parameters and
establish the SVN checkout. The Jenkinsfile sets `pollSCM('H/2 * * * *')`, which
checks for changes about every two minutes. Both the checked-out Git repository
and SVN trunk are eligible to trigger builds. Several commits between polls may
be combined into one build; commits outside the checked-out SVN path need not
trigger a trunk build. GitHub inbound webhooks are not required.

## 4. Demonstrate an SVN-triggered deployment

On the runner or another private lab workstation with an SVN client:

```bash
svn checkout svn://cicd-target/cicd-site/trunk lab-site --username lab-writer --no-auth-cache
cd lab-site
# Edit index.html using your editor, then:
svn diff
svn commit -m 'Update lab homepage' --username lab-writer --no-auth-cache
```

Enter the password interactively when prompted. Wait for polling, inspect the
Jenkins changelog and dry-run output, approve, and verify the homepage changed
and `/build` matches the new Jenkins number on every target. The SVN checkout
is kept for that build; a commit during approval is picked up by a later build.

Optional examples of SVN's branch/tag layout (replace `build-42` appropriately):

```bash
svn copy svn://cicd-target/cicd-site/trunk svn://cicd-target/cicd-site/branches/demo -m 'Create demo branch' --username lab-writer --no-auth-cache
svn copy svn://cicd-target/cicd-site/trunk svn://cicd-target/cicd-site/tags/build-42 -m 'Tag reviewed version' --username lab-writer --no-auth-cache
```

For a tag that must match a specific deployed SVN revision, pass `-r REVISION`
with the revision from `artifacts/svn-revision.txt`; copying HEAD later may tag
newer content. Record the SVN revision separately from the Jenkins build number.
