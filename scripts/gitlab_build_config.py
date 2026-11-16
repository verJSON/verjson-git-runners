#!/usr/bin/env python3
"""Render a credential-free GitLab Kubernetes build-container configuration."""
import argparse
import json
import re
from pathlib import Path


class ContractError(ValueError):
    pass


# Root-owned, job-nonwritable public approval/trust/supervisor inputs only.
# Never emit hostPath, Secret, PVC, CSI, NFS, or Docker-socket mounts here.
ISOLATION_CONFIG_MAP_MOUNTS = (
    {'name': 'verjson-candidate-acquisition', 'mount_path': '/etc/verjson-candidate-acquisition'},
    {'name': 'verjson-candidate-execution', 'mount_path': '/etc/verjson-candidate-execution'},
    {'name': 'verjson-dependency-acquisition', 'mount_path': '/etc/verjson-dependency-acquisition'},
)

ISOLATION_POD_LABEL = 'verjson.io/isolation'
ISOLATION_POD_LABEL_VALUE = 'restricted'
# Match deploy/gitlab/runner.json runner-isolation public ipBlock.except order.
PRIVATE_EGRESS_EXCEPTIONS = (
    '10.0.0.0/8',
    '172.16.0.0/12',
    '192.168.0.0/16',
    '127.0.0.0/8',
    '169.254.0.0/16',
    '100.64.0.0/10',
    '224.0.0.0/4',
)


def require(condition, message):
    if not condition:
        raise ContractError(message)


