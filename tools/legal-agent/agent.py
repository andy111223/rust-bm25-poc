#!/usr/bin/env python3
"""Agent analizy prawnej projektu. Python 3.11+, Git, Codex CLI; bez pip."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
from schema import SCHEMA, validate, normalize_evidence_locations
from sources import fetch, validate_registry
from view import render, report_markdown, findings_markdown, flows_markdown

VERSION = "1.0.2"
HERE = Path(__file__).resolve().parent
RUNTIME = ["agent.py", "schema.py", "sources.py", "view.py", "instructions.md", "demo.json"]
BEGIN = "<!-- LEGAL-AGENT:START -->"
END = "<!-- LEGAL-AGENT:END -->"
SEEDS = ["README.md", "APP_PROFILE.md", "SOURCES.json", "DECISIONS.md", "SCIAGA.md"]
EXTS = {".rs", ".cs", ".py", ".go", ".java", ".kt", ".kts", ".js", ".ts", ".jsx", ".tsx",
        ".sql", ".sh", ".bash", ".html", ".css", ".yaml", ".yml", ".toml", ".xml",
        ".unity", ".prefab", ".asset", ".gradle", ".cfg", ".conf"}
SPECIAL = {"Dockerfile", "requirements.txt", "package.json", "package-lock.json", "go.mod",
           "go.sum", "Cargo.lock", "Cargo.toml", "pom.xml", "AndroidManifest.xml", ".gitignore",
           "manifest.json", "packages-lock.json", "LICENSE", "LICENSE.md", "NOTICE", "NOTICE.md"}
SKIP_PARTS = {"target", ".git", ".codex", ".idea", ".vscode", "Library", "Temp", "Logs", "Build",
              "Builds", "bin", "obj", "node_modules", ".venv", "venv", "__pycache__",
              "recordings", "uploads", "datasets", "backups", "audio", "logs"}
SKIP_PREFIXES = ("tools/legal-agent/", "tools/learning-agent/", "docs/legal/", "docs/learning/")
CONTEXT_PATHS = ["AGENTS.md", "ENGINEERING_RULES.md", "LEGAL_AGENT.md", "docs/legal/APP_PROFILE.md",
                 "docs/legal/DECISIONS.md", "docs/APP_PLAN.md", "docs/PROJECT_PLAN.md",
                 "docs/PROJECT_STATUS.md", "docs/ARCHITECTURE.md", "docs/CODE_MAP.md",
                 "docs/DECISIONS.md", "docs/ROADMAP.md"]
DEFAULTS = dict(enabled=True, model="gpt-6.1-sol", reasoning="high", codex_command=["codex"],
                auto_open=True, browser_command=[], browser_desktop="",
                files_per_part=3, max_blob_bytes=180000, max_input_bytes=300000,
                context_bytes=60000, max_targets=300, max_new_commits=100,
                large_file_chunk_bytes=100000, max_split_blob_bytes=16000000,
                timeout_seconds=1200, source_refresh_hours=168, refresh_sources=True,
                max_reports_in_browser=20)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError("Odmowa zapisu przez symlink: " + str(path))
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode() if isinstance(data, str) else data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def git(root, *args, check=True):
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if check and proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    return proc.stdout


def safe_rel(path):
    p = PurePosixPath(path)
    return (bool(path) and not p.is_absolute() and ".." not in p.parts
            and not any(ord(c) < 32 for c in path) and "\\" not in path)


def secret_path(path):
    name = PurePosixPath(path).name.lower()
    return (name.startswith(".env") or name in {"auth.json", "credentials.json", "secrets.json"}
            or name.endswith((".key", ".pem", ".p12", ".pfx", ".jks", ".keystore"))
            or any(s in name for s in ("private-key", "service-account", "credential", "secret")))


def candidate(path):
    p = PurePosixPath(path)
    return (safe_rel(path) and not secret_path(path) and not path.startswith(SKIP_PREFIXES)
            and not any(x in SKIP_PARTS for x in p.parts)
            and (p.suffix.lower() in EXTS or p.name in SPECIAL or p.name.startswith("LICENSE")))


def redact(text):
    lines, count = [], 0
    sensitive = re.compile(r'''(?i)(?:api[_-]?key|password|passwd|client[_-]?secret|access[_-]?token|authorization|bearer|connectionstring)[^\n]{0,60}(?:[=:]|bearer\s)[^\n]{4,}''')
    jwt = re.compile(r"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
    for line in text.splitlines():
        if sensitive.search(line) or jwt.search(line) or "-----BEGIN " in line:
            indent = line[:len(line)-len(line.lstrip())]
            lines.append(indent + "[UKRYTO WIERSZ Z POTENCJALNYM SEKRETEM]")
            count += 1
        else:
            lines.append(line)
    return "\n".join(lines), count


class Repo:
    def __init__(self, path):
        self.root = Path(git(path, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        if any(c in str(self.root) for c in "\n\r"):
            raise RuntimeError("Ścieżka projektu zawierająca nową linię nie jest obsługiwana")
        self.gitdir = Path(git(self.root, "rev-parse", "--absolute-git-dir").decode().strip())
        self.state = self.gitdir / "legal-agent"
        if self.state.is_symlink():
            raise RuntimeError("Katalog stanu jest symlinkiem")
        self.state.mkdir(mode=0o700, exist_ok=True)
        self.config_path = self.state / "config.json"

    def cfg(self):
        cfg = dict(DEFAULTS)
        cfg.update(load(self.config_path, {}))
        for k in ("files_per_part", "max_blob_bytes", "max_input_bytes", "context_bytes",
                  "max_targets", "max_new_commits", "timeout_seconds", "source_refresh_hours",
                  "max_reports_in_browser", "large_file_chunk_bytes", "max_split_blob_bytes"):
            if type(cfg[k]) is not int or cfg[k] < 1:
                raise RuntimeError("Nieprawidłowa konfiguracja: " + k)
        for k in ("codex_command", "browser_command"):
            if not isinstance(cfg[k], list) or any(not isinstance(x, str) for x in cfg[k]):
                raise RuntimeError(k + " musi być listą argumentów, nie poleceniem Bash")
        if not cfg["codex_command"] or cfg["reasoning"] not in {"low", "medium", "high", "xhigh"}:
            raise RuntimeError("Nieprawidłowy model/poziom rozumowania")
        for k in ("enabled", "auto_open", "refresh_sources"):
            if type(cfg[k]) is not bool:
                raise RuntimeError("Nieprawidłowa opcja: " + k)
        return cfg

    def note(self, relative=""):
        base = self.root / "docs/legal"
        p = base / relative
        if relative and not safe_rel(relative):
            raise RuntimeError("Nieprawidłowa ścieżka dokumentacji")
        current = self.root
        for part in p.relative_to(self.root).parts:
            current /= part
            if current.is_symlink():
                raise RuntimeError("Symlink w ścieżce dokumentacji: " + str(current))
        return p

    @contextmanager
    def lock(self, name, blocking=True):
        p = self.state / (name + ".lock")
        if p.is_symlink():
            raise RuntimeError("Symlink blokady")
        with p.open("a+") as f:
            acquired = False
            try:
                fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
                acquired = True
            except BlockingIOError:
                pass
            try:
                yield acquired
            finally:
                if acquired:
                    fcntl.flock(f, fcntl.LOCK_UN)

    def head(self):
        return git(self.root, "rev-parse", "HEAD").decode().strip()

    def branch(self):
        return git(self.root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).decode().strip() or "DETACHED"

    def log(self, message):
        with (self.state / "agent.log").open("a") as f:
            f.write(now() + " " + message + "\n")

    def jobs(self):
        return sorted((self.state / "jobs").glob("*.json"), key=lambda p: load(p)["created_at"])


def context(repo):
    files, omitted, total = [], [], 0
    for name in CONTEXT_PATHS:
        if (not safe_rel(name) or secret_path(name)
                or any(part in SKIP_PARTS for part in PurePosixPath(name).parts)):
            continue
        p = repo.root / name
        if not p.exists():
            continue
        if any(x.is_symlink() for x in [p, *p.parents] if x != repo.root.parent):
            raise RuntimeError("Symlink w pliku kontekstu: " + name)
        raw = p.read_bytes()
        if len(raw) > 40000 or total + len(raw) > repo.cfg()["context_bytes"]:
            omitted.append(name + ": limit kontekstu")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            omitted.append(name + ": nie UTF-8")
            continue
        clean, n = redact(text)
        files.append(dict(path=name, version="context", text=clean, sha256=digest(raw),
                          provenance="working_tree_context", redacted_lines=n))
        total += len(raw)
    return files, omitted


def profile_signature(repo):
    names = ["docs/legal/APP_PROFILE.md", "docs/legal/DECISIONS.md", "docs/legal/SOURCES.json"]
    values = []
    for name in names:
        p = repo.root / name
        repo.note(name.removeprefix("docs/legal/"))
        values.append((name, digest(p.read_bytes()) if p.exists() else "missing"))
    return digest(values)


def tree(repo, commit):
    result = {}
    if not commit:
        return result
    for entry in git(repo.root, "ls-tree", "-rlz", commit).split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, typ, oid, size = meta.decode().split()
        path = raw_path.decode("utf-8", "replace")
        if typ == "blob" and mode in {"100644", "100755"} and safe_rel(path):
            result[path] = (oid, int(size))
    return result


def parent(repo, commit):
    parts = git(repo.root, "rev-list", "--parents", "-n", "1", commit).decode().split()
    return parts[1] if len(parts) > 1 else ""


def changed(repo, commit, base=None):
    base = parent(repo, commit) if base is None else base
    if base:
        raw = git(repo.root, "diff", "--name-only", "--no-renames", "-z", base, commit, "--")
    else:
        raw = git(repo.root, "diff-tree", "--root", "--no-commit-id", "-r", "--name-only", "-z", commit)
    return [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]


def enqueue(repo, kind, commit=None, files=None, base=None, manual=False, force=False):
    if not repo.cfg()["enabled"] and not manual:
        return None
    commit = commit or repo.head()
    # Resolve refs to an immutable full commit ID before freezing input.
    commit = git(repo.root, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    base = base if base is not None else parent(repo, commit)
    if base:
        base = git(repo.root, "rev-parse", "--verify", base + "^{commit}").decode().strip()
    after, before = tree(repo, commit), tree(repo, base)
    paths = files if files is not None else (list(after) if kind in {"baseline", "context", "sources"} else changed(repo, commit, base))
    if files is not None and any(not candidate(x) for x in files):
        raise RuntimeError("Wybrany plik jest wykluczony, sekretny albo ma nieobsługiwany format")
    targets = []
    for path in sorted(set(paths)):
        if not candidate(path):
            continue
        side = "after" if path in after else "before"
        if path not in (after if side == "after" else before):
            raise RuntimeError("Brak pliku w wybranym commicie: " + path)
        targets.append(dict(path=path, version=side))
    if not targets:
        return None
    if len(targets) > repo.cfg()["max_targets"]:
        raise RuntimeError("Przekroczono max_targets. Wybierz zakres przez --file lub zwiększ limit w konfiguracji.")
    inputs, omitted = context(repo)
    registry = validate_registry(load(repo.note("SOURCES.json")))
    signature = profile_signature(repo)
    source_cache = load(repo.state / "source-cache.json", {})
    identity = commit[:12] + "-" + digest([kind, base, targets, signature,
                                          [(x["path"], x["sha256"]) for x in inputs],
                                          source_cache, uuid.uuid4().hex if force else ""])[:12]
    with repo.lock("queue"):
        p = repo.state / "jobs" / (identity + ".json")
        if not p.exists():
            job = dict(id=identity, kind=kind, commit=commit, base=base, branch=repo.branch(),
                       created_at=now(), status="pending", error="", manual=manual,
                       profile_signature=signature, targets=targets, context=inputs,
                       omissions=omitted, registry=registry, source_cache=source_cache, parts_done=[],
                       published=False, finished_at="")
            save(p, job)
    return identity


def scan(repo):
    if not repo.cfg()["enabled"] or not (repo.root / "LEGAL_AGENT.md").is_file():
        return []
    with repo.lock("scan"):
        cursor = load(repo.state / "cursor.json", {"branches": {}})
        branch, head = repo.branch(), repo.head()
        previous = cursor["branches"].get(branch)
        queued = []
        if previous is None:
            commits = [head]  # New branch: current change, never an unbounded history replay.
            repo.log("Nowa gałąź: analiza HEAD; pełny stan wymaga baseline: " + branch)
        elif previous["head"] == head:
            commits = []
        elif subprocess.run(["git", "-C", str(repo.root), "merge-base", "--is-ancestor",
                             previous["head"], head], capture_output=True).returncode == 0:
            commits = git(repo.root, "rev-list", "--reverse", "--first-parent", head,
                          "^" + previous["head"]).decode().splitlines()
        else:
            commits = [head]
            repo.log("Zmieniona historia Git; sprawdzam HEAD. Pełny przegląd: baseline.")
        if len(commits) > repo.cfg()["max_new_commits"]:
            raise RuntimeError("Za dużo nowych commitów. Użyj baseline, aby przejrzeć obecny stan i ustawić punkt kontynuacji.")
        for commit in commits:
            ident = enqueue(repo, "commit", commit=commit)
            if ident:
                queued.append(ident)
        signature = profile_signature(repo)
        if previous and previous.get("profile_signature") != signature:
            ident = enqueue(repo, "context", commit=head)
            if ident:
                queued.append(ident)
        cursor["branches"][branch] = dict(head=head, profile_signature=signature)
        save(repo.state / "cursor.json", cursor)
        return queued


def refresh_sources(repo, force=False):
    registry = validate_registry(load(repo.note("SOURCES.json")))
    old = load(repo.state / "source-cache.json", {})
    if not force and old.get("checked_at"):
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(old["checked_at"])).total_seconds()
        if age < repo.cfg()["source_refresh_hours"] * 3600 and old.get("registry_hash") == digest(registry):
            return False
    with repo.lock("sources"):
        values = [fetch(source) for source in registry["sources"]]
        previous = {x["id"]: x for x in old.get("records", [])}
        changed_ids = [v["id"] for v in values if v["status"] == "retrieved"
                       and previous.get(v["id"], {}).get("content_sha256")
                       and previous[v["id"]]["content_sha256"] != v["content_sha256"]]
        save(repo.state / "source-cache.json", dict(checked_at=now(), registry_hash=digest(registry),
                                                    records=values, changed_ids=changed_ids))
        repo.log("Sprawdzenie dostępności źródeł: " + ", ".join(v["id"] + "=" + v["status"] for v in values))
        return bool(changed_ids)


def all_reports(repo):
    folder = repo.note("reviews")
    result = []
    for p in sorted(folder.glob("*/report.json")):
        repo.note(p.relative_to(repo.note()).as_posix())
        item = load(p)
        if not isinstance(item, dict) or item.get("format") != 1:
            raise RuntimeError("Nieprawidłowy zapis raportu: " + str(p))
        result.append(item)
    return result


def current_reports(repo):
    commits = git(repo.root, "rev-list", "--topo-order", "--reverse", "HEAD").decode().splitlines()
    order = {commit: i for i, commit in enumerate(commits)}
    return sorted((r for r in all_reports(repo) if r["commit"] in order),
                  key=lambda r: (order[r["commit"]], r["created_at"], r["id"]))


def finding_id(key):
    return "LEGAL-" + digest(key.encode())[:10].upper()


def registry_state(repo):
    findings, flows = {}, {}
    for report in current_reports(repo):
        observed_in_report = {}
        for part in report["parts"]:
            for finding in part["findings"]:
                key = finding["key"]
                # Several chunks can describe one concern. Keep all their evidence/actions.
                if key in observed_in_report:
                    combined = dict(observed_in_report[key])
                    for field in ("evidence", "references", "code_actions", "author_actions", "questions", "closure_evidence"):
                        merged = combined[field] + finding[field]
                        combined[field] = list({digest(value): value for value in merged}.values())
                    rank = {"low": 0, "medium": 1, "high": 2}
                    combined["priority"] = max((combined["priority"], finding["priority"]), key=rank.get)
                    finding = combined
                observed_in_report[key] = finding
                old = findings.get(key, {})
                findings[key] = dict(finding, id=finding_id(key),
                                     first_commit=old.get("first_commit", report["commit"]),
                                     last_commit=report["commit"], report_id=report["id"],
                                     observation_date=report["created_at"], status="open",
                                     profile_signature=report["profile_signature"],
                                     history=list(dict.fromkeys(old.get("history", []) + [report["id"]])),
                                     references_resolved=resolve_refs(finding, report["legal_sources"]))
            for flow in part["flows"]:
                flows[flow["key"]] = dict(flow, commit=report["commit"], report_id=report["id"])
            for assessed in part["previous_findings"]:
                if assessed["key"] in findings and assessed["assessment"] == "change_observed":
                    findings[assessed["key"]].update(assessment_report_id=report["id"],
                                                     later_assessment=assessed,
                                                     assessment_commit=report["commit"])
    decisions = []
    for p in repo.note("decisions").glob("*.json"):
        repo.note(p.relative_to(repo.note()).as_posix())
        decisions.append(load(p))
    for decision in sorted(decisions, key=lambda x: (x["at"], x["id"])):
        key = decision["key"]
        if key in findings:
            findings[key]["decision"] = decision
            # A decision covers a specific observation, never future changes automatically.
            relevant_report = findings[key].get("assessment_report_id", findings[key]["report_id"])
            findings[key]["status"] = (decision["status"] if decision["report_id"] == relevant_report
                                       else "review_again")
    return list(findings.values()), list(flows.values())


def resolve_refs(finding, sources):
    indexed = {s["id"]: s for s in sources}
    return [dict(ref, source=indexed[ref["source_id"]]) for ref in finding["references"]]


def source_cards(job):
    cached = {x["id"]: x for x in job["source_cache"].get("records", [])}
    result = []
    for source in job["registry"]["sources"]:
        record = cached.get(source["id"], {})
        result.append(dict(source, retrieval_status=record.get("status", "not_checked_locally"),
                           retrieved_at=record.get("retrieved_at", ""),
                           content_sha256=record.get("content_sha256", ""),
                           retrieved_excerpt=record.get("excerpt", "")[:7000],
                           currency="Nie potwierdza aktualności stanu prawnego; sprawdź datę karty i zakres źródła."))
    return result


def expand_large_targets(repo, job):
    """Lossless line windows for large text targets; keep normal targets unchanged."""
    cfg = repo.cfg()
    trees = {"before": tree(repo, job["base"]), "after": tree(repo, job["commit"])}
    result = []
    for target in job["targets"]:
        oid, size = trees[target["version"]][target["path"]]
        if size <= cfg["max_blob_bytes"] or "first_line" in target:
            result.append(target)
            continue
        if size > cfg["max_split_blob_bytes"]:
            raise RuntimeError("Plik przekracza limit bezpiecznego podziału max_split_blob_bytes: " + target["path"])
        raw = git(repo.root, "cat-file", "blob", oid)
        try:
            text = raw.decode("utf-8")
            if "\0" in text:
                raise UnicodeError()
        except UnicodeError:
            raise RuntimeError("Wybrany duży plik nie jest tekstem UTF-8: " + target["path"])
        clean, _ = redact(text)
        lines = clean.splitlines()
        # Budget the JSON-encoded text, including escaped quotes/newlines.
        limit = min(cfg["large_file_chunk_bytes"], cfg["max_blob_bytes"],
                    max(1000, cfg["max_input_bytes"] // 3))
        start, used = 1, 0
        for number, line in enumerate(lines, 1):
            length = len(json.dumps(line, ensure_ascii=False).encode()) + 2
            if length > limit:
                raise RuntimeError("Jedna linia dużego pliku przekracza limit fragmentu; potrzebny osobny zakres: " + target["path"])
            if used and used + length > limit:
                result.append(dict(target, first_line=start, last_line=number-1, total_lines=len(lines)))
                start, used = number, 0
            used += length
        if lines:
            result.append(dict(target, first_line=start, last_line=len(lines), total_lines=len(lines)))
        else:
            result.append(target)
    return result


def plan_parts(repo, job, path):
    if "part_targets" in job:
        return
    targets = expand_large_targets(repo, job)
    groups, start = [], 0
    while start < len(targets):
        # One window per part: evidence keys remain (version, path), never ambiguous.
        count = 1 if "first_line" in targets[start] else min(repo.cfg()["files_per_part"], len(targets)-start)
        for i in range(1, count):
            if "first_line" in targets[start+i]:
                count = i
                break
        while True:
            selected = targets[start:start+count]
            try:
                build_bundle(repo, job, selected)
                break
            except RuntimeError as ex:
                if count > 1 and "max_input_bytes" in str(ex):
                    count -= 1
                    continue
                raise
        groups.append(selected)
        start += count
    job["part_targets"] = groups
    job["chunk_plan_version"] = 2
    save(path, job)
    windows = sum("first_line" in target for group in groups for target in group)
    repo.log(f'Plan {job["id"]}: {len(groups)} części, w tym {windows} fragmentów dużych plików.')


def build_bundle(repo, job, targets):
    cfg = repo.cfg()
    before, after = tree(repo, job["base"]), tree(repo, job["commit"])
    all_targets = {(t["version"], t["path"]) for t in targets}
    target_info = {(t["version"], t["path"]): t for t in targets}
    files, omissions, used = list(job["context"]), list(job["omissions"]), 0
    # Source cards and history count toward the same bounded input budget.
    cards = source_cards(job)
    previous, _ = registry_state(repo)
    prior = [{k: f[k] for k in ("key", "title", "status", "observed", "applicability", "last_commit")}
             for f in previous][-80:]
    base_bundle = dict(format=1, job_id=job["id"], commit=job["commit"], base=job["base"],
                       branch=job["branch"], kind=job["kind"], captured_at=now(),
                       profile_signature=job["profile_signature"], targets=targets,
                       files=files, legal_sources=cards, previous_findings=prior,
                       omissions=omissions, analysis="static_only_no_execution")
    used = len(json.dumps(base_bundle, ensure_ascii=False).encode())
    ordered = [(t["version"], t["path"]) for t in targets]
    ordered += [("before", t["path"]) for t in targets
                if t["version"] == "after" and t["path"] in before]
    # Give related folders and likely data-flow code priority, then other supported code.
    folders = {str(PurePosixPath(t["path"]).parent) for t in targets}
    names = sorted((p for p in after if candidate(p)),
                   key=lambda p: (str(PurePosixPath(p).parent) not in folders,
                                  not bool(re.search(r"(?i)(speech|stt|rag|config|model|api|main|controller|auth)", p)), p))
    ordered += [("after", p) for p in names]
    seen = set()
    for side, path in ordered:
        if (side, path) in seen:
            continue
        seen.add((side, path))
        entry = (after if side == "after" else before).get(path)
        if entry is None:
            continue
        oid, size = entry
        required = (side, path) in all_targets
        selection = target_info.get((side, path), {})
        window = "first_line" in selection
        if size > cfg["max_blob_bytes"] and not window:
            if required:
                raise RuntimeError("Wybrany plik przekracza max_blob_bytes: " + path)
            omissions.append(side + ":" + path + ": limit pliku")
            continue
        if window and size > cfg["max_split_blob_bytes"]:
            raise RuntimeError("Plik przekracza max_split_blob_bytes: " + path)
        raw = git(repo.root, "cat-file", "blob", oid)
        try:
            text = raw.decode("utf-8")
            if "\0" in text:
                raise UnicodeError()
        except UnicodeError:
            if required:
                raise RuntimeError("Wybrany plik nie jest tekstem UTF-8: " + path)
            omissions.append(side + ":" + path + ": format binarny")
            continue
        clean, n = redact(text)
        range_meta = {}
        if window:
            lines = clean.splitlines()
            first, last = selection["first_line"], selection["last_line"]
            if not 1 <= first <= last <= len(lines):
                raise RuntimeError("Nieprawidłowy zakres fragmentu pliku: " + path)
            clean = "\n".join(lines[first-1:last])
            n = sum("[UKRYTO WIERSZ Z POTENCJALNYM SEKRETEM]" in line for line in lines[first-1:last])
            range_meta = dict(first_line=first, last_line=last, total_lines=len(lines),
                              range_sha256=digest(clean.encode()))
        item = dict(path=path, version=side, text=clean, sha256=digest(raw),
                    git_blob=oid, provenance=job["commit"] if side == "after" else job["base"], redacted_lines=n,
                    **range_meta)
        length = len(json.dumps(item, ensure_ascii=False).encode())
        if used + length > cfg["max_input_bytes"]:
            if required:
                raise RuntimeError("Część przekracza max_input_bytes. Zmniejsz files_per_part lub zwiększ limit.")
            omissions.append(side + ":" + path + ": limit całej migawki")
            continue
        files.append(item)
        used += length
    if not all_targets.issubset({(f["version"], f["path"]) for f in files}):
        raise RuntimeError("Brakuje wybranego pliku w migawce")
    # No raw diff: it could reintroduce secrets removed by the redaction pass.
    return base_bundle


def codex_options(repo, cfg):
    # Listing declarations does not connect to the servers. Never log the returned configuration.
    proc = subprocess.run([*cfg["codex_command"], "mcp", "list", "--json"],
                          capture_output=True, timeout=30)
    if proc.returncode:
        raise RuntimeError("Nie udało się ustalić listy MCP; analiza nie wystartowała. Sprawdź codex mcp list --json.")
    servers = json.loads(proc.stdout)
    if not isinstance(servers, list) or any(not isinstance(x, dict) or "name" not in x for x in servers):
        raise RuntimeError("Nieobsługiwany format codex mcp list --json")
    options = []
    settings = ['approval_policy="never"', 'web_search="disabled"', 'features.shell_tool=false',
                'features.apps=false', 'features.plugins=false', 'features.multi_agent=false',
                'features.hooks=false', 'features.memories=false', 'features.shell_snapshot=false',
                'features.skill_mcp_dependency_install=false', 'project_doc_max_bytes=0',
                'history.persistence="none"', 'notify=[]',
                'model_reasoning_effort=' + json.dumps(cfg["reasoning"])]
    settings += ['mcp_servers.' + json.dumps(x["name"]) + '.enabled=false' for x in servers]
    for value in settings:
        options += ["--config", value]
    return options


def run_codex(repo, bundle, result_path):
    cfg = repo.cfg()
    schema_path = repo.state / "output-schema.json"
    save(schema_path, SCHEMA)
    prompt = (HERE / "instructions.md").read_text() + "\n\nDANE_WEJSCIOWE_JSON:\n" + json.dumps(bundle, ensure_ascii=False)
    options = codex_options(repo, cfg)
    # An empty directory outside the repository avoids project-local Codex configuration.
    with tempfile.TemporaryDirectory(prefix="legal-model-") as empty:
        command = [*cfg["codex_command"], "exec", "--sandbox", "read-only", "--skip-git-repo-check",
                   "--model", cfg["model"], *options, "--output-schema", str(schema_path),
                   "--output-last-message", str(result_path), "-"]
        with (repo.state / "codex.log").open("ab") as log:
            process = subprocess.Popen(command, cwd=empty, stdin=subprocess.PIPE,
                                       stdout=log, stderr=log, start_new_session=True)
            try:
                process.communicate(prompt.encode(), timeout=cfg["timeout_seconds"])
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise RuntimeError("Analiza przerwana lub przekroczony limit czasu; zachowano kolejkę.")
            if process.returncode:
                raise RuntimeError(f"Codex zakończył się kodem {process.returncode}; zobacz lokalny codex.log")
    if not result_path.is_file() or result_path.stat().st_size > 2_000_000:
        raise RuntimeError("Brak odpowiedzi JSON albo odpowiedź jest za duża")
    return load(result_path)


def compatible(repo, job):
    return repo.branch() == job["branch"] and (repo.root / "LEGAL_AGENT.md").is_file()


def regenerate(repo):
    findings, flows = registry_state(repo)
    reports = current_reports(repo)
    signature = profile_signature(repo)
    atomic(repo.note("FINDINGS.md"), findings_markdown(findings, signature))
    atomic(repo.note("DATA_MAP.md"), flows_markdown(flows))
    index = "# Przeglądy\n\nRaporty są oceną statyczną wskazanych migawek, nie potwierdzeniem zgodności.\n\n"
    for report in reversed(reports):
        index += f'- [{report["title"]}](reviews/{report["id"]}/report.md) · `{report["commit"][:12]}` · {report["created_at"]}\n'
    atomic(repo.note("REVIEWS.md"), index)
    suggestions = [s for r in reports[-5:] for p in r["parts"] for s in p["profile_suggestions"]]
    atomic(repo.note("PROFILE_SUGGESTIONS.md"), "# Propozycje uzupełnienia profilu\n\nAgent nie zmienia samodzielnie deklaracji autora w APP_PROFILE.md.\n\n" +
           "\n".join("- " + s.replace("\n", " ") for s in dict.fromkeys(suggestions)) + "\n")
    atomic(repo.state / "site/index.html", render(findings, flows, reports[-repo.cfg()["max_reports_in_browser"]:], signature))
    return findings


def publish(repo, job, parts):
    target = repo.note("reviews/" + job["id"])
    if (target / "report.json").is_file():
        return False
    old, _ = registry_state(repo)
    old_values = {f["key"]: digest([f["observed"], f["priority"], f["applicability"]]) for f in old}
    manifests = []
    for i in range(1, len(parts)+1):
        bundle = load(repo.state / "inputs" / f'{job["id"]}-p{i:03}.json')
        manifests.append(dict(part=i, files=[{k: v for k, v in f.items() if k != "text"} for f in bundle["files"]],
                              omissions=bundle["omissions"],
                              line_repairs=load(repo.state / "repairs" / f'{job["id"]}-p{i:03}.json', {})))
    record = dict(format=1, agent_version=VERSION, id=job["id"], title=parts[0]["title"],
                  commit=job["commit"], base=job["base"], branch=job["branch"],
                  commit_time=int(git(repo.root, "show", "-s", "--format=%ct", job["commit"]).decode()),
                  created_at=now(), kind=job["kind"], profile_signature=job["profile_signature"],
                  context_hashes=[dict(path=x["path"], sha256=x["sha256"]) for x in job["context"]],
                  legal_sources=source_cards(job), targets=job["targets"], parts=parts, manifests=manifests,
                  excluded_categories="Sekrety, produkcyjne dane, binaria, pliki niewersjonowane, vendor/SDK i kod samych agentów; szczegóły filtrów w agent.py.",
                  verification="not_run", currency="Nie wydano potwierdzenia zgodności prawnej.")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".review-", dir=target.parent))
    try:
        save(staging / "report.json", record)
        atomic(staging / "report.md", report_markdown(record))
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    changed_findings = any(old_values.get(f["key"]) != digest([f["observed"], f["priority"], f["applicability"]])
                           for p in parts for f in p["findings"])
    changed_prior = any(x["assessment"] == "change_observed" for p in parts for x in p["previous_findings"])
    return bool(changed_findings or changed_prior or job["manual"])


def process(repo, path, saved_only=False):
    job = load(path)
    if not compatible(repo, job):
        return False
    job.update(status="running", error="")
    save(path, job)
    # Plan small chunks dynamically; shrink a chunk instead of failing on three large files.
    # Once persisted, boundaries remain fixed across retries and configuration changes.
    if "part_targets" not in job:
        if saved_only:
            raise RuntimeError("Brak planu zapisanych części; recheck nie tworzy nowej analizy")
        plan_parts(repo, job, path)
    parts = []
    for index, selected in enumerate(job["part_targets"], 1):
        if not compatible(repo, job) or not repo.cfg()["enabled"]:
            job["status"] = "pending"
            save(path, job)
            return False
        bundle_path = repo.state / "inputs" / f'{job["id"]}-p{index:03}.json'
        output = repo.state / "results" / f'{job["id"]}-p{index:03}.json'
        if bundle_path.exists():
            bundle = load(bundle_path)
        else:
            if saved_only:
                raise RuntimeError("Brak zapisanej migawki części; recheck nie wywołuje modelu")
            bundle = build_bundle(repo, job, selected)
            save(bundle_path, bundle)
        if output.exists():
            response = load(output)
        elif saved_only:
            raise RuntimeError("Brak zapisanej odpowiedzi; użyj retry")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            response = run_codex(repo, bundle, output)
        response, repairs = normalize_evidence_locations(response, bundle)
        validate(response, bundle)
        if repairs:
            save(repo.state / "repairs" / output.name,
                 dict(method="unique_literal_quote_in_frozen_source", at=now(),
                      input_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                      raw_response_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                      changes=repairs))
            repo.log(f'Korekta numerów linii {output.stem}: {len(repairs)}; oryginalna odpowiedź zachowana.')
        else:
            (repo.state / "repairs" / output.name).unlink(missing_ok=True)
        # Add deterministic scope information to the published copy, preserving raw output.
        published_response = json.loads(json.dumps(response))
        for target in selected:
            if "first_line" in target:
                description = (f'Fragment {target["path"]}: oryginalne linie '
                               f'{target["first_line"]}–{target["last_line"]} z {target["total_lines"]}.')
                published_response["scope_note"] += " " + description
                published_response["limitations"].append(description + " Ta część nie obejmuje całego pliku; pozostałe fragmenty są w innych częściach raportu.")
        parts.append(published_response)
        if index not in job["parts_done"]:
            job["parts_done"].append(index)
        save(path, job)
    if not compatible(repo, job):
        job["status"] = "pending"
        save(path, job)
        return False
    changed_page = publish(repo, job, parts)
    job.update(status="done", error="", finished_at=now(), published=True)
    save(path, job)
    regenerate(repo)
    return changed_page


def work(repo):
    with repo.lock("worker", blocking=False) as acquired:
        if not acquired:
            return
        with repo.lock("queue"):
            for p in repo.jobs():
                j = load(p)
                if j["status"] == "running":
                    j.update(status="pending", error="Wznowiono po przerwaniu procesu")
                    save(p, j)
        should_open = False
        while repo.cfg()["enabled"] and (repo.root / "LEGAL_AGENT.md").is_file():
            with repo.lock("queue"):
                pending = [p for p in repo.jobs() if load(p)["status"] == "pending" and compatible(repo, load(p))]
            if not pending:
                break
            for p in pending:
                if not repo.cfg()["enabled"]:
                    break
                try:
                    should_open |= process(repo, p)
                except Exception as ex:
                    j = load(p)
                    j.update(status="failed", error=str(ex), finished_at=now())
                    save(p, j)
                    repo.log("Błąd " + j["id"] + ": " + str(ex))
        if should_open and repo.cfg()["auto_open"]:
            try:
                open_browser(repo)
            except Exception as ex:
                repo.log("Raport zapisany; nie otwarto BrowserOS: " + str(ex))


def spawn(repo, command="work"):
    runner = repo.state / "runtime/agent.py"
    if not runner.is_file():
        runner = HERE / "agent.py"
    with (repo.state / "worker.log").open("ab") as log:
        subprocess.Popen([sys.executable, str(runner), "--repo", str(repo.root), command],
                         cwd=repo.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


def tick(repo):
    if not repo.cfg()["enabled"] or not (repo.root / "LEGAL_AGENT.md").is_file():
        return
    with repo.lock("tick", blocking=False) as acquired:
        if not acquired:
            return
        scan(repo)
        if repo.cfg()["refresh_sources"] and refresh_sources(repo):
            enqueue(repo, "sources")
        work(repo)


def browser(cfg):
    if cfg["browser_command"]:
        return cfg["browser_command"]
    if cfg["browser_desktop"]:
        p = Path(cfg["browser_desktop"]).expanduser()
        if p.is_file() and shutil.which("gio"):
            return ["gio", "launch", str(p)]
        raise RuntimeError("Nie znaleziono pliku .desktop lub gio")
    dirs = [Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local/share"))) / "applications"]
    dirs += [Path(x)/"applications" for x in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")]
    for folder in dirs:
        for p in sorted(folder.glob("*.desktop")):
            if "browseros" in p.name.lower() and shutil.which("gio"):
                return ["gio", "launch", str(p)]
    for command in ("browseros", "BrowserOS", "browseros-browser"):
        if shutil.which(command):
            return [shutil.which(command)]
    raise RuntimeError("Nie znaleziono BrowserOS; użyj configure --browser-desktop /ścieżka/browseros.desktop")


def open_browser(repo, page=None):
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("Brak sesji graficznej. Raport pozostaje zapisany; później użyj open.")
    page = page or repo.state / "site/index.html"
    with (repo.state / "browser.log").open("ab") as log:
        p = subprocess.Popen([*browser(repo.cfg()), Path(page).as_uri()], stdout=log, stderr=log,
                             start_new_session=True)
        try:
            if p.wait(timeout=1):
                raise RuntimeError("BrowserOS zakończył uruchamianie błędem; zobacz browser.log")
        except subprocess.TimeoutExpired:
            pass


def unit_name(repo):
    return "legal-agent-" + digest(str(repo.root).encode())[:12]


def unit_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


def package_root():
    path = HERE.parent.parent
    if not (path / "LEGAL_AGENT.md").is_file():
        raise RuntimeError("Install/update uruchom z tools/legal-agent projektu, nie lokalnej kopii runtime")
    return path


def update(repo):
    package_root()
    with repo.lock("worker", blocking=False) as acquired:
        if not acquired:
            raise RuntimeError("Trwa analiza; wykonaj update po jej zakończeniu")
        for name in RUNTIME:
            atomic(repo.state / "runtime" / name, (HERE / name).read_bytes())
    print("Zaktualizowano runtime. Zachowano reguły, profil, źródła, raporty i ustawienia.")


def install(repo, timer=False):
    package = package_root()
    for name in SEEDS:
        target = repo.note(name)
        if not target.exists():
            atomic(target, (package / "docs/legal" / name).read_bytes())
    role = repo.root / "LEGAL_AGENT.md"
    if role.is_symlink():
        raise RuntimeError("LEGAL_AGENT.md jest symlinkiem")
    if not role.exists():
        atomic(role, (package / "LEGAL_AGENT.md").read_bytes())
    agents = repo.root / "AGENTS.md"
    if agents.is_symlink():
        raise RuntimeError("AGENTS.md jest symlinkiem")
    text = agents.read_text() if agents.exists() else "# Instrukcje projektu\n"
    if (BEGIN in text) != (END in text):
        raise RuntimeError("Niekompletna sekcja agenta prawnego w AGENTS.md")
    if BEGIN not in text:
        if not (repo.state / "AGENTS.before-install.md").exists():
            atomic(repo.state / "AGENTS.before-install.md", text)
        block = (package / "DODAJ_AGENTA_PRAWNEGO_DO_AGENTS.md").read_text()
        atomic(agents, text.rstrip() + "\n\n" + BEGIN + "\n" + block.rstrip() + "\n" + END + "\n")
    if not repo.config_path.exists():
        cfg = dict(DEFAULTS)
        if shutil.which("codex"):
            cfg["codex_command"] = [shutil.which("codex")]
        save(repo.config_path, cfg)
    update(repo)
    if not (repo.state / "cursor.json").exists():
        previous_reports = current_reports(repo)
        start_commit = previous_reports[-1]["commit"] if previous_reports else repo.head()
        save(repo.state / "cursor.json", {"branches": {repo.branch(): dict(head=start_commit,
                                                                         profile_signature=profile_signature(repo))}})
    regenerate(repo)
    if timer:
        if not shutil.which("systemctl"):
            raise RuntimeError("Brak systemd. Instalacja plików gotowa; używaj tick ręcznie.")
        directory = Path.home() / ".config/systemd/user"
        name = unit_name(repo)
        runner = repo.state / "runtime/agent.py"
        service = ("[Unit]\nDescription=Agent analizy prawnej projektu\n[Service]\nType=oneshot\n"
                   f"ExecStart={unit_quote(sys.executable)} {unit_quote(runner)} --repo {unit_quote(repo.root)} tick\n"
                   "TimeoutStartSec=infinity\nKillMode=control-group\n")
        timer_text = ("[Unit]\nDescription=Sprawdzanie nowych commitów i kolejki agenta prawnego\n"
                      f"[Timer]\nOnStartupSec=45s\nOnUnitInactiveSec=60s\nUnit={name}.service\n"
                      "[Install]\nWantedBy=timers.target\n")
        atomic(directory / (name + ".service"), service)
        atomic(directory / (name + ".timer"), timer_text)
        env_names = [x for x in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR") if x in os.environ]
        if env_names:
            subprocess.run(["systemctl", "--user", "import-environment", *env_names], check=False)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", name + ".timer"], check=True)
    print("Zainstalowano agenta prawnego. Hooki Git i pliki agenta nauki pozostały bez zmian.")
    print("Konfiguracja lokalna:", repo.config_path)
    print("Następnie: doctor, demo, profil aplikacji, sources refresh i baseline --background.")


def doctor(repo):
    cfg = repo.cfg()
    print("Wersja agenta:", VERSION, "Python:", sys.version.split()[0])
    print("Repozytorium:", repo.root, "Gałąź:", repo.branch())
    print("Model:", cfg["model"], "Rozumowanie:", cfg["reasoning"])
    try:
        p = subprocess.run([*cfg["codex_command"], "--version"], capture_output=True, text=True, timeout=15)
        print("Codex:", p.stdout.strip() or "niedostępny")
        codex_options(repo, cfg)
        print("Lista MCP: odczytana; serwery będą wyłączone na czas analizy.")
    except Exception as ex:
        print("Codex/MCP:", ex)
    try:
        print("BrowserOS:", browser(cfg))
    except Exception as ex:
        print("BrowserOS:", ex)
    print("Sesja graficzna:", bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")))
    print("Timer:", unit_name(repo) + ".timer")
    if shutil.which("systemctl"):
        p = subprocess.run(["systemctl", "--user", "is-active", unit_name(repo)+".timer"], capture_output=True, text=True)
        print("Stan timera:", p.stdout.strip() or "nieustalony")
    print("Rejestr źródeł:", len(validate_registry(load(repo.note("SOURCES.json")))["sources"]))
    print("Konfiguracja:", repo.config_path)
    print("Logowanie sprawdź poleceniem codex login status; agent nie odczytuje plików poświadczeń.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=".")
    subs = p.add_subparsers(dest="cmd", required=True)
    install_p = subs.add_parser("install")
    install_p.add_argument("--timer", action="store_true")
    for name in ("doctor", "status", "tick", "scan", "work", "open", "demo", "pause", "resume", "update", "uninstall"):
        subs.add_parser(name)
    for name in ("baseline", "review"):
        cmd = subs.add_parser(name)
        cmd.add_argument("--file", action="append", dest="files")
        cmd.add_argument("--since")
        cmd.add_argument("--background", action="store_true")
        cmd.add_argument("--force", action="store_true", help="Nowe zadanie także przy niezmienionym wejściu")
    recheck = subs.add_parser("recheck")
    recheck.add_argument("job_id")
    retry = subs.add_parser("retry")
    retry.add_argument("job_id")
    retry.add_argument("--new-response", action="store_true")
    source_p = subs.add_parser("sources")
    source_p.add_argument("action", choices=["status", "refresh"])
    decide = subs.add_parser("decide")
    decide.add_argument("finding_id")
    decide.add_argument("--status", required=True, choices=["open", "planned", "implemented", "verified", "not_applicable"])
    decide.add_argument("--note", required=True)
    configure = subs.add_parser("configure")
    configure.add_argument("--model")
    configure.add_argument("--reasoning", choices=["low", "medium", "high", "xhigh"])
    configure.add_argument("--auto-open", choices=["on", "off"])
    configure.add_argument("--refresh-sources", choices=["on", "off"])
    configure.add_argument("--browser-desktop")
    configure.add_argument("--browser-executable")
    configure.add_argument("--files-per-part", type=int)
    configure.add_argument("--max-blob-bytes", type=int)
    configure.add_argument("--max-input-bytes", type=int)
    configure.add_argument("--large-file-chunk-bytes", type=int)
    configure.add_argument("--max-split-blob-bytes", type=int)
    args = p.parse_args(argv)
    repo = Repo(args.repo)
    if args.cmd == "install":
        install(repo, args.timer)
    elif args.cmd == "update":
        update(repo)
    elif args.cmd == "doctor":
        doctor(repo)
    elif args.cmd == "tick":
        tick(repo)
    elif args.cmd == "scan":
        print("Dodano do kolejki:", ", ".join(scan(repo)) or "brak nowych zmian")
    elif args.cmd == "work":
        work(repo)
    elif args.cmd in {"baseline", "review"}:
        if not repo.cfg()["enabled"]:
            raise RuntimeError("Agent wstrzymany; użyj resume")
        kind = "baseline" if args.cmd == "baseline" else "review"
        if args.cmd == "baseline" and args.since:
            raise RuntimeError("--since służy do review; baseline opisuje bieżący stan")
        ident = enqueue(repo, kind, files=args.files, base=args.since, manual=True, force=args.force)
        print("W kolejce:", ident or "brak obsługiwanych plików")
        if ident and args.cmd == "baseline" and not args.files:
            with repo.lock("scan"):
                cursor = load(repo.state / "cursor.json", {"branches": {}})
                cursor["branches"][repo.branch()] = dict(head=repo.head(), profile_signature=profile_signature(repo))
                save(repo.state / "cursor.json", cursor)
        if ident and args.background:
            spawn(repo)
        elif ident:
            work(repo)
            job = load(repo.state / "jobs" / (ident + ".json"))
            print("Stan:", job["status"])
            if job["status"] == "failed":
                raise RuntimeError(job["error"])
            if job["status"] == "pending":
                print("Kolejka oczekuje na wolny proces lub powrót na właściwą gałąź.")
    elif args.cmd in {"recheck", "retry"}:
        if not re.fullmatch(r"[a-f0-9]{12}-[a-f0-9]{12}", args.job_id):
            raise RuntimeError("Nieprawidłowy identyfikator zadania")
        path = repo.state / "jobs" / (args.job_id + ".json")
        if not path.exists():
            raise RuntimeError("Nie znaleziono zadania")
        with repo.lock("worker", blocking=False) as acquired:
            if not acquired:
                raise RuntimeError("Trwa analiza; spróbuj po jej zakończeniu")
            job = load(path)
            if not compatible(repo, job):
                raise RuntimeError("Zadanie pochodzi z innej gałęzi; wróć na " + job["branch"])
            if args.cmd == "recheck":
                changed_page = process(repo, path, saved_only=True)
                print("Sprawdzono zapisane odpowiedzi; model nie był wywoływany.")
                if changed_page and repo.cfg()["auto_open"]:
                    try:
                        open_browser(repo)
                    except Exception as ex:
                        repo.log(str(ex))
            else:
                if job["status"] == "done":
                    raise RuntimeError("Zadanie zakończone. Nowy zakres zleć przez review lub baseline.")
                if args.new_response:
                    for response in (repo.state / "results").glob(args.job_id + "-p*.json"):
                        match = re.fullmatch(re.escape(args.job_id) + r"-p(\d{3,})", response.stem)
                        if match and int(match.group(1)) not in job["parts_done"]:
                            response.rename(response.with_suffix(".rejected-" + uuid.uuid4().hex[:8] + ".json"))
                job.update(status="pending", error="")
                save(path, job)
        if args.cmd == "retry":
            spawn(repo)
            print("Wznowiono zadanie. --new-response zamawia nową odpowiedź tylko dla niezaakceptowanych części.")
    elif args.cmd in {"pause", "resume", "uninstall"}:
        cfg = repo.cfg()
        cfg["enabled"] = args.cmd == "resume"
        save(repo.config_path, cfg)
        if args.cmd == "resume":
            spawn(repo, "tick")
        if args.cmd == "uninstall" and shutil.which("systemctl"):
            subprocess.run(["systemctl", "--user", "disable", "--now", unit_name(repo)+".timer"], capture_output=True)
            subprocess.run(["systemctl", "--user", "stop", unit_name(repo)+".service"], capture_output=True)
        print("Wznowiono." if args.cmd == "resume" else "Wstrzymano; trwająca część może się zakończyć. Dokumentacja i kolejka pozostają zapisane.")
    elif args.cmd == "configure":
        cfg = repo.cfg()
        for key in ("model", "reasoning", "files_per_part", "max_blob_bytes", "max_input_bytes", "large_file_chunk_bytes", "max_split_blob_bytes"):
            if getattr(args, key) is not None:
                cfg[key] = getattr(args, key)
        for key in ("auto_open", "refresh_sources"):
            if getattr(args, key):
                cfg[key] = getattr(args, key) == "on"
        if args.browser_desktop:
            cfg["browser_desktop"] = str(Path(args.browser_desktop).expanduser().resolve())
            cfg["browser_command"] = []
        if args.browser_executable:
            cfg["browser_command"] = [str(Path(args.browser_executable).expanduser().resolve())]
            cfg["browser_desktop"] = ""
        previous = load(repo.config_path, {})
        save(repo.config_path, cfg)
        try:
            repo.cfg()
        except Exception:
            save(repo.config_path, previous)
            raise
        print("Zapisano konfigurację lokalną:", repo.config_path)
    elif args.cmd == "sources":
        if args.action == "refresh":
            changed_sources = refresh_sources(repo, force=True)
            print("Sprawdzono dostępność źródeł. Zmiana treści:", changed_sources)
            if changed_sources and repo.cfg()["enabled"]:
                ident = enqueue(repo, "sources")
                if ident:
                    spawn(repo)
                    print("Dodano przegląd zmienionych źródeł:", ident)
        cache = load(repo.state / "source-cache.json", {})
        print("Sprawdzenie HTTP nie potwierdza aktualności przepisów ani poprawności ich interpretacji.")
        for value in cache.get("records", []):
            print(value["id"], value["status"], value["retrieved_at"] or value["attempted_at"])
        if not cache:
            print("Źródła nie były jeszcze sprawdzane lokalnie; dostępne są datowane karty startowe.")
    elif args.cmd == "decide":
        with repo.lock("worker", blocking=False) as acquired:
            if not acquired:
                raise RuntimeError("Trwa analiza; zapisz decyzję po jej zakończeniu")
            findings, _ = registry_state(repo)
            finding = next((f for f in findings if f["id"] == args.finding_id), None)
            if finding is None:
                raise RuntimeError("Nie znaleziono ustalenia na bieżącej historii Git")
            if not args.note.strip():
                raise RuntimeError("Decyzja wymaga uzasadnienia i wskazania dowodu")
            event_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
            save(repo.note("decisions/" + event_id + ".json"), dict(id=event_id, at=now(),
                 key=finding["key"], report_id=finding.get("assessment_report_id", finding["report_id"]), status=args.status,
                 note=args.note, provenance="author_statement"))
            regenerate(repo)
        print("Zapisano deklarację autora; nie jest automatycznym potwierdzeniem zgodności prawnej.")
    elif args.cmd == "status":
        print("Repozytorium:", repo.root, "\nGałąź:", repo.branch(), "\nWłączony:", repo.cfg()["enabled"])
        print("Timer:", unit_name(repo) + ".timer", "\nKonfiguracja:", repo.config_path,
              "\nLog:", repo.state / "agent.log")
        for path in repo.jobs():
            job = load(path)
            progress = (f'części {len(job["parts_done"])}/{len(job["part_targets"])}'
                        if "part_targets" in job else "plan części jeszcze niegotowy")
            print(job["id"], job["kind"], job["status"], job["branch"], progress, job["error"])
        if not current_reports(repo):
            active = [load(p) for p in repo.jobs() if load(p)["branch"] == repo.branch()]
            if any(j["status"] in {"pending", "running"} for j in active):
                print("Przegląd trwa lub czeka w kolejce; raport pojawi się po ukończeniu wszystkich części.")
            elif any(j["status"] == "failed" for j in active):
                print("Przegląd zatrzymany. Po usunięciu przyczyny wznów istniejące zadanie przez retry ID; zachowane części pozostają zapisane.")
            else:
                print("Brak opublikowanego przeglądu na bieżącej historii. Wykonaj baseline --background.")
    elif args.cmd == "open":
        with repo.lock("worker", blocking=False) as acquired:
            if acquired:
                regenerate(repo)
        open_browser(repo)
        print("Przekazano stronę raportów do BrowserOS.")
    elif args.cmd == "demo":
        data = load(HERE / "demo.json")
        page = repo.state / "site/demo.html"
        atomic(page, render(data["findings"], data["flows"], data["reports"], "demo", demo=True))
        open_browser(repo, page)
        print("Otwarto fikcyjną demonstrację. Nie analizowano projektu, nie wywoływano modelu i nie zmieniono rejestru ustaleń.")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("Błąd agenta prawnego:", ex, file=sys.stderr)
        sys.exit(1)
