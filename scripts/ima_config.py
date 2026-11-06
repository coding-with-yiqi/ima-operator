"""Local discovery and non-secret configuration shared by setup and operations."""
import json
import os
from pathlib import Path
import tempfile

REQUIRED = ('SKILL.md', 'ima_api.cjs', 'meta.json', 'notes/SKILL.md',
            'notes/references/api.md', 'knowledge-base/SKILL.md', 'knowledge-base/references/api.md')


def config_file(home):
    return home / '.config/ima/operator.json'


def load_config(home):
    path = config_file(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise RuntimeError('invalid_operator_config') from None
    if not isinstance(data, dict):
        raise RuntimeError('invalid_operator_config')
    return data


def skill_info(path):
    missing = [name for name in REQUIRED if not (path / name).is_file()]
    try:
        metadata = json.loads((path / 'meta.json').read_text(encoding='utf-8'))
        version = metadata.get('version') if isinstance(metadata, dict) else None
    except (ValueError, OSError):
        version = None
    return {'path': str(path), 'complete': not missing and isinstance(version, str),
            'version': version, 'missing': missing}


def skill_roots(home, env, cwd):
    roots = [home / '.agents/skills', Path(env.get('CODEX_HOME', home / '.codex')) / 'skills',
             home / '.claude/skills', Path(env.get('OPENCLAW_STATE_DIR', home / '.openclaw')) / 'skills']
    roots += [cwd / '.agents/skills', cwd / '.claude/skills', cwd / 'skills']
    return roots


def discover(home=None, env=None, cwd=None, explicit=None):
    home, env, cwd = home or Path.home(), os.environ if env is None else env, cwd or Path.cwd()
    # An explicit current setting wins; an invalid one needs correction, not a silent switch.
    preferred = explicit or env.get('IMA_OFFICIAL_SKILL_DIR')
    if preferred:
        paths = [Path(preferred).expanduser().resolve()]
    else:
        cached = load_config(home).get('official_dir')
        paths = [Path(cached)] if isinstance(cached, str) else []
        paths.append(home / '.local/share/ima-skills')
        for root in skill_roots(home, env, cwd):
            if root.is_dir():
                paths.extend(p for p in sorted(root.iterdir()) if p.is_dir() and 'ima' in p.name.lower()
                             and (p.name in ('ima-skill', 'ima-skills') or (p / 'ima_api.cjs').is_file()))
    unique = {}
    for path in paths:
        path = path.resolve()
        if path.is_dir():
            unique[str(path)] = skill_info(path)
    healthy = [x for x in unique.values() if x['complete']]
    return {'selected': healthy[0] if healthy else None,
            'found': list(unique.values()), 'explicit_invalid': bool(preferred and not healthy)}


def resolve_official(explicit=None):
    chosen = explicit or os.environ.get('IMA_OFFICIAL_SKILL_DIR')
    if chosen:
        return Path(chosen).expanduser().resolve()
    found = discover()['selected']
    return Path(found['path']) if found else Path.home() / '.local/share/ima-skills'


def remember(home, directory):
    path = config_file(home)
    data = load_config(home)
    directory = str(directory.resolve())
    if data.get('official_dir') == directory:
        return False
    data['official_dir'] = directory
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.operator-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True
