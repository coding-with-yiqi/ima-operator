import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ima_ops as ops


def snap(items):
    return {'knowledge_base_id': 'kb', 'complete': True, 'items': items}


def item(mid, title='A', folder='kb', kind=7):
    return {'media_id': mid, 'title': title, 'parent_folder_id': folder, 'media_type': kind}


class Invariants(unittest.TestCase):
    def test_paging_reads_final_page(self):
        responses = iter([{'rows': [1], 'is_end': False, 'next_cursor': 'b'},
                          {'rows': [2], 'is_end': True}])
        cursors = []
        def call(_, body):
            cursors.append(body['cursor'])
            return next(responses)
        self.assertEqual(ops.pages(call, 'x', {}, 'rows'), [1, 2])
        self.assertEqual(cursors, ['', 'b'])

    def test_repeated_cursor_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, 'cursor'):
            ops.pages(lambda *_: {'rows': [1], 'is_end': False, 'next_cursor': 'b'}, 'x', {}, 'rows')

    def test_snapshot_resolves_actual_fields_and_subfolder(self):
        def call(endpoint, body):
            if endpoint.endswith('search_knowledge_base'):
                return {'info_list': [{'kb_id': 'kb', 'kb_name': '目标'}], 'is_end': True}
            if endpoint.endswith('get_knowledge_base'):
                return {'infos': {'kb': {'id': 'kb', 'name': '目标'}}}
            rows = [item('n', '正文', 'f', 11)] if body.get('folder_id') == 'f' else [item('f', '目录', kind=99)]
            return {'knowledge_list': rows, 'is_end': True}
        self.assertEqual(len(ops.snapshot(call, '目标')['items']), 2)

    def test_titles_only_are_candidates_and_dates_stay_distinct(self):
        data = snap([item('1', '标题.md'), item('2', '标题'), item('3', '周报 01'), item('4', '周报 02')])
        result = ops.candidates(data, [])
        self.assertTrue(result['candidate_only'])
        self.assertFalse(result['delete_authorized'])
        self.assertEqual(result['groups'][0]['media_ids'], ['1', '2'])
        self.assertEqual(len(result['groups']), 1)

    def test_hash_types_do_not_mix(self):
        manifest = [{'media_id': '1', 'sha256': 'a', 'hash_type': 'file'},
                    {'media_id': '2', 'sha256': 'a', 'hash_type': 'plain'}]
        self.assertEqual(ops.candidates(snap([item('1', 'A'), item('2', 'B')]), manifest)['groups'], [])

    def test_delete_audit_rejects_wrong_item_or_metadata_change(self):
        before = snap([item('old'), item('keep')])
        approved = {'knowledge_base_id': 'kb', 'media_ids': ['old']}
        self.assertTrue(ops.audit(before, snap([item('keep')]), approved)['ok'])
        self.assertFalse(ops.audit(before, snap([item('old')]), approved)['ok'])
        self.assertFalse(ops.audit(before, snap([item('keep', folder='elsewhere')]), approved)['ok'])
        incomplete = {**before, 'complete': False}
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            ops.audit(incomplete, before, approved)

    def test_writes_unknown_endpoints_and_network_blocked(self):
        with patch.object(ops.subprocess, 'run') as run:
            for endpoint in ('note/v1/import_doc', 'wiki/v1/delete'):
                with self.assertRaisesRegex(ValueError, 'not_allowed'):
                    ops.api(endpoint, {})
            with patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '1'}):
                with self.assertRaisesRegex(RuntimeError, 'blocked_execution_network'):
                    ops.api('note/v1/get_doc_content', {})
            run.assert_not_called()

    def test_business_error_and_secret_environment(self):
        response = type('Response', (), {'returncode': 0, 'stdout': json.dumps({'code': 403, 'data': {}})})()
        with patch.dict(os.environ, {'IMA_API_KEY': 'not-a-real-key', 'CODEX_SANDBOX_NETWORK_DISABLED': '0'}):
            with patch.object(ops.subprocess, 'run', return_value=response) as run:
                with self.assertRaisesRegex(RuntimeError, 'business_error:403'):
                    ops.api('note/v1/get_doc_content', {})
                self.assertNotIn('IMA_API_KEY', run.call_args.kwargs['env'])

    def test_backup_does_not_overwrite_and_detects_concurrent_change(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / 'backup.json'
            ops.save(filename, {'original': True})
            with self.assertRaises(FileExistsError):
                ops.save(filename, {'original': False})
            self.assertTrue(ops.read(filename)['original'])
        responses = iter(['before', '{}', 'after'])
        with self.assertRaisesRegex(RuntimeError, 'changed_during_backup'):
            ops.note_backup(lambda *_: {'content': next(responses)}, 'id')


if __name__ == '__main__':
    unittest.main()
