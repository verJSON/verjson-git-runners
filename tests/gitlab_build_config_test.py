import copy
import json
import importlib.util
from pathlib import Path
import tomllib
import unittest

spec = importlib.util.spec_from_file_location('config', Path(__file__).resolve().parents[1] / 'scripts/gitlab_build_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def contract():
    result = {'registry': 'nexus.example.org', 'namespace': 'gitlab-jobs', 'architecture': 'amd64'}
    for index, (role, path) in enumerate((('build', 'ghcr.io/verjson/gha-runner-node'), ('manager', 'registry.gitlab.com/gitlab-org/gitlab-runner'), ('helper', 'registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper')), 1):
        digest = 'sha256:' + str(index) * 64
        result[role] = {'source': path + '@' + digest, 'destination': 'nexus.example.org/' + role + '@' + digest, 'version': '19.5.2'}
    return result


class BuildConfigTest(unittest.TestCase):
    def test_only_selected_producer_image_can_run_without_github_entrypoint(self):
        data = contract()
        runner = tomllib.loads(config.render(data))['runners'][0]
        self.assertFalse(runner['feature_flags']['FF_KUBERNETES_HONOR_ENTRYPOINT'])
        self.assertEqual(runner['kubernetes']['allowed_images'], [data['build']['destination']])
        self.assertNotIn(data['manager']['destination'], runner['kubernetes'].values())
        self.assertEqual(runner['kubernetes']['helper_image'], data['helper']['destination'])

    def test_reviewed_runtime_adds_only_its_exact_digest_to_job_allowlist(self):
        data = contract()
        data['runtime'] = {
            'sourceRepository': 'https://github.com/Verjson/verjson-ci',
            'sourceCommit': 'a' * 40,
            'destination': 'nexus.example.org/verjson/ci/candidates@sha256:' + '4' * 64,
            'artifactLicenseInventoryDigest': 'sha256:' + '5' * 64,
            'trust': 'reviewed-bootstrap-candidate',
        }
        allowed = tomllib.loads(config.render(data))['runners'][0]['kubernetes']['allowed_images']
        self.assertEqual(allowed, [data['build']['destination'], data['runtime']['destination']])
        for key, value in [
            ('sourceRepository', 'https://github.com/other/verjson-ci'),
            ('sourceCommit', 'main'),
            ('destination', 'evil.example.org/verjson/ci/candidates@sha256:' + '4' * 64),
            ('destination', 'nexus.example.org/verjson/ci/other@sha256:' + '4' * 64),
            ('destination', 'nexus.example.org/verjson/ci/candidates:latest'),
            ('artifactLicenseInventoryDigest', 'sha256:short'),
            ('trust', 'signed-stable-release'),
        ]:
            changed = copy.deepcopy(data)
            changed['runtime'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(config.ContractError):
                config.render(changed)

    def test_gitlab_183_jobs_satisfy_restricted_seccomp_without_privileged_accounts(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        settings = runner['kubernetes']
        self.assertTrue(runner['feature_flags']['FF_USE_ADVANCED_POD_SPEC_CONFIGURATION'])
        self.assertEqual(settings['pod_spec'][0], {
            'name': 'restricted-seccomp', 'patch_type': 'merge',
            'patch': json.dumps({'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}}}),
        })
        self.assertEqual(settings['service_account'], 'default')
        self.assertEqual(settings['pod_labels_overwrite_allowed'], '')
        self.assertEqual(settings['scripts_base_dir'], '/tmp')
        self.assertEqual(settings['logs_base_dir'], '/tmp')

    def test_nonroot_home_reaches_helper_and_build_without_replacing_containers(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        self.assertEqual(runner['environment'], ['HOME=/tmp'])
        patch = runner['kubernetes']['pod_spec'][1]
        self.assertEqual(patch['patch_type'], 'strategic')
        self.assertEqual(json.loads(patch['patch']), {'containers': [
            {'name': name, 'env': [{'name': 'HOME', 'value': '/tmp'}]}
            for name in ('build', 'helper')
        ]})

    def test_job_pull_auth_has_no_static_or_service_account_fallback(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        settings = runner['kubernetes']
        self.assertEqual(settings['image_pull_secrets'], [])
        self.assertFalse(settings['use_service_account_image_pull_secrets'])
        self.assertEqual(settings['pull_policy'], ['always'])
        self.assertEqual(settings['allowed_pull_policies'], ['always'])
        self.assertFalse(any(value.startswith('DOCKER_AUTH_CONFIG=') for value in runner['environment']))

    def test_bootstrap_pull_secret_is_scoped_to_manager_deployment_only(self):
        resources = json.loads((Path(__file__).resolve().parents[1] / 'deploy/gitlab/runner.json').read_text())['items']
        deployment = next(item for item in resources if item['kind'] == 'Deployment')
        self.assertEqual(deployment['spec']['template']['spec']['imagePullSecrets'], [{'name': 'nexus-manager-pull'}])
        for item in resources:
            if item['kind'] == 'ServiceAccount':
                self.assertNotIn('imagePullSecrets', item)
        self.assertFalse(any(item['kind'] == 'Secret' for item in resources))

    def test_jobs_have_nonroot_bounded_resources_without_host_mounts_or_credentials(self):
        parsed = tomllib.loads(config.render(contract()))
        self.assertEqual(parsed['concurrent'], 1)
        settings = parsed['runners'][0]['kubernetes']
        self.assertEqual(settings['pod_security_context']['run_as_user'], 1001)
        for name in ('privileged', 'allow_privilege_escalation', 'automount_service_account_token', 'bearer_token_overwrite_allowed'):
            self.assertFalse(settings[name])
        self.assertEqual(settings['cap_drop'], ['ALL'])
        volumes = settings['volumes']
        self.assertEqual(set(volumes), {'config_map'})
        for forbidden in ('host_path', 'secret', 'pvc', 'csi', 'nfs', 'empty_dir'):
            self.assertNotIn(forbidden, volumes)
        for prefix in ('', 'helper_'):
            for resource in ('cpu', 'memory', 'ephemeral_storage'):
                self.assertTrue(settings[prefix + resource + '_limit'])
        self.assertEqual(settings['allowed_pull_policies'], ['always'])

    def test_emits_read_only_public_approval_mounts_without_secrets(self):
        settings = tomllib.loads(config.render(contract()))['runners'][0]['kubernetes']
        mounts = settings['volumes']['config_map']
        self.assertEqual(mounts, [
            {'name': 'verjson-candidate-acquisition', 'mount_path': '/etc/verjson-candidate-acquisition', 'read_only': True},
            {'name': 'verjson-candidate-execution', 'mount_path': '/etc/verjson-candidate-execution', 'read_only': True},
            {'name': 'verjson-dependency-acquisition', 'mount_path': '/etc/verjson-dependency-acquisition', 'read_only': True},
        ])
        rendered = config.render(contract())
        for needle in ('host_path', '[[runners.kubernetes.volumes.secret]]', 'docker.sock', 'DOCKER_AUTH_CONFIG='):
            self.assertNotIn(needle, rendered)

    def test_admission_disables_service_links_and_labels_restricted_jobs(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        settings = runner['kubernetes']
        self.assertFalse(settings['enable_service_links'])
        self.assertEqual(settings['pod_labels'], {'verjson.io/isolation': 'restricted'})
        self.assertEqual(settings['pod_labels_overwrite_allowed'], '')
        self.assertEqual(settings['allowed_services'], ['services-disabled.invalid/no-image@sha256:' + '0' * 64])

    def test_egress_network_policy_is_credential_free_and_namespace_scoped(self):
        data = contract()
        policy = config.render_egress(data)
        self.assertEqual(policy['apiVersion'], 'networking.k8s.io/v1')
        self.assertEqual(policy['kind'], 'NetworkPolicy')
        self.assertEqual(policy['metadata']['namespace'], data['namespace'])
        self.assertEqual(policy['metadata']['name'], 'verjson-job-isolation')
        spec = policy['spec']
        self.assertEqual(spec['podSelector'], {'matchLabels': {'verjson.io/isolation': 'restricted'}})
        self.assertEqual(spec['policyTypes'], ['Ingress', 'Egress'])
        self.assertEqual(spec['ingress'], [])
        egress = spec['egress']
        self.assertEqual(egress[0]['ports'], [
            {'protocol': 'UDP', 'port': 53},
            {'protocol': 'TCP', 'port': 53},
        ])
        self.assertEqual(
            egress[0]['to'][0]['podSelector'],
            {'matchLabels': {'k8s-app': 'kube-dns'}},
        )
        public = egress[1]['to'][0]['ipBlock']
        self.assertEqual(public['cidr'], '0.0.0.0/0')
        isolation = next(
            item
            for item in json.loads(
                (Path(__file__).resolve().parents[1] / 'deploy/gitlab/runner.json').read_text()
            )['items']
            if item.get('kind') == 'NetworkPolicy' and item['metadata']['name'] == 'runner-isolation'
        )
        reviewed_public = next(
            rule['to'][0]['ipBlock']
            for rule in isolation['spec']['egress']
            if rule.get('to') and 'ipBlock' in rule['to'][0]
        )
        self.assertEqual(public['except'], reviewed_public['except'])
        self.assertEqual(egress[1]['ports'], [{'protocol': 'TCP', 'port': 443}])
        reviewed_ports = next(
            rule['ports']
            for rule in isolation['spec']['egress']
            if rule.get('to') and 'ipBlock' in rule['to'][0]
        )
        self.assertEqual(egress[1]['ports'], reviewed_ports)
        # Jobs-only selector must not grant Traefik :8443 (manager/API path).
        serialized = json.dumps(policy)
        self.assertNotIn('traefik', serialized.lower())
        self.assertNotIn('8443', serialized)
        for needle in ('password', 'token', 'secret', 'private_key', 'DOCKER_AUTH'):
            self.assertNotIn(needle.lower(), serialized.lower())

    def test_rejects_untrusted_mutable_or_mismatched_image_records(self):
        changes = [('build', 'destination', 'nexus.example.org/build:latest'), ('build', 'source', 'ghcr.io/other/image@sha256:' + '1' * 64), ('build', 'destination', 'evil.example.org/build@sha256:' + '1' * 64), ('build', 'destination', 'nexus.example.org/build@sha256:' + '9' * 64), ('manager', 'source', 'ghcr.io/verjson/gha-runner@sha256:' + '2' * 64), ('helper', 'version', '18.2.0'), ('helper', 'version', 'latest'), ('build', 'source', 'ghcrXio/verjson/gha-runner@sha256:' + '1' * 64), ('build', 'version', '01.2.3')]
        for role, field, value in changes:
            with self.subTest(role=role, field=field, value=value):
                data = contract()
                data[role][field] = value
                with self.assertRaises(config.ContractError):
                    config.render(data)

    def test_rejects_injection_and_unknown_settings(self):
        for field, value in [('registry', 'nexus.example.org/evil'), ('registry', 'nexus.example.org:99999'), ('namespace', 'jobs"\nprivileged=true'), ('architecture', 's390x'), ('extra', True), ('build', None)]:
            data = contract()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(config.ContractError):
                config.render(data)

    def test_arm64_uses_matching_node_selector_without_mutating_input(self):
        data = contract()
        data['architecture'] = 'arm64'
        before = copy.deepcopy(data)
        parsed = tomllib.loads(config.render(data))
        self.assertEqual(parsed['runners'][0]['kubernetes']['node_selector']['kubernetes.io/arch'], 'arm64')
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
