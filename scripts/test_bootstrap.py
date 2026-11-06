import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import bootstrap as boot
import ima_config as cfg


def official(directory):
    for name in cfg.REQUIRED:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'version': boot.VERSION}) if name == 'meta.json' else 'fixture')
    return directory


def fixture_archive(extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as archive:
        for name in cfg.REQUIRED:
            text = json.dumps({'version': boot.VERSION}) if name == 'meta.json' else 'fixture'
            archive.writestr('ima-skill/' + name, text)
        if extra:
            archive.writestr(extra, 'bad')
    return buf.getvalue()


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()

    def test_host_detection_uses_running_context(self):
        self.assertEqual(boot.detect_agent(env={'CODEX_THREAD_ID': 'x'}, parents=[])['name'], 'codex')
        self.assertEqual(boot.detect_agent(env={}, parents=['/Applications/WorkBuddy.app/WorkBuddy'])['name'], 'workbuddy')
        self.assertEqual(boot.detect_agent(env={'CLAUDECODE': '1'}, parents=[])['name'], 'claude-code')
        self.assertEqual(boot.detect_agent(env={}, parents=['/usr/bin/openclaw'])['name'], 'openclaw')
        self.assertEqual(boot.detect_agent('workbuddy', {'CODEX_THREAD_ID': 'x'}, [])['name'], 'workbuddy')
        self.assertEqual(boot.detect_agent(env={'CODEX_THREAD_ID': 'x', 'CLAUDECODE': '1'}, parents=[])['name'], 'other')
        self.assertEqual(boot.detect_agent(env={}, parents=[])['name'], 'other')

    def test_workbuddy_route_does_not_install_or_read_credentials(self):
        with patch.object(boot, 'download') as download, patch.object(boot, 'credentials') as creds:
            result = boot.bootstrap('workbuddy', apply=True, home=self.home, env={}, parents=[])
            self.assertEqual(result['status'], 'host_connector_check_required')
            self.assertEqual(result['changed'], [])
            download.assert_not_called()
            creds.assert_not_called()

    def test_discovery_skips_operator_and_reuses_symlink(self):
        (self.home / '.agents/skills/ima-operator').mkdir(parents=True)
        unrelated = self.home / '.agents/skills/ima-other-tool'
        unrelated.mkdir()
        (unrelated / 'meta.json').write_text('{"version":"1"}')
        self.assertEqual(cfg.discover(self.home, {}, self.home)['found'], [])
        source = official(self.home / '.claude/skills/ima-skill')
        (self.home / '.agents/skills/ima-skill').symlink_to(source, target_is_directory=True)
        found = cfg.discover(self.home, {}, self.home)
        self.assertEqual(len(found['found']), 1)
        self.assertEqual(found['selected']['path'], str(source))

    def test_stale_cache_recovers_but_bad_explicit_path_does_not_switch(self):
        cfg.remember(self.home, self.home / 'deleted')
        source = official(self.home / '.agents/skills/ima-skill')
        self.assertEqual(cfg.discover(self.home, {}, self.home)['selected']['path'], str(source))
        self.assertTrue(cfg.discover(self.home, {}, self.home, self.home / 'wrong')['explicit_invalid'])

    def test_first_install_then_repeat_has_no_changes(self):
        data = fixture_archive()
        env = {'IMA_CLIENT_ID': 'fixture-client', 'IMA_API_KEY': 'fixture-api-key'}
        with patch.object(boot, 'SHA256', hashlib.sha256(data).hexdigest()), \
             patch.object(boot, 'download', return_value=data) as download, \
             patch.object(boot, 'node_status', return_value={'ready': True}), \
             patch.object(boot, 'verify_api', return_value={'authenticated': True, 'target_verified': False}):
            first = boot.bootstrap('codex', apply=True, home=self.home, env=env, cwd=self.home, parents=[])
            config = cfg.config_file(self.home)
            stamp = config.stat().st_mtime_ns
            second = boot.bootstrap('codex', apply=True, home=self.home, env=env, cwd=self.home, parents=[])
            self.assertEqual(first['status'], 'ready')
            self.assertEqual(second['changed'], [])
            self.assertEqual(second['status'], 'ready')
            self.assertEqual(config.stat().st_mtime_ns, stamp)
            self.assertEqual(download.call_count, 1)
            self.assertNotIn('fixture-api-key', json.dumps(first))
            self.assertNotIn('fixture-client', json.dumps(first))

    def test_reuses_existing_skill_without_network_download(self):
        source = official(self.home / '.claude/skills/ima-skill')
        boot.credentials(self.home, {'IMA_CLIENT_ID': 'x', 'IMA_API_KEY': 'y'}, apply=True)
        with patch.object(boot, 'download') as download, \
             patch.object(boot, 'node_status', return_value={'ready': True}), \
             patch.object(boot, 'verify_api', return_value={'authenticated': True}):
            result = boot.bootstrap('codex', apply=True, home=self.home, env={}, cwd=self.home, parents=[])
            self.assertEqual(result['official_dir'], str(source))
            self.assertFalse((self.home / '.agents/skills/ima-skill').exists())
            download.assert_not_called()

    def test_missing_node_returns_host_action_without_requesting_new_credentials(self):
        official(self.home / '.agents/skills/ima-skill')
        boot.credentials(self.home, {'IMA_CLIENT_ID': 'x', 'IMA_API_KEY': 'y'}, apply=True)
        with patch.object(boot, 'node_status', return_value={'ready': False}), patch.object(boot, 'verify_api') as verify:
            result = boot.bootstrap('codex', apply=True, home=self.home, env={}, cwd=self.home, parents=[])
            self.assertEqual(result['next_actions'], ['ensure_node_18_via_host'])
            verify.assert_not_called()

    def test_files_win_and_partial_credentials_never_mix_accounts(self):
        values = {'IMA_CLIENT_ID': 'one', 'IMA_API_KEY': 'secret-one'}
        boot.credentials(self.home, values, apply=True)
        result = boot.credentials(self.home, {'IMA_CLIENT_ID': 'two', 'IMA_API_KEY': 'secret-two'}, apply=True)
        self.assertEqual(result['source'], 'files')
        key = self.home / '.config/ima/api_key'
        self.assertEqual(key.read_text().strip(), 'secret-one')
        key.unlink()
        result = boot.credentials(self.home, {'IMA_CLIENT_ID': 'two', 'IMA_API_KEY': 'secret-two'}, apply=True)
        self.assertEqual(result['reason'], 'credential_conflict')
        self.assertFalse(key.exists())
        self.assertEqual(boot.credentials(self.home, values, apply=True)['written'], 1)

    def test_environment_conflict_and_readonly_plan(self):
        env = {'IMA_CLIENT_ID': 'a', 'IMA_API_KEY': 'b', 'IMA_OPENAPI_CLIENTID': 'c', 'IMA_OPENAPI_APIKEY': 'd'}
        self.assertEqual(boot.credentials(self.home, env, apply=True)['reason'], 'credential_conflict')
        self.assertFalse((self.home / '.config').exists())
        with patch.object(boot, 'node_status', return_value={'ready': True}), patch.object(boot, 'download') as download:
            result = boot.bootstrap('codex', home=self.home, env={}, cwd=self.home, parents=[])
            self.assertIn('install_official_skill', result['next_actions'])
            download.assert_not_called()

    def test_network_boundary_no_download_no_probe(self):
        with patch.object(boot, 'download') as download:
            result = boot.bootstrap('codex', apply=True, home=self.home,
                                    env={'CODEX_SANDBOX_NETWORK_DISABLED': '1'}, cwd=self.home, parents=[])
            self.assertEqual(result['status'], 'blocked_execution_network')
            download.assert_not_called()

    def test_incomplete_install_preserved(self):
        directory = self.home / '.agents/skills/ima-skill'
        directory.mkdir(parents=True)
        with patch.object(boot, 'download') as download:
            result = boot.bootstrap('codex', apply=True, home=self.home, env={}, cwd=self.home, parents=[])
            self.assertEqual(result['status'], 'existing_skill_incomplete')
            download.assert_not_called()
        self.assertEqual(list(directory.iterdir()), [])

    def test_tampered_archive_and_traversal_never_install(self):
        target = self.home / 'installed'
        with self.assertRaisesRegex(RuntimeError, 'hash_mismatch'):
            boot.install_official(target, b'invalid')
        data = fixture_archive('ima-skill/../../escape')
        with patch.object(boot, 'SHA256', hashlib.sha256(data).hexdigest()):
            with self.assertRaisesRegex(RuntimeError, 'unsafe_archive'):
                boot.install_official(target, data)
        self.assertFalse(target.exists())
        self.assertFalse((self.home / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
