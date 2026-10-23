pipeline {
    agent { label 'cicd-runner' }

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 60, unit: 'MINUTES')
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    parameters {
        booleanParam(name: 'RUN_DEPLOYMENT', defaultValue: false,
                     description: 'Run remote dry run, approval, deployment and smoke tests.')
        booleanParam(name: 'USE_SVN', defaultValue: false,
                     description: 'Deploy the SVN trunk homepage instead of the Git seed.')
        string(name: 'SVN_URL', defaultValue: 'svn://cicd-target/cicd-site/trunk',
               description: 'Lab SVN trunk URL; used only when USE_SVN is enabled.')
        string(name: 'SVN_CREDENTIALS_ID', defaultValue: 'lab-svn',
               description: 'Jenkins username/password credential ID for the SVN reader.')
    }

    environment {
        PATH = "${WORKSPACE}/.venv/bin:${env.PATH}"
        INVENTORY = 'inventories/lab/hosts.ini'
        PYTHONUNBUFFERED = '1'
    }

    stages {
        stage('Checkout Git') {
            steps {
                deleteDir()
                checkout scm
                sh 'mkdir -p artifacts'
            }
        }

        stage('Install validation tools') {
            steps {
                sh '''
                    python3 -m venv .venv
                    python -m pip install -r requirements-dev.txt
                    python -m pip freeze > artifacts/python-packages.txt
                '''
            }
        }

        stage('YAML lint') {
            steps { sh 'yamllint .' }
        }

        stage('Ansible lint') {
            steps { sh 'ansible-lint playbooks/ roles/' }
        }

        stage('Unit tests') {
            steps {
                sh 'python -m pytest tests/unit/ -q --junitxml=artifacts/unit-tests.xml'
            }
            post {
                always { junit testResults: 'artifacts/unit-tests.xml' }
            }
        }

        stage('Ansible syntax checks') {
            steps {
                sh '''
                    ansible-playbook -i "$INVENTORY" playbooks/bootstrap.yml --syntax-check
                    ansible-playbook -i "$INVENTORY" playbooks/deploy.yml --syntax-check
                '''
            }
        }

        stage('Checkout website content') {
            steps {
                script {
                    if (params.USE_SVN) {
                        dir('site-content') {
                            checkout changelog: true, poll: true, scm: [
                                $class: 'SubversionSCM',
                                locations: [[
                                    remote: params.SVN_URL,
                                    credentialsId: params.SVN_CREDENTIALS_ID,
                                    local: '.',
                                    depthOption: 'infinity',
                                    ignoreExternalsOption: true
                                ]],
                                workspaceUpdater: [$class: 'UpdateUpdater']
                            ]
                        }
                        sh 'svn info --show-item revision site-content > artifacts/svn-revision.txt'
                    } else {
                        sh 'mkdir -p site-content && cp svn-seed/trunk/index.html site-content/index.html'
                    }
                }
                sh '''
                    python scripts/prepare_deploy.py --build "$BUILD_NUMBER" \
                        --content-dir "$WORKSPACE/site-content"
                    ansible-inventory -i "$INVENTORY" --list > artifacts/inventory.json
                '''
            }
        }

        stage('Ansible dry run and diff') {
            when { expression { params.RUN_DEPLOYMENT } }
            steps {
                sshagent(credentials: ['lab-ssh']) {
                    sh '''#!/usr/bin/env bash
                        set -euo pipefail
                        ansible-playbook -i "$INVENTORY" playbooks/deploy.yml \
                            -e @artifacts/deploy-vars.json --check --diff \
                            | tee artifacts/dry-run.txt
                    '''
                }
            }
        }

        stage('Approve deployment') {
            when { expression { params.RUN_DEPLOYMENT } }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    input message: "Review the dry-run diff. Deploy build ${env.BUILD_NUMBER} to all nginx hosts?",
                          ok: 'Deploy'
                }
            }
        }

        stage('Deploy NGINX') {
            when { expression { params.RUN_DEPLOYMENT } }
            steps {
                sshagent(credentials: ['lab-ssh']) {
                    sh '''#!/usr/bin/env bash
                        set -euo pipefail
                        ansible-playbook -i "$INVENTORY" playbooks/deploy.yml \
                            -e @artifacts/deploy-vars.json --diff \
                            | tee artifacts/deploy.txt
                    '''
                }
            }
        }

        stage('Smoke-test every target') {
            when { expression { params.RUN_DEPLOYMENT } }
            steps {
                sh '''
                    python scripts/smoke_test.py --inventory artifacts/inventory.json \
                        --expected-build "$BUILD_NUMBER"
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'artifacts/**', allowEmptyArchive: true
        }
    }
}
