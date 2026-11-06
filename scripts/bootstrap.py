#!/usr/bin/env python3
"""Idempotent setup; host connector/UI actions stay in the invoking Agent."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from ima_config import discover, remember, skill_info

VERSION = '1.1.10'
URL = 'https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip'
SHA256 = '7e0d07cae0f98145dc5147e84b77bcc557e2fc4b256b08907922637952c20a7b'
AGENTS = ('auto', 'workbuddy', 'codex', 'claude-code', 'openclaw', 'other')


def parent_names():
    """Read executable names only, never command arguments or other process environments."""
    names, pid = [], os.getppid()
    if os.name == 'nt' or not shutil.which('ps'):
        return names
    for _ in range(6):
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'ppid=', '-o', 'comm='],
                                capture_output=True, text=True, timeout=3)
        parts = result.stdout.strip().split(maxsplit=1)
        if len(parts) != 2:
            break
        names.append(parts[1])
        pid = int(parts[0])
        if pid <= 1:
            break
    return names


def detect_agent(declared='auto', env=None, parents=None):
    env = os.environ if env is None else env
    if declared != 'auto':
        return {'name': declared, 'evidence': 'host_declared'}
    names = parent_names() if parents is None else parents
    for executable in names:
        lower = Path(executable).name.lower()
        for token, agent in (('workbuddy', 'workbuddy'), ('codex', 'codex'),
                             ('claude', 'claude-code'), ('openclaw', 'openclaw')):
            if token in lower:
                return {'name': agent, 'evidence': 'parent_executable'}
    terminal = env.get('TERM_PROGRAM', '').lower()
    if terminal == 'workbuddy':
        return {'name': 'workbuddy', 'evidence': 'terminal_identity'}
    # Active-session markers only; an installed app or config directory proves no active host.
    markers = [('CODEX_THREAD_ID', 'codex'), ('CODEX_SESSION_ID', 'codex'), ('CLAUDECODE', 'claude-code')]
    detected = {agent for key, agent in markers if env.get(key)}
    if len(detected) == 1:
        return {'name': detected.pop(), 'evidence': 'session_marker'}
    return {'name': 'other', 'evidence': 'unknown_or_ambiguous'}


def destination(agent, home, env):
    if agent == 'codex':
        return home / '.agents/skills/ima-skill'
    if agent == 'claude-code':
        return home / '.claude/skills/ima-skill'
    if agent == 'openclaw':
        return Path(env.get('OPENCLAW_STATE_DIR', home / '.openclaw')) / 'skills/ima-skill'
    return home / '.local/share/ima-skills'


def node_status():
    binary = shutil.which('node')
    if not binary:
        return {'ready': False, 'reason': 'node_missing'}
    try:
        result = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=10)
        match = re.fullmatch(r'v(\d+)\.\d+\.\d+\s*', result.stdout)
        return {'ready': result.returncode == 0 and bool(match) and int(match[1]) >= 18,
                'reason': 'node_18_required', 'version': result.stdout.strip() if match else 'unknown'}
    except (OSError, subprocess.TimeoutExpired):
        return {'ready': False, 'reason': 'node_unavailable'}


def credentials(home, env, apply=False):
    paths = [home / '.config/ima' / n for n in ('client_id', 'api_key')]
    existing = [p.read_text(encoding='utf-8').strip() if p.is_file() else '' for p in paths]
    if all(existing):
        return {'ready': True, 'source': 'files', 'written': 0}
    pairs = []
    for names in [('IMA_CLIENT_ID', 'IMA_API_KEY'), ('IMA_OPENAPI_CLIENTID', 'IMA_OPENAPI_APIKEY')]:
        pair = [env.get(n, '').strip() for n in names]
        if all(pair) and pair not in pairs:
            pairs.append(pair)
    if not pairs:
        return {'ready': False, 'reason': 'credentials_missing', 'written': 0}
    if len(pairs) != 1 or any(a and a != b for a, b in zip(existing, pairs[0])):
        return {'ready': False, 'reason': 'credential_conflict', 'written': 0}
    if not apply:
        return {'ready': False, 'reason': 'credentials_available_in_environment', 'written': 0}
    written = 0
    for path, old, value in zip(paths, existing, pairs[0]):
        if not old:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Never replace a nonempty credential; check again immediately before writing.
            if path.exists() and path.read_text(encoding='utf-8').strip():
                raise RuntimeError('credential_changed_during_setup')
            with path.open('w', encoding='utf-8') as stream:
                os.chmod(path, 0o600)
                stream.write(value + '\n')
            written += 1
    return {'ready': True, 'source': 'existing_environment_saved_locally', 'written': written}


def download():
    if os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
        raise RuntimeError('blocked_execution_network')
    with urllib.request.urlopen(URL, timeout=30) as response:
        return response.read(32 * 1024 * 1024 + 1)


def install_official(target, blob):
    if hashlib.sha256(blob).hexdigest() != SHA256:
        raise RuntimeError('official_archive_hash_mismatch')
    if target.exists():
        raise RuntimeError('existing_directory_preserved')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ima-install-', dir=target.parent) as temp:
        staged = Path(temp) / 'ima-skill'
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 32 * 1024 * 1024:
                raise RuntimeError('archive_too_large')
            for entry in archive.infolist():
                parts = PurePosixPath(entry.filename).parts
                if not parts or parts[0] != 'ima-skill':
                    continue
                if '..' in parts or '\\' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                    raise RuntimeError('unsafe_archive_entry')
                if '.history' in parts or '.DS_Store' in parts:
                    continue
                path = Path(temp).joinpath(*parts)
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('xb') as stream:
                        stream.write(archive.read(entry))
        info = skill_info(staged)
        if not info['complete'] or info['version'] != VERSION:
            raise RuntimeError('invalid_official_package')
        if target.exists():
            raise RuntimeError('existing_directory_preserved')
        staged.rename(target)


def verify_api(directory):
    from ima_ops import api
    data = api('wiki/v1/search_knowledge_base', {'query': '', 'cursor': '', 'limit': 1}, directory)
    if not isinstance(data.get('info_list'), list) or type(data.get('is_end')) is not bool:
        raise RuntimeError('invalid_probe_response')
    # This checks authentication/connectivity, not a particular KB or full inventory.
    return {'authenticated': True, 'target_verified': False}


def bootstrap(agent='auto', need='auto', explicit=None, apply=False,
              home=None, env=None, cwd=None, parents=None):
    home, env, cwd = home or Path.home(), os.environ if env is None else env, cwd or Path.cwd()
    host = detect_agent(agent, env, parents)
    route = 'connector' if need == 'connector' or (need == 'auto' and host['name'] == 'workbuddy') else 'api'
    result = {'agent': host['name'], 'detection': host['evidence'], 'route': route,
              'changed': [], 'next_actions': []}
    if route == 'connector':
        result.update(status='host_connector_check_required',
                      next_actions=['inspect_or_reuse_host_connector'])
        return result
    found = discover(home, env, cwd, explicit)
    if found['explicit_invalid']:
        return {**result, 'status': 'configuration_needs_repair', 'next_actions': ['repair_explicit_skill_path']}
    selected = found['selected']
    if not selected and found['found']:
        return {**result, 'status': 'existing_skill_incomplete', 'next_actions': ['inspect_existing_skill'],
                'existing': found['found']}
    target = Path(selected['path']) if selected else destination(host['name'], home, env)
    if not selected and target.exists():
        return {**result, 'status': 'existing_directory_preserved', 'next_actions': ['inspect_existing_skill']}
    if not selected:
        if apply:
            if env.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
                return {**result, 'status': 'blocked_execution_network', 'next_actions': []}
            install_official(target, download())
            selected = skill_info(target)
            result['changed'].append('official_skill_installed')
        else:
            result['next_actions'].append('install_official_skill')
    if selected:
        result['official_dir'] = str(target)
        result['official_version'] = selected['version']
        if apply and remember(home, target):
            result['changed'].append('official_path_saved')
    runtime, creds = node_status(), credentials(home, env, apply)
    result['node_ready'], result['credentials_ready'] = runtime['ready'], creds['ready']
    if not runtime['ready']:
        result['next_actions'].append('ensure_node_18_via_host')
    if creds['written']:
        result['changed'].append('existing_credentials_saved')
    if not creds['ready']:
        result['next_actions'].append(creds['reason'])
    result['status'] = 'needs_followup' if result['next_actions'] else 'configured_unverified'
    if apply and not result['next_actions']:
        if env.get('CODEX_SANDBOX_NETWORK_DISABLED') == '1':
            result['status'] = 'blocked_execution_network'
        else:
            result.update(verify_api(target), status='ready')
    return result


def main():
    parser = argparse.ArgumentParser(description='Detect, reuse, install missing official skill, then probe; compact output.')
    parser.add_argument('--agent', choices=AGENTS, default='auto', help='only needed if host identity is already known but not detectable')
    parser.add_argument('--need', choices=('auto', 'api', 'connector'), default='auto')
    parser.add_argument('--official-dir', help='reuse an existing official skill outside standard roots')
    parser.add_argument('--apply', action='store_true', help='install missing skill, save non-secret path, reuse existing credentials and probe')
    args = parser.parse_args()
    result = bootstrap(args.agent, args.need, args.official_dir, args.apply)
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return 0 if result['status'] in ('ready', 'configured_unverified', 'host_connector_check_required') else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Avoid upstream bodies, raw credential errors, subprocess stdout and tracebacks.
        error = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(json.dumps({'status': 'setup_failed', 'error': error}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
