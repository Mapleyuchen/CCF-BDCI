"""Check this sample's layout, byte integrity and declared outstanding materials.

Unlike the old generic checker, this accepts the actual sample's spaced reviewer
directory and config.yaml containing only environment-variable credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(bundle):
    return sorted(p for p in bundle.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')


def write_manifest(bundle):
    content = ''.join(f'{sha256(p)}  {p.relative_to(bundle).as_posix()}\n' for p in files(bundle))
    (bundle / 'SHA256SUMS.txt').write_text(content, encoding='utf-8')


def verify(bundle, destination=None):
    checks = []

    def check(name, passed, detail):
        checks.append({'check': name, 'passed': bool(passed), 'detail': detail})

    required = ['paper/paper.pdf', 'Agentic Reviewer/PaperReview-AccessToken.txt',
                'code/main.py', 'code/config.yaml', 'code/requirements.txt', 'code/run_guide.md',
                'docs/architecture.md', 'docs/module_call.md', 'docs/innovation.md',
                'framework_contribution.md', 'resource_report.md', '提交说明.md',
                'evidence/package_status.json', 'evidence/source_export.json', 'SHA256SUMS.txt']
    missing = [name for name in required if not (bundle / name).is_file()]
    check('required_files', not missing, missing)
    empty = [name for name in required if (bundle / name).is_file()
             and name != 'Agentic Reviewer/PaperReview-AccessToken.txt'
             and (bundle / name).stat().st_size == 0]
    check('nonempty_materials', not empty, empty)
    try:
        status = json.loads((bundle / 'evidence/package_status.json').read_text(encoding='utf-8'))
        paper = bundle / 'paper/paper.pdf'
        check('pdf_header_and_hash', paper.read_bytes().startswith(b'%PDF-') and
              sha256(paper) == status['paper_sha256'], 'Must match the packaged candidate PDF.')
        check('team_name', isinstance(status.get('team_name'), str) and bool(status['team_name'].strip()),
              'Fill the official team name and rename the final top-level folder.')
        token = (bundle / 'Agentic Reviewer/PaperReview-AccessToken.txt').read_text(encoding='utf-8').strip()
        check('reviewer_token', len(token) >= 8 and not re.search('todo|placeholder|待|your.token|xxx', token, re.I),
              'A real review token is required. This check cannot authenticate it.')
        check('reviewer_pdf_binding', status.get('reviewed_pdf_sha256') == sha256(paper),
              'Record the hash of the PDF actually reviewed by Agentic Reviewer.')
        pr = status.get('upstream_pr_url') or ''
        check('upstream_pr', bool(re.match(r'https://[^/]+/.+/(?:pull/\d+|pulls/\d+|merge_requests/\d+)', pr)),
              'Real upstream PR URL remains required; repository commit links are not PRs.')
        check('human_review', status.get('human_review_completed') is True,
              'Manual claim and citation review remains required.')
    except (OSError, ValueError, KeyError) as error:
        check('package_status', False, str(error))

    integrity = []
    try:
        manifest = {}
        for line in (bundle / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            expected, name = line.split('  ', 1)
            path = (bundle / name).resolve()
            if not path.is_relative_to(bundle.resolve()) or not path.is_file() or sha256(path) != expected:
                integrity.append(name)
            manifest[name] = expected
        actual = {p.relative_to(bundle).as_posix() for p in files(bundle)}
        integrity.extend(sorted(actual.symmetric_difference(manifest)))
        check('file_integrity', not integrity, integrity)
    except (OSError, ValueError) as error:
        check('file_integrity', False, str(error))

    try:
        exported = json.loads((bundle / 'evidence/source_export.json').read_text(encoding='utf-8'))
        changed = [item['repository_path'] for item in exported['files']
                   if not (bundle / 'code/project' / item['repository_path']).is_file()
                   or sha256(bundle / 'code/project' / item['repository_path']) != item['sha256']]
        check('source_snapshot', not changed, changed)
    except (OSError, ValueError, KeyError) as error:
        check('source_snapshot', False, str(error))

    findings = []
    pattern = re.compile(rb'\bsk-[A-Za-z0-9_-]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    # A deliberately invalid key literal belongs to the unchanged secret-scanner unit test.
    dummy = b'sk-' + b'livekeyvalue1234567890'
    private_values = [v.encode() for k, v in os.environ.items()
                      if re.search(r'API_KEY|ACCESS_TOKEN|SECRET', k, re.I) and len(v) >= 20]
    for path in files(bundle):
        relative = path.relative_to(bundle).as_posix()
        if relative == 'Agentic Reviewer/PaperReview-AccessToken.txt':
            continue
        if path.name in {'.env', 'credentials.json', 'id_rsa', 'id_ed25519'} or any(
            part in {'.git', 'node_modules', '__pycache__', '.venv'} for part in path.relative_to(bundle).parts
        ):
            findings.append(relative)
            continue
        data = path.read_bytes()
        matches = [m.group() for m in pattern.finditer(data)]
        allow_dummy = relative.endswith('/tests/test_submission.py') or relative == 'contributions/74e5820.patch'
        if any(value != dummy or not allow_dummy for value in matches) or any(value in data for value in private_values):
            findings.append(relative)
    check('credential_and_cache_scan', not findings, findings)
    for name in ['config.yaml', 'config.experiment.yaml']:
        config_path = bundle / 'code' / name
        if not config_path.is_file():
            check(name + '_env_credential', False, 'Missing configuration file.')
            continue
        content = config_path.read_text(encoding='utf-8')
        values = re.findall(r'^\s*api_key:\s*(.*?)\s*$', content, re.M)
        check(name + '_env_credential', bool(values) and all(
            re.fullmatch(r'\$\{[A-Z_][A-Z_0-9]*\}', value) for value in values),
            'API credentials must be environment placeholders.')
    report = {'ready_for_submission': all(c['passed'] for c in checks),
              'passed': sum(c['passed'] for c in checks),
              'failed': sum(not c['passed'] for c in checks), 'checks': checks}
    destination = (destination or bundle.parent / (bundle.name + '.validation.json')).resolve()
    if destination.is_relative_to(bundle.resolve()):
        raise ValueError('Write validation reports outside the bundle to preserve its manifest.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ready_for_submission': report['ready_for_submission'], 'passed': report['passed'],
                      'failed': report['failed'], 'outstanding': [c for c in checks if not c['passed']],
                      'report': str(destination)}, ensure_ascii=False, indent=2))
    return 0 if report['ready_for_submission'] else 2
