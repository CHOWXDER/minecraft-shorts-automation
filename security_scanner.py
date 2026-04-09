"""
security_scanner.py — Pre-flight script security audit.

Scans Python files for patterns that could indicate malware, telemetry,
credential theft, or unwanted network calls before any script is run.

Usage:
    py security_scanner.py                    # scan all .py files
    py security_scanner.py produce.py         # scan specific file
    py security_scanner.py --strict           # exit 1 if any HIGH finding

Integrate in pipeline:
    from security_scanner import scan_files, Severity
    results = scan_files(["produce.py", "orient.py"])
    if any(r.severity == Severity.HIGH for r in results):
        sys.exit("Security scan failed")
"""

import ast
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    HIGH = "HIGH"


@dataclass
class Finding:
    file: str
    line: int
    severity: Severity
    rule: str
    detail: str

    def __str__(self) -> str:
        icon = {"INFO": "ℹ", "WARN": "⚠", "HIGH": "✗"}[self.severity.value]
        return f"  {icon} [{self.severity.value}] {self.file}:{self.line}  {self.rule}: {self.detail}"


# ── Rule definitions ──────────────────────────────────────────────────────────

# Domains the pipeline legitimately contacts
ALLOWED_DOMAINS = {
    "reddit.com", "www.reddit.com",
    "youtube.com", "www.youtube.com", "youtu.be",
    "localhost", "127.0.0.1", "0.0.0.0",
    "api.elevenlabs.io",       # optional premium TTS
    "googleapis.com",          # YouTube upload OAuth
    "accounts.google.com",
    "oauth2.googleapis.com",
    "pypi.org",                # pip installs (not in prod code)
}

# Patterns always considered dangerous regardless of context
_HIGH_PATTERNS = [
    (r"\beval\s*\(", "eval() executes arbitrary code"),
    (r"\bexec\s*\(", "exec() executes arbitrary code"),
    (r"__import__\s*\(", "__import__() dynamic import — verify intent"),
    (r"pickle\.loads?\s*\(", "pickle.load() can execute arbitrary code"),
    (r"os\.system\s*\(", "os.system() — use subprocess with explicit args instead"),
    (r"subprocess\.call\s*\(.*shell\s*=\s*True", "shell=True in subprocess — command injection risk"),
    (r"subprocess\.run\s*\(.*shell\s*=\s*True", "shell=True in subprocess — command injection risk"),
    (r"subprocess\.Popen\s*\(.*shell\s*=\s*True", "shell=True in subprocess — command injection risk"),
]

_WARN_PATTERNS = [
    (r"(?i)(password|passwd|secret|api_key|token)\s*=\s*['\"][^'\"]{6,}", "Possible hard-coded credential"),
    (r"base64\.b64decode\s*\(", "base64 decode — verify this is not obfuscating malicious payload"),
    (r"urllib\.request\.urlopen|httplib|http\.client", "Low-level HTTP — ensure destination is trusted"),
    (r"socket\.connect\s*\(", "Raw socket connection — verify destination"),
    (r"ctypes\.(cdll|windll|CDLL)", "ctypes native call — verify intent"),
    (r"import\s+keyring", "keyring access — ensure not extracting stored credentials"),
]

_TELEMETRY_DOMAINS = [
    "sentry.io", "bugsnag.com", "datadog.com", "newrelic.com",
    "amplitude.com", "mixpanel.com", "segment.io", "segment.com",
    "telemetry", "analytics", "tracking", "beacon",
]

_URL_RE = re.compile(r'https?://([a-zA-Z0-9._-]+)', re.IGNORECASE)