def validate(contract):
    require(isinstance(contract, dict), 'contract must be an object')
    required = {'registry', 'namespace', 'architecture', 'build', 'manager', 'helper'}
    require(set(contract) in (required, required | {'runtime'}), 'unexpected contract fields')
    registry = contract['registry']
    require(isinstance(registry, str) and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+(?::[1-9][0-9]{0,4})?', registry), 'invalid Nexus registry host')
    require(':' not in registry or int(registry.rsplit(':', 1)[1]) <= 65535, 'invalid registry port')
    namespace = contract['namespace']
    require(isinstance(namespace, str) and len(namespace) <= 63 and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', namespace), 'invalid namespace')
    require(contract['architecture'] in ('amd64', 'arm64'), 'unsupported architecture')
    for role in ('build', 'manager', 'helper'):
        record = contract[role]
        require(isinstance(record, dict) and set(record) == {'source', 'destination', 'version'}, f'invalid {role} record')
        require(all(isinstance(value, str) for value in record.values()), f'invalid {role} values')
        source = record['source']
        destination = record['destination']
        require(re.fullmatch(r'[a-z0-9./_-]+@sha256:[0-9a-f]{64}', source), f'{role} source must be digest pinned')
        require(re.fullmatch(re.escape(registry) + r'/[a-z0-9]+(?:[._/-][a-z0-9]+)*@sha256:[0-9a-f]{64}', destination), f'{role} destination must be a Nexus digest reference')
        require(source.rsplit('@', 1)[1] == destination.rsplit('@', 1)[1], f'{role} promotion changed digest')
        require(re.fullmatch(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)', record['version']), f'{role} version must be explicit SemVer')
    require(re.fullmatch(r'ghcr\.io/verjson/gha-runner(?:-(?:node|python|go|rust|pwsh))?@sha256:[0-9a-f]{64}', contract['build']['source']), 'build must be a released Verjson producer image')
    require(contract['manager']['source'].startswith('registry.gitlab.com/gitlab-org/gitlab-runner@'), 'manager must be owned by GitLab')
    require(contract['helper']['source'].startswith('registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper@'), 'helper must be owned by GitLab')
    require(contract['manager']['version'] == contract['helper']['version'], 'manager/helper versions must match')
    require(len({contract[role]['destination'] for role in ('build', 'manager', 'helper')}) == 3, 'build, manager and helper must be distinct')
    allowed = [contract['build']['destination']]
    if 'runtime' in contract:
        runtime = contract['runtime']
        require(isinstance(runtime, dict) and set(runtime) == {'sourceRepository', 'sourceCommit', 'destination', 'artifactLicenseInventoryDigest', 'trust'}, 'invalid runtime record')
        require(all(isinstance(value, str) for value in runtime.values()), 'invalid runtime values')
        require(runtime['sourceRepository'] == 'https://github.com/Verjson/verjson-ci', 'runtime must identify the canonical CI source')
        require(re.fullmatch(r'[0-9a-f]{40}', runtime['sourceCommit']), 'runtime source must be immutable')
        require(re.fullmatch(re.escape(registry) + r'/verjson/ci/candidates@sha256:[0-9a-f]{64}', runtime['destination']), 'runtime must use the exact Nexus candidate path and digest')
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', runtime['artifactLicenseInventoryDigest']), 'runtime must bind its artifact-license inventory')
        require(runtime['trust'] == 'reviewed-bootstrap-candidate', 'runtime bootstrap trust must be explicit')
        allowed.append(runtime['destination'])
    return namespace, allowed


def render(contract):
    namespace, allowed = validate(contract)
    build = json.dumps(contract['build']['destination'])
    helper = json.dumps(contract['helper']['destination'])
    seccomp_patch = json.dumps({'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}}})
    home_patch = json.dumps({'containers': [
        {'name': name, 'env': [{'name': 'HOME', 'value': '/tmp'}]}
        for name in ('build', 'helper')
    ]})
    mounts = ''.join(
        f'''    [[runners.kubernetes.volumes.config_map]]
      name = {json.dumps(mount['name'])}
      mount_path = {json.dumps(mount['mount_path'])}
      read_only = true
'''
        for mount in ISOLATION_CONFIG_MAP_MOUNTS
    )
    return f'''# Install using manager image: {contract['manager']['destination']}
# Version/architecture and provenance must be verified from publication receipts.
# Isolation mounts are public ConfigMaps only; never secrets, hostPath, or sockets.
concurrent = 1
[[runners]]
  executor = "kubernetes"
  environment = ["HOME=/tmp"]
  shell = "bash"
  [runners.feature_flags]
    FF_USE_ADVANCED_POD_SPEC_CONFIGURATION = true
    FF_KUBERNETES_HONOR_ENTRYPOINT = false
    FF_USE_LEGACY_KUBERNETES_EXECUTION_STRATEGY = false
  [runners.kubernetes]
    namespace = {json.dumps(namespace)}
    image = {build}
    helper_image = {helper}
    allowed_images = {json.dumps(allowed)}
    allowed_services = ["services-disabled.invalid/no-image@sha256:{'0' * 64}"]
    pull_policy = ["always"]
    allowed_pull_policies = ["always"]
    image_pull_secrets = []
    use_service_account_image_pull_secrets = false
    enable_service_links = false
    privileged = false
    allow_privilege_escalation = false
    cap_drop = ["ALL"]
    automount_service_account_token = false
    bearer_token_overwrite_allowed = false
    namespace_overwrite_allowed = ""
    service_account_overwrite_allowed = ""
    service_account = "default"
    pod_labels_overwrite_allowed = ""
    scripts_base_dir = "/tmp"
    logs_base_dir = "/tmp"
    cpu_request = "500m"
    cpu_limit = "2"
    memory_request = "1Gi"
    memory_limit = "4Gi"
    ephemeral_storage_request = "1Gi"
    ephemeral_storage_limit = "8Gi"
    helper_cpu_request = "100m"
    helper_cpu_limit = "500m"
    helper_memory_request = "128Mi"
    helper_memory_limit = "512Mi"
    helper_ephemeral_storage_request = "128Mi"
    helper_ephemeral_storage_limit = "1Gi"
    [runners.kubernetes.pod_labels]
      {json.dumps(ISOLATION_POD_LABEL)} = {json.dumps(ISOLATION_POD_LABEL_VALUE)}
{mounts}    [runners.kubernetes.node_selector]
      "kubernetes.io/arch" = {json.dumps(contract['architecture'])}
    [[runners.kubernetes.pod_spec]]
    name = "restricted-seccomp"
    patch_type = "merge"
    patch = {json.dumps(seccomp_patch)}
  [[runners.kubernetes.pod_spec]]
    name = "nonroot-home"
    patch_type = "strategic"
    patch = {json.dumps(home_patch)}
  [runners.kubernetes.pod_security_context]
      run_as_non_root = true
      run_as_user = 1001
      run_as_group = 1001
      fs_group = 1001
    [runners.kubernetes.build_container_security_context]
      run_as_non_root = true
      run_as_user = 1001
      run_as_group = 1001
'''


def render_egress(contract):
    """Credential-free job NetworkPolicy template for review/apply with the runner config."""
    namespace, _allowed = validate(contract)
    return {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'NetworkPolicy',
        'metadata': {
            'name': 'verjson-job-isolation',
            'namespace': namespace,
        },
        'spec': {
            'podSelector': {
                'matchLabels': {
                    ISOLATION_POD_LABEL: ISOLATION_POD_LABEL_VALUE,
                },
            },
            'policyTypes': ['Ingress', 'Egress'],
            'ingress': [],
            'egress': [
                {
                    'to': [
                        {
                            'namespaceSelector': {
                                'matchLabels': {
                                    'kubernetes.io/metadata.name': 'kube-system',
                                },
                            },
                            'podSelector': {
                                'matchLabels': {
                                    'k8s-app': 'kube-dns',
                                },
                            },
                        },
                    ],
                    'ports': [
                        {'protocol': 'UDP', 'port': 53},
                        {'protocol': 'TCP', 'port': 53},
                    ],
                },
                {
                    'to': [
                        {
                            'ipBlock': {
                                'cidr': '0.0.0.0/0',
                                'except': list(PRIVATE_EGRESS_EXCEPTIONS),
                            },
                        },
                    ],
                    'ports': [
                        {'protocol': 'TCP', 'port': 443},
                    ],
                },
            ],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract', type=Path)
    parser.add_argument(
        '--egress',
        action='store_true',
        help='emit the credential-free job NetworkPolicy JSON instead of config.toml',
    )
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text())
        if args.egress:
            print(json.dumps(render_egress(contract), indent=2, sort_keys=True))
        else:
            print(render(contract), end='')
    except (ContractError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f'gitlab-build-config: {error}\n')


if __name__ == '__main__':
    main()
