#!/usr/bin/env python3
"""Small-output ima helpers. Credentials stay inside the official Node helper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from ima_config import resolve_official

READ = {'wiki/v1/' + x for x in ('search_knowledge_base', 'get_knowledge_base',
    'get_knowledge_list', 'get_addable_knowledge_base_list', 'search_knowledge',
    'get_media_info', 'check_repeated_names')}
READ |= {'note/v1/' + x for x in ('search_note', 'list_note', 'list_notebook', 'get_doc_content')}
WRITE = {'note/v1/import_doc', 'note/v1/append_doc', 'wiki/v1/add_knowledge', 'wiki/v1/import_urls'}
NODE = '''const fs=require('fs');const q=JSON.parse(fs.readFileSync(0,'utf8'));
const {imaApi}=require(q.helper);
imaApi(q.endpoint,q.body,{baseUrl:'https://ima.qq.com'}).then(r=>process.stdout.write(r))
.catch(e=>{process.stderr.write(JSON.stringify({code:e.code||-100}));process.exitCode=1});'''


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8', errors='strict'))


def save(path, data):
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # A fresh receipt must never overwrite an existing backup.
    with target.open('x', encoding='utf-8') as stream:
        os.chmod(target, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return str(target)


def api(endpoint, body, official=None, write=False):
    short = endpoint.removeprefix('openapi/')
    if short not in READ and not (write and short in WRITE):
        raise ValueError('endpoint_not_allowed_or_write_flag_missing')
    if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
        raise RuntimeError('blocked_execution_network')
    encoded = json.dumps(body, ensure_ascii=False)
    encoded.encode('utf-8', errors='strict')
    env = dict(os.environ)
    for key in ('IMA_CLIENT_ID', 'IMA_API_KEY', 'IMA_OPENAPI_CLIENTID',
                'IMA_OPENAPI_APIKEY', 'IMA_BASE_URL', 'IMA_SKILL_VERSION', 'IMA_LAST_CHECK_FILE'):
        env.pop(key, None)
    request = {'helper': str(resolve_official(official) / 'ima_api.cjs'),
               'endpoint': 'openapi/' + short, 'body': body}
    proc = subprocess.run(['node', '-e', NODE], input=json.dumps(request, ensure_ascii=False),
        text=True, encoding='utf-8', capture_output=True, timeout=60, env=env)
    if proc.returncode:
        try:
            code = json.loads(proc.stderr).get('code')
        except ValueError:
            code = 'unknown'
        raise RuntimeError(f'official_helper_failed:{code}')
    response = json.loads(proc.stdout)
    if type(response.get('code')) is not int or response['code'] != 0:
        raise RuntimeError(f'ima_business_error:{response.get("code")}')
    if not isinstance(response.get('data'), dict):
        raise RuntimeError('invalid_response_data')
    return response['data']


def pages(call, endpoint, body, field):
    cursor, seen, result = '', set(), []
    while True:
        data = call(endpoint, {**body, 'cursor': cursor})
        if not isinstance(data.get(field), list) or type(data.get('is_end')) is not bool:
            raise RuntimeError('invalid_pagination_schema')
        result.extend(data[field])
        if data['is_end']:
            return result
        cursor = data.get('next_cursor')
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise RuntimeError('missing_or_repeated_cursor')
        seen.add(cursor)


def snapshot(call, name):
    matches = pages(call, 'wiki/v1/search_knowledge_base', {'query': name, 'limit': 20}, 'info_list')
    matches = [x for x in matches if x.get('kb_name', x.get('name')) == name]
    if len(matches) != 1:
        raise RuntimeError('target_not_unique')
    kb = matches[0].get('kb_id', matches[0].get('id'))
    if not kb:
        raise RuntimeError('missing_knowledge_base_id')
    detail = call('wiki/v1/get_knowledge_base', {'ids': [kb]}).get('infos', {}).get(kb)
    if not detail or detail.get('id') != kb or detail.get('name') != name:
        raise RuntimeError('target_detail_mismatch')
    queue, items, seen = [None], [], set()
    while queue:
        folder = queue.pop(0)
        body = {'knowledge_base_id': kb, 'limit': 50}
        if folder:
            body['folder_id'] = folder
        for raw in pages(call, 'wiki/v1/get_knowledge_list', body, 'knowledge_list'):
            item = dict(raw)
            if 'folder_id' in item and 'media_id' not in item:
                item.update(media_id=item['folder_id'], media_type=99, title=item.get('name'))
            mid = item.get('media_id')
            if not mid or mid in seen or 'media_type' not in item:
                raise RuntimeError('missing_or_repeated_media_id_or_type')
            seen.add(mid)
            items.append(item)
            if item['media_type'] == 99:
                queue.append(mid)
    return {'knowledge_base_id': kb, 'name': name, 'complete': True,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'items': items}


def indexed(snapshot_data):
    if snapshot_data.get('complete') is not True:
        raise ValueError('incomplete_snapshot')
    result = {x['media_id']: x for x in snapshot_data['items']}
    if len(result) != len(snapshot_data['items']):
        raise ValueError('duplicate_snapshot_ids')
    return result


def candidates(snapshot_data, manifest):
    items = indexed(snapshot_data)
    evidence = {x['media_id']: x for x in manifest}
    if len(evidence) != len(manifest) or not set(evidence) <= set(items):
        raise ValueError('invalid_manifest_ids')
    groups = {}
    for mid, item in items.items():
        if item['media_type'] == 99:
            continue
        title = ' '.join(unicodedata.normalize('NFC', item['title']).split())
        if title.lower().endswith('.md'):
            title = title[:-3]
        keys = [('title_candidate', title)]
        ev = evidence.get(mid, {})
        if ev.get('source_key'):
            keys.append(('source_candidate', ev['source_key']))
        if ev.get('sha256') and ev.get('hash_type'):
            keys.append(('hash_candidate', ev['hash_type'] + ':' + ev['sha256']))
        for key in keys:
            groups.setdefault(key, []).append(mid)
    return {'candidate_only': True, 'delete_authorized': False, 'groups': [
        {'reason': reason, 'key': key, 'media_ids': ids}
        for (reason, key), ids in groups.items() if len(ids) > 1]}


def audit(before, after, approved):
    if not before.get('knowledge_base_id') or not (before['knowledge_base_id'] ==
            after.get('knowledge_base_id') == approved.get('knowledge_base_id')):
        raise ValueError('knowledge_base_mismatch')
    a, b = indexed(before), indexed(after)
    plan = set(approved['media_ids'])
    if len(plan) != len(approved['media_ids']) or not plan <= set(a):
        raise ValueError('invalid_approved_set')
    removed, added = set(a) - set(b), set(b) - set(a)
    changed = [mid for mid in set(a) & set(b) if any(a[mid].get(k) != b[mid].get(k)
               for k in ('title', 'parent_folder_id', 'media_type'))]
    return {'ok': removed == plan and not added and not changed,
        'removed': len(removed), 'pending': sorted(plan - removed),
        'unexpected_removals': sorted(removed - plan), 'unexpected_additions': sorted(added),
        'metadata_changed': sorted(changed), 'bodies_verified': False}


def note_backup(call, note_id):
    def content(fmt):
        value = call('note/v1/get_doc_content', {'note_id': note_id, 'target_content_format': fmt})['content']
        if not isinstance(value, str):
            raise ValueError('invalid_note_content')
        return value
    plain, rich = content(0), json.loads(content(2))
    # Detect concurrent edits while the two representations were being read.
    if content(0) != plain:
        raise RuntimeError('note_changed_during_backup')
    return {'note_id': note_id, 'plain': plain, 'rich': rich,
            'plain_sha256': hashlib.sha256(plain.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description='ima: save full results locally; print short receipts.')
    parser.add_argument('--official-dir', help='override the automatically discovered official skill path')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, args in {'snapshot': ['name'], 'note': ['id'], 'candidates': ['snapshot'],
                       'audit': ['before', 'after', 'approved'], 'call': ['endpoint', 'request']}.items():
        sub = commands.add_parser(name)
        for arg in args:
            sub.add_argument('--' + arg, required=True)
        sub.add_argument('--out', required=True, help='new local receipt file; existing files are not overwritten')
        if name == 'candidates':
            sub.add_argument('--manifest')
        if name == 'call':
            sub.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if Path(args.out).expanduser().exists():
        raise FileExistsError('receipt_already_exists')
    call = lambda endpoint, body: api(endpoint, body, args.official_dir)
    if args.command == 'snapshot':
        data = snapshot(call, args.name)
        summary = {'knowledge_base_id': data['knowledge_base_id'], 'complete': True,
            'files': sum(x['media_type'] != 99 for x in data['items']),
            'folders': sum(x['media_type'] == 99 for x in data['items'])}
    elif args.command == 'note':
        data = note_backup(call, args.id)
        summary = {'note_id': args.id, 'characters': len(data['plain']), 'sha256': data['plain_sha256']}
    elif args.command == 'candidates':
        data = candidates(read(args.snapshot), read(args.manifest) if args.manifest else [])
        summary = {'candidate_groups': len(data['groups']), 'candidate_only': True}
    elif args.command == 'audit':
        data = audit(read(args.before), read(args.after), read(args.approved))
        summary = data
    else:
        data = api(args.endpoint, read(args.request), args.official_dir, args.write)
        summary = {'code': 0, **{k: data[k] for k in ('note_id', 'media_id') if k in data}}
    output = save(args.out, data)
    print(json.dumps({**summary, 'receipt': output}, ensure_ascii=False, separators=(',', ':')))
    if args.command == 'audit' and not data['ok']:
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Never expose raw upstream responses, URLs, request content or credentials.
        message = str(exc) if isinstance(exc, (RuntimeError, ValueError, FileExistsError)) else type(exc).__name__
        if isinstance(exc, (json.JSONDecodeError, UnicodeError)):
            message = 'invalid_json_or_utf8'
        print(json.dumps({'error': message}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
