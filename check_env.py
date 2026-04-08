"""
check_env.py — Pre-flight security and environment check.

Run before starting the pipeline:
    py check_env.py

Or import and call validate() at the top of any entry point.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Keys required for full autonomous operation
REQUIRED = {
    'ANTHROPIC_API_KEY':    'Claude AI scoring (orient.py)',
    'ELEVENLABS_API_KEY':   'TTS voice generation (produce.py)',
    'REDDIT_CLIENT_ID':     'Reddit scraping (observe.py)',
    'REDDIT_CLIENT_SECRET': 'Reddit scraping (observe.py)',
}

# Keys that are optional but recommended
OPTIONAL = {
    'REDDIT_USER_AGENT':     'Reddit scraping — defaults to MinecraftShortsBot/1.0',
    'ELEVENLABS_VOICE_ID':   'Voice ID — defaults to built-in voice',
    'MINECRAFT_FOOTAGE_URL': 'Footage source — defaults to built-in URL',
    'WHISPER_MODEL':         'Whisper model size — defaults to "base"',
}

SENSITIVE_PREFIXES = ('sk-', 'sk-ant-', 'xi_')


def _mask(value: str) -> str:
    """Show only first 6 + last 4 chars of a key."""
    if len(value) <= 10:
        return '*' * len(value)
    return value[:6] + '…' + value[-4:]


def _looks_like_placeholder(value: str) -> bool:
    return any(value.startswith(p) for p in ('your_', 'sk-ant-...', 'YOUR_'))


def validate(exit_on_fail: bool = True) -> bool:
    """
    Check all required env vars are set and don't look like placeholders.
    Returns True if all checks pass, False (or sys.exit) otherwise.
    """
    print('\n── Environment Security Check ────────────────────────────────')

    # Warn if .env file missing
    env_file = Path('.env')
    if not env_file.exists():
        print('  [WARN] No .env file found in current directory.')
        print('         Copy .env.example → .env and fill in your keys.\n')

    failures = []
    warnings = []

    # Required keys
    print('  Required:')
    for key, desc in REQUIRED.items():
        val = os.environ.get(key, '')
        if not val:
            print(f'    ✗ {key} — MISSING  ({desc})')
            failures.append(key)
        elif _looks_like_placeholder(val):
            print(f'    ✗ {key} — looks like a placeholder value')
            failures.append(key)
        else:
            print(f'    ✓ {key} = {_mask(val)}')

    # Optional keys
    print('  Optional:')
    for key, desc in OPTIONAL.items():
        val = os.environ.get(key, '')
        if val and not _looks_like_placeholder(val):
            print(f'    ✓ {key} = {_mask(val)}')
        else:
            print(f'    – {key} not set  ({desc})')
            warnings.append(key)

    # YouTube credentials file
    print('  Files:')
    if Path('client_secrets.json').exists():
        print('    ✓ client_secrets.json found')
    else:
        print('    – client_secrets.json not found (YouTube upload will fail)')
        warnings.append('client_secrets.json')

    # Summary
    print()
    if failures:
        print(f'  RESULT: {len(failures)} required key(s) missing — pipeline will not run.')
        print('  Fix:')
        for key in failures:
            print(f'    setx {key} your_actual_value   (CMD)')
            print(f'    # or add to .env file')
        print()
        if exit_on_fail:
            sys.exit(1)
        return False

    if warnings:
        print(f'  RESULT: OK (with {len(warnings)} optional item(s) not configured)')
    else:
        print('  RESULT: All checks passed — ready to run.')
    print('─' * 60 + '\n')
    return True


if __name__ == '__main__':
    validate(exit_on_fail=True)
