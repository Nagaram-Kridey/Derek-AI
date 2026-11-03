"""Read-only pre-publish guard. Reports paths/categories, never secret values."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    secret_values = []
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            key, sep, value = line.partition('=')
            value = value.strip().strip('"').strip("'")
            if sep and re.search(r'KEY|TOKEN|SECRET|PASSWORD', key, re.I) and len(value) > 12:
                secret_values.append(value.encode())
    config = ROOT / '.trial-workspace/config.json'
    if config.exists():
        for key, value in json.loads(config.read_text()).items():
            if isinstance(value, str) and len(value) > 12 and re.search(r'key|token|secret|password', key, re.I):
                secret_values.append(value.encode())
    forbidden = re.compile(r'(^|/)(\.env($|\.)|\.trial-workspace/|\.companion/|output/|\.playwright-cli/|graphify-out/)|\.(sqlite3?|db|pem|pfx|mp4|wav)$', re.I)
    patterns = re.compile(rb'AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----')
    findings = []
    for raw_path in git('ls-files', '-z').split(b'\0'):
        if not raw_path:
            continue
        path = raw_path.decode('utf-8')
        if forbidden.search(path) and not path.endswith('.env.example'):
            findings.append((path, 'private/generated file tracked'))
        # Inspect staged content, not just the working copy.
        body = git('show', ':' + path)
        if patterns.search(body) or any(value in body for value in secret_values):
            findings.append((path, 'possible credential in Git index'))
    for folder in ('web_dashboard/dist', 'backend/staticapp', '.trial-workspace/dashboard'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and path.suffix in {'.js', '.html', '.css', '.map'}:
                body = path.read_bytes()
                if patterns.search(body) or any(value in body for value in secret_values):
                    findings.append((str(path.relative_to(ROOT)), 'possible credential in browser assets'))
    for path, reason in findings:
        print(f'{reason}: {path}')
    print(f'Publish safety check: {len(findings)} finding(s). No files changed.')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