def _check_urls(line_text: str) -> list[str]:
    """Return warning messages for any non-allowlisted URLs found."""
    issues = []
    for match in _URL_RE.finditer(line_text):
        domain = match.group(1).lower()
        # Strip leading www.
        bare = domain[4:] if domain.startswith("www.") else domain
        # Check telemetry domains
        for tel in _TELEMETRY_DOMAINS:
            if tel in bare:
                issues.append(f"Possible telemetry/analytics URL: {match.group(0)}")
        # Check if domain is in allow-list
        if bare not in ALLOWED_DOMAINS and domain not in ALLOWED_DOMAINS:
            # Don't flag local addresses
            if not (bare.startswith("192.168") or bare.startswith("10.") or bare == "localhost"):
                issues.append(f"Unknown external domain: {domain}")
    return issues


# ── Scanner ───────────────────────────────────────────────────────────────────

def scan_file(file_path: str | Path) -> list[Finding]:
    path     = Path(file_path)
    findings: list[Finding] = []

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [Finding(str(path), 0, Severity.WARN, "READ_ERROR", str(e))]

    lines = source.splitlines()

    for ln, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # HIGH patterns
        for pattern, desc in _HIGH_PATTERNS:
            if re.search(pattern, line):
                findings.append(Finding(str(path), ln, Severity.HIGH, "DANGEROUS_PATTERN", desc))

        # WARN patterns
        for pattern, desc in _WARN_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(Finding(str(path), ln, Severity.WARN, "SUSPICIOUS_PATTERN", desc))

        # URL checks
        for issue in _check_urls(line):
            sev = Severity.HIGH if "telemetry" in issue.lower() or "analytics" in issue.lower() else Severity.INFO
            findings.append(Finding(str(path), ln, sev, "NETWORK_CALL", issue))

    # AST-level checks
    try:
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            # Flag dynamic attribute access on subprocess-like objects
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("loads",) and isinstance(node.func.value, ast.Name):
                        if node.func.value.id in ("pickle", "marshal"):
                            findings.append(Finding(
                                str(path), node.lineno, Severity.HIGH,
                                "UNSAFE_DESERIALIZE",
                                f"{node.func.value.id}.loads() can execute arbitrary code",
                            ))
    except SyntaxError:
        pass  # Already invalid Python — don't add noise

    return findings


def scan_files(files: list[str | Path]) -> list[Finding]:
    all_findings: list[Finding] = []
    for f in files:
        all_findings.extend(scan_file(f))
    return all_findings


def scan_directory(directory: str | Path = ".") -> list[Finding]:
    py_files = list(Path(directory).rglob("*.py"))
    # Exclude venv, __pycache__, .git
    py_files = [
        f for f in py_files
        if not any(part in f.parts for part in ("__pycache__", ".git", "venv", ".venv", "site-packages"))
    ]
    return scan_files(py_files)


def print_report(findings: list[Finding], title: str = "Security Scan Results") -> None:
    high = [f for f in findings if f.severity == Severity.HIGH]
    warn = [f for f in findings if f.severity == Severity.WARN]
    info = [f for f in findings if f.severity == Severity.INFO]

    print(f"\n── {title} {'─' * (54 - len(title))}")

    if not findings:
        print("  ✓ No issues found — all clear.")
    else:
        if high:
            print(f"\n  HIGH ({len(high)}) — requires attention:")
            for f in high:
                print(f)
        if warn:
            print(f"\n  WARN ({len(warn)}) — review recommended:")
            for f in warn:
                print(f)
        if info:
            print(f"\n  INFO ({len(info)}) — for awareness:")
            for f in info[:20]   # cap info noise
            :
                print(f)
            if len(info) > 20:
                print(f"    ... and {len(info) - 20} more INFO findings")

    print(f"\n  Summary: {len(high)} HIGH  {len(warn)} WARN  {len(info)} INFO")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    args    = sys.argv[1:]
    strict  = "--strict" in args
    targets = [a for a in args if not a.startswith("--")]

    if targets:
        findings = scan_files(targets)
    else:
        findings = scan_directory(".")

    print_report(findings)

    if strict:
        high = [f for f in findings if f.severity == Severity.HIGH]
        if high:
            sys.exit(f"[SECURITY] {len(high)} HIGH finding(s) — refusing to run.")
