#!/usr/bin/env python3
"""Local commit-triggered learning pipeline; Python 3.10+, Linux, no pip packages."""
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

sys.dont_write_bytecode = True
from schema import SCHEMA, PRACTICE_SCHEMA, check_schema, validate, validate_self_test
from view import page, markdown, diagram_svg, self_test_markdown

HERE = Path(__file__).resolve().parent
RUNTIME_FILES = ['agent.py', 'schema.py', 'view.py', 'auto-instructions.md',
                 'practice-instructions.md', 'example-lesson.json']
MARKER = '# learning-agent managed hook v2'
BLOCK_START = '<!-- LEARNING-AGENT-AUTO:START -->'
BLOCK_END = '<!-- LEARNING-AGENT-AUTO:END -->'
EXTS = {'.rs', '.toml', '.cs', '.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.java', '.kt', '.kts',
        '.html', '.css', '.sql', '.sh', '.bash', '.shader', '.uxml', '.uss', '.unity', '.prefab'}
SKIP_PARTS = {'target', '.idea', '.vscode', '.codex', 'Library', 'Temp', 'obj', 'Obj', 'bin', 'Logs', 'Build', 'Builds',
              'node_modules', '.venv', 'venv', '__pycache__', '.git'}
SKIP_PREFIXES = ('tools/learning-agent/', 'tools/legal-agent/', 'docs/learning/', 'docs/legal/')
DEFAULTS = {
    'enabled': True, 'auto_open': True, 'model': 'gpt-6.1-sol', 'reasoning': 'medium',
    'codex_command': ['codex'], 'browser_command': [], 'browser_desktop': '',
    'debounce_seconds': 12, 'timeout_seconds': 1200, 'max_files_per_lesson': 3,
    'max_snapshot_bytes': 16_000_000, 'max_blob_bytes': 350_000,
    'max_changed_files': 120, 'max_lessons_in_browser': 30,
    'plan_files': ['docs/APP_PLAN.md', 'docs/PROJECT_PLAN.md', 'docs/PROJECT_STATUS.md',
                   'docs/DECISIONS.md', 'docs/ROADMAP.md', 'ROADMAP.md'],
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'Odmowa zapisu przez symlink: {path}')
    raw = data.encode('utf-8') if isinstance(data, str) else data
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def save(path, data):
    atomic(path, json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def load(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def git(root, *args, check=True):
    proc = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if check and proc.returncode:
        raise RuntimeError(proc.stderr.decode('utf-8', 'replace').strip())
    return proc.stdout


def safe_rel(path):
    p = PurePosixPath(path)
    return bool(path and not p.is_absolute() and '..' not in p.parts and '\x00' not in path)


def secret_path(path):
    name = PurePosixPath(path).name.lower()
    return (name.startswith('.env') or name in {'auth.json', 'credentials.json', 'secrets.json'}
            or name.endswith(('.pem', '.key', '.p12', '.pfx', '.jks', '.keystore'))
            or any(x in name for x in ['service-account', 'private-key']))


def is_source(path):
    return (safe_rel(path) and not secret_path(path)
            and not any(x in SKIP_PARTS for x in PurePosixPath(path).parts)
            and not path.startswith(SKIP_PREFIXES) and (PurePosixPath(path).suffix.lower() in EXTS or PurePosixPath(path).name == 'Cargo.lock'))


class Repo:
    def __init__(self, path):
        self.root = Path(git(path, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
        if '\n' in str(self.root) or '\r' in str(self.root):
            raise RuntimeError('Ścieżka repozytorium z nową linią nie jest obsługiwana przez instalator')
        self.gitdir = Path(git(self.root, 'rev-parse', '--absolute-git-dir').decode().strip())
        self.state = self.gitdir / 'learning-agent'
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.notes = self.root / 'docs/learning'
        self.config_path = self.state / 'config.json'

    def config(self):
        config = dict(DEFAULTS)
        config.update(load(self.config_path, {}))
        if config['reasoning'] not in {'low', 'medium', 'high', 'xhigh', 'max'}:
            raise RuntimeError('Niepoprawny poziom reasoning w config.json')
        for key in ['codex_command', 'browser_command']:
            if not isinstance(config[key], list) or any(not isinstance(x, str) for x in config[key]):
                raise RuntimeError(f'{key} musi być listą argumentów JSON, nie poleceniem powłoki')
        if not config['codex_command']:
            raise RuntimeError('Puste codex_command')
        for key in ['max_files_per_lesson', 'max_changed_files', 'max_blob_bytes', 'max_snapshot_bytes', 'timeout_seconds', 'max_lessons_in_browser']:
            if not isinstance(config[key], int) or config[key] < 1:
                raise RuntimeError(f'Niepoprawna wartość {key}')
        if not isinstance(config['debounce_seconds'], (int, float)) or config['debounce_seconds'] < 0:
            raise RuntimeError('Niepoprawna wartość debounce_seconds')
        return config

    def note_path(self, relative=''):
        path = self.notes / relative
        if path.resolve() != path and not path.resolve().is_relative_to(self.notes.resolve()):
            raise RuntimeError('Symlink wyprowadza notatki poza docs/learning')
        # Existing symlink anywhere in notes is not an output target.
        current = self.root
        for part in path.relative_to(self.root).parts:
            current /= part
            if current.is_symlink(): raise RuntimeError(f'Symlink w ścieżce notatek: {current}')
        return path

    @contextmanager
    def lock(self, name):
        with (self.state / (name+'.lock')).open('a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield f

    def head(self):
        return git(self.root, 'rev-parse', 'HEAD').decode().strip()

    def jobs(self):
        return sorted((self.state/'jobs').glob('*.json'), key=lambda p: load(p)['enqueued_at'])

    def log(self, message):
        with (self.state/'agent.log').open('a', encoding='utf-8') as f:
            f.write(f'{now()} {message}\n')


def changed_paths(repo, commit):
    parents = git(repo.root, 'rev-list', '--parents', '-n', '1', commit).decode().split()[1:]
    if parents:
        data = git(repo.root, 'diff', '--name-only', '-z', parents[0], commit, '--')
    else:
        data = git(repo.root, 'diff-tree', '--root', '--no-commit-id', '-r', '--name-only', '-z', commit)
    return [p.decode('utf-8') for p in data.split(b'\0') if p]


def enqueue(repo, explicit=None, force=False, background=False):
    cfg = repo.config()
    if not cfg['enabled'] and not force: return None
    if not (repo.root/'LEARNING_AGENT.md').is_file():
        repo.log('Pomijam: bieżąca gałąź nie ma LEARNING_AGENT.md')
        return None
    commit = repo.head()
    paths = sorted(set(explicit if explicit is not None else changed_paths(repo, commit)))
    paths = [p for p in paths if is_source(p)]
    if not paths: return None
    if len(paths) > cfg['max_changed_files']:
        raise RuntimeError('Commit przekracza limit plików; uruchom now --file dla wybranego zakresu lub zmień lokalny limit')
    identity = commit[:16]+'-'+digest('\0'.join(paths).encode())[:10]
    with repo.lock('queue'):
        target = repo.state/'jobs'/f'{identity}.json'
        if not target.exists():
            save(target, {'id': identity, 'commit': commit,
                          'lesson_format_version': 3,
                          'branch': git(repo.root, 'rev-parse', '--abbrev-ref', 'HEAD').decode().strip(),
                          'paths': paths, 'enqueued_at': now(), 'status': 'pending', 'parts_done': [],
                          'error': '', 'finished_at': ''})
    if background: spawn(repo)
    return identity


def spawn(repo):
    runner = repo.state/'runtime/agent.py'
    if not runner.exists(): runner = HERE/'agent.py'
    with (repo.state/'worker.log').open('ab') as out:
        subprocess.Popen([sys.executable, str(runner), '--repo', str(repo.root), 'work'],
                         stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                         start_new_session=True, close_fds=True, cwd=repo.root)


def lessons(repo):
    result = []
    folder = repo.note_path('lessons')
    if folder.exists():
        for path in sorted(folder.glob('*/lesson.json')):
            if path.is_symlink() or path.parent.is_symlink():
                raise RuntimeError('Symlink w bibliotece lekcji')
            value = load(path)
            if not isinstance(value, dict) or '_meta' not in value:
                raise RuntimeError(f'Uszkodzony zapis lekcji: {path}')
            result.append(value)
    return result


def known_concepts(repo):
    known = {}
    for lesson in lessons(repo):
        for c in lesson['new_concepts']:
            known[c['key']] = c
    manual_index = repo.note_path('concepts/INDEX.md')
    if manual_index.exists():
        for line in manual_index.read_text().splitlines():
            match = re.match(r'^\|\s*`?([a-z][a-z0-9.-]{2,100})`?\s*\|', line)
            if match: known.setdefault(match[1], {'key':match[1], 'title':match[1]})
    return known


def memory_signature(repo):
    entries = []
    if repo.notes.exists():
        for path in sorted(repo.notes.rglob('*')):
            if path.is_symlink(): raise RuntimeError('Symlink w pamięci nauki')
            if not path.is_file(): continue
            rel = path.relative_to(repo.notes).as_posix()
            if rel.endswith('lesson.json') or (path.suffix == '.md' and not rel.startswith(('lessons/', 'concepts/auto/')) and path.name != 'AUTO_INDEX.md'):
                entries.append(rel+':'+digest(path.read_bytes()))
    return digest('\n'.join(entries).encode())


def snapshot(repo, job, selected, folder, cfg):
    commit = job['commit']
    manifest = {'commit':commit, 'branch':job['branch'], 'lesson_files':[],
                'snapshot_files':[], 'plan_files':[], 'known_concept_keys':sorted(known_concepts(repo)),
                'omitted':[], 'analysis':'static-only; no execution'}
    tree = git(repo.root, 'ls-tree', '-rlz', commit).split(b'\0')
    objects = {}
    for entry in tree:
        if not entry: continue
        meta, raw_path = entry.split(b'\t',1)
        mode, typ, oid, size = meta.decode().split()
        path = raw_path.decode('utf-8')
        if typ == 'blob' and mode in {'100644','100755'}:
            objects[path] = (oid, int(size))
    plan_paths = set(cfg['plan_files'])
    plan_paths.update(p for p in objects if p.startswith('docs/tasks/') and p.endswith('.md') and not p.endswith('_TEMPLATE.md'))
    total = 0
    ordered = list(selected)+sorted(p for p in objects if p not in selected)
    for path in ordered:
        if path not in objects: continue
        if (not safe_rel(path) or secret_path(path)
                or any(part in SKIP_PARTS for part in PurePosixPath(path).parts)) : continue
        is_plan = path in plan_paths
        eligible = (is_source(path) or is_plan or path in {'AGENTS.md','ENGINEERING_RULES.md','LEARNING_AGENT.md',
                    'docs/README.md','docs/CODE_MAP.md','docs/ARCHITECTURE.md','Cargo.toml','Cargo.lock'})
        if not eligible: continue
        oid, size = objects[path]
        if size > cfg['max_blob_bytes'] or total+size > cfg['max_snapshot_bytes']:
            manifest['omitted'].append(path+' (limit rozmiaru)')
            if path in selected: raise RuntimeError(f'Wybrany plik przekracza limit migawki: {path}')
            continue
        content = git(repo.root, 'cat-file', 'blob', oid)
        try: content.decode('utf-8')
        except UnicodeDecodeError:
            manifest['omitted'].append(path+' (nietekstowy)')
            if path in selected: raise RuntimeError('Wybrany plik nie jest tekstem UTF-8')
            continue
        target = folder/path
        atomic(target, content)
        item = {'path':path,'snapshot_path':path,'sha256':digest(content),'status':'present'}
        manifest['snapshot_files'].append(item)
        if path in selected:manifest['lesson_files'].append(item)
        if is_plan:manifest['plan_files'].append(path)
        total += size
    parents = git(repo.root,'rev-list','--parents','-n','1',commit).decode().split()[1:]
    for path in selected:
        if any(x['path']==path for x in manifest['lesson_files']):continue
        if path in objects:raise RuntimeError(f'Nie udało się dołączyć wybranego pliku: {path}')
        if not parents:raise RuntimeError('Brak wcześniejszej wersji usuniętego pliku')
        content = git(repo.root,'show',f'{parents[0]}:{path}')
        if len(content)>cfg['max_blob_bytes']:raise RuntimeError('Usunięty plik przekracza limit')
        content.decode('utf-8')
        target = '_previous/'+path
        atomic(folder/target,content)
        item={'path':path,'snapshot_path':target,'sha256':digest(content),'status':'deleted'}
        manifest['lesson_files'].append(item)
        manifest['snapshot_files'].append(item)
    # Always use installed role rules if an older commit predates installation.
    if not (folder/'LEARNING_AGENT.md').exists():
        atomic(folder/'LEARNING_AGENT.md',(repo.root/'LEARNING_AGENT.md').read_bytes())
    memory = folder/'_learning_memory'
    memory.mkdir()
    listing = []
    for key, concept in known_concepts(repo).items():
        listing.append(f'- {key}: {concept["title"]}')
        atomic(memory/(key+'.json'),json.dumps(concept,ensure_ascii=False,indent=2))
    for rel in ['README.md','concepts/INDEX.md','files/INDEX.md','concepts/AUTO_INDEX.md','files/AUTO_INDEX.md']:
        src = repo.note_path(rel)
        if src.is_file():atomic(memory/rel,src.read_bytes())
    # Copy manual cards too, keeping aliases and earlier explanations available.
    manual = repo.note_path('concepts')
    if manual.exists():
        for src in sorted(manual.glob('*.md')):
            if src.name not in {'INDEX.md','AUTO_INDEX.md'}:atomic(memory/'manual'/src.name,src.read_bytes())
    atomic(memory/'INDEX.md','# Pamięć pojęć\n\n'+'\n'.join(listing)+'\n\nOdczytaj także indeks manualny concepts/INDEX.md i odpowiednie karty manual/.\n')
    save(folder/'SOURCE_MANIFEST.json',manifest)
    return manifest


def run_codex(repo, cfg, folder, output, schema=SCHEMA, prompt_name='auto-instructions.md'):
    schema_path=folder/'OUTPUT_SCHEMA.json'
    save(schema_path,schema)
    prompt=(HERE/prompt_name).read_text(encoding='utf-8')
    command=[*cfg['codex_command'],'exec','--sandbox','read-only','--skip-git-repo-check',
             '--model',cfg['model'],'--config',f'model_reasoning_effort="{cfg["reasoning"]}"',
             '--config','approval_policy="never"','--output-schema',str(schema_path),
             '--output-last-message',str(output),'-']
    with (repo.state/'codex.log').open('ab') as log:
        process=subprocess.Popen(command,cwd=folder,stdin=subprocess.PIPE,stdout=log,
                                 stderr=log,start_new_session=True)
        try:
            process.communicate(prompt.encode('utf-8'),timeout=cfg['timeout_seconds'])
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            raise RuntimeError('Przerwano lub przekroczono czas analizy; zobacz codex.log')
        if process.returncode:raise RuntimeError(f'Codex zakończył się kodem {process.returncode}; zobacz codex.log')
    if not output.is_file():raise RuntimeError('Codex nie zapisał końcowego JSON')
    return load(output)


def publish(repo, lesson):
    lesson_id=lesson['_meta']['lesson_id']
    target=repo.note_path('lessons/'+lesson_id)
    if target.exists():return
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.lesson-',dir=target.parent))
    try:
        save(staging/'lesson.json',lesson)
        atomic(staging/'lesson.md',markdown(lesson))
        for i,d in enumerate(lesson['diagrams']):atomic(staging/f'diagram-{i+1}.svg',diagram_svg(d))
        os.replace(staging,target)
    finally:
        if staging.exists():shutil.rmtree(staging)


def regenerate(repo):
    all_lessons=lessons(repo)
    concept_rows=[]
    file_rows=[]
    seen=set()
    for lesson in sorted(all_lessons,key=lambda l:l['_meta']['created_at']):
        m=lesson['_meta']; lid=m['lesson_id']
        for c in lesson['new_concepts']:
            if c['key'] in seen:raise RuntimeError('Duplikat pojęcia w zapisanych lekcjach')
            seen.add(c['key'])
            card=repo.note_path('concepts/auto/'+c['key']+'.md')
            text=f'# {c["title"]}\n\nKlucz: `{c["key"]}` · {c["language"]} · {c["category"]}\n\nStatus: przygotowano — nie potwierdzono przeczytania.\n\n'+c['meaning']+'\n\n'+c['why']+'\n\n````\n'+c['example']+'\n````\n\n'+c['example_explanation']+'\n\nCzęste nieporozumienie: '+c['pitfall']+f'\n\n[Lekcja źródłowa](../../lessons/{lid}/lesson.md)\n'
            atomic(card,text)
            concept_rows.append(f'| `{c["key"]}` | {c["title"].replace("|","/")} | przygotowano | [karta](auto/{c["key"]}.md) |')
        for source in lesson['sources']:
            if source['path'] in m.get('context_file_paths',[]):
                continue
            entry=next(x for x in m['source_files'] if x['path']==source['path'])
            file_rows.append(f'| `{source["path"].replace("|","/")}` | `{m["commit"][:12]}` | `{entry["sha256"][:12]}` | {source["coverage"]} | [lekcja](../lessons/{lid}/lesson.md) |')
    atomic(repo.note_path('concepts/AUTO_INDEX.md'),'# Automatycznie przygotowane pojęcia\n\nPlik generowany z lekcji; własne uwagi dopisuj w indeksie manualnym.\n\n| Klucz | Nazwa | Stan | Karta |\n|---|---|---|---|\n'+'\n'.join(concept_rows)+'\n')
    atomic(repo.note_path('files/AUTO_INDEX.md'),'# Automatyczne wyjaśnienia plików\n\nHistoria według commitów; nie oznacza zgodności z niezapisanymi zmianami.\n\n| Plik | Commit | SHA-256 treści | Zakres | Materiał |\n|---|---|---|---|---|\n'+'\n'.join(file_rows)+'\n')
    latest=sorted(all_lessons,key=lambda l:l['_meta']['created_at'],reverse=True)
    atomic(repo.state/'site/index.html',page(latest[:repo.config()['max_lessons_in_browser']]))
    return latest


def reuse_cached_concepts(lesson, known):
    """Keep current cards authoritative when another lesson finished before a saved recheck."""
    reused = []
    existing = {item['key'] for item in lesson['reused_concepts']}
    fresh = []
    for concept in lesson['new_concepts']:
        key = concept['key']
        if key not in known:
            fresh.append(concept)
            continue
        reused.append(key)
        if key not in existing:
            title = known[key].get('title',concept['title'])
            lesson['reused_concepts'].append({'key':key,
                'reminder':f'Pojęcie „{title}” zostało już przygotowane w innej lekcji; pełne wyjaśnienie pozostaje we wcześniejszej karcie.'})
            existing.add(key)
    lesson['new_concepts'] = fresh
    if reused:
        lesson['limitations'].append('Podczas odzyskiwania wykorzystano istniejące karty zamiast ponownych definicji: '+', '.join(reused)+'. Oryginalna odpowiedź modelu pozostała w results.')
    return reused


def process_job(repo, path, cfg, saved_only=False):
    job=load(path)
    job.update(status='running',error='')
    save(path,job)
    size=cfg['max_files_per_lesson']
    for start in range(0,len(job['paths']),size):
        if not saved_only and not repo.config()['enabled']:
            job['status']='pending';save(path,job)
            return False
        part=start//size+1
        lid=f'{job["id"]}-p{part:03d}'
        if (repo.note_path('lessons/'+lid)/'lesson.json').exists():
            if part not in job['parts_done']:job['parts_done'].append(part)
            save(path,job)
            continue
        before=memory_signature(repo)
        with tempfile.TemporaryDirectory(prefix='learning-snapshot-',dir=repo.state) as name:
            folder=Path(name)
            manifest=snapshot(repo,job,job['paths'][start:start+size],folder,cfg)
            output=repo.state/'results'/f'{lid}.json'
            output.parent.mkdir(exist_ok=True)
            if saved_only:
                if not output.is_file():
                    raise RuntimeError('Brak zapisanej odpowiedzi dla '+lid+'; recheck nie wywołuje modelu. Użyj retry, jeśli chcesz nową analizę')
                lesson=load(output)
            else:
                # Normal retry regenerates output; recheck above always preserves it.
                if output.exists():output.unlink()
                lesson=run_codex(repo,cfg,folder,output)
            known = set(manifest['known_concept_keys'])
            allow_legacy = saved_only and job.get('lesson_format_version',2)<3
            validate(lesson,manifest,folder,known,allow_legacy=allow_legacy,allow_known_new=saved_only)
            reused_after_recheck = []
            if saved_only:
                reused_after_recheck = reuse_cached_concepts(lesson,known_concepts(repo))
                validate(lesson,manifest,folder,known,allow_legacy=allow_legacy)
            if memory_signature(repo)!=before:
                raise RuntimeError('Pamięć nauki zmieniła się podczas analizy; wynik zachowano w results. Użyj retry po przejrzeniu zmian')
            current_branch=git(repo.root,'rev-parse','--abbrev-ref','HEAD').decode().strip()
            ancestor=subprocess.run(['git','-C',str(repo.root),'merge-base','--is-ancestor',job['commit'],'HEAD'],
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
            if current_branch!=job['branch'] or not ancestor:
                raise RuntimeError('Zmieniono gałąź lub historię podczas analizy; nie zapisuję lekcji do innej gałęzi. Wróć do właściwej gałęzi i użyj retry')
            omissions=[f'Pominięto w migawce: {p}' for p in manifest['omitted']]
            lesson['limitations'].extend(omissions)
            targets={entry['path'] for entry in manifest['lesson_files']}
            reported={entry['path'] for entry in lesson['sources']}
            cited={entry['path'] for entry in lesson['plan_connection']['evidence']}
            evidence_files=[]
            for entry in manifest['snapshot_files']:
                if entry['path'] not in cited:continue
                kind = 'plan' if entry['path'] in manifest['plan_files'] else ('implementation' if is_source(entry['path']) else 'context')
                evidence_files.append({**entry,'kind':kind})
            lesson['_meta']={'lesson_id':lid,'commit':job['commit'],'branch':job['branch'],
                             'created_at':now(),
                             'source_files':[entry for entry in manifest['snapshot_files'] if entry['path'] in reported],
                             'lesson_file_paths':sorted(targets),'context_file_paths':sorted(reported-targets),
                             'plan_files':manifest['plan_files'],'static_analysis':True,
                             'evidence_files':evidence_files,'reused_after_recheck':reused_after_recheck,
                             'lesson_format_version':3 if 'self_test' in lesson else 2,
                             'reading_confirmed':False}
            publish(repo,lesson)
        job['parts_done'].append(part)
        save(path,job)
    regenerate(repo)
    job.update(status='done',finished_at=now())
    save(path,job)
    repo.log('Gotowa lekcja: '+job['id'])
    return True


def recheck(repo, job_id):
    """Validate and publish an existing result; never invoke the model."""
    if not re.fullmatch(r'[a-f0-9]{16}-[a-f0-9]{10}',job_id):
        raise RuntimeError('Niepoprawny identyfikator zadania')
    target=repo.state/'jobs'/f'{job_id}.json'
    if not target.is_file():raise RuntimeError('Nie znaleziono zadania: '+job_id)
    with (repo.state/'worker.lock').open('a+') as lock:
        acquire_maintenance_lock(lock)
        try:
            process_job(repo,target,repo.config(),saved_only=True)
        except Exception as ex:
            job=load(target);job.update(status='failed',error=str(ex),finished_at=now());save(target,job)
            raise
        if repo.config()['auto_open']:
            try:open_browser(repo)
            except Exception as ex:repo.log('Lekcja odzyskana; otwarcie przeglądarki nieudane: '+str(ex))
    print('Zapisana odpowiedź sprawdzona ponownie. Stan: done. Model nie był wywoływany.')
    print('Gotowa lekcja:',repo.state/'site/index.html')


def update_runtime(repo):
    """Refresh local hook/timer code without reinstalling or editing project rules."""
    runtime=repo.state/'runtime'
    if not runtime.is_dir():raise RuntimeError('Brak zainstalowanego runtime; najpierw wykonaj install')
    contents={name:(HERE/name).read_bytes() for name in RUNTIME_FILES}
    with (repo.state/'worker.lock').open('a+') as lock:
        acquire_maintenance_lock(lock)
        for name,data in contents.items():atomic(runtime/name,data)
    print('Zaktualizowano lokalny runtime. Zachowano reguły, konfigurację, hook, timer, kolejkę i lekcje.')


def practice(repo, lesson_id, saved_only=False):
    """Add exercises to one published lesson, preserving its explanation and concept history."""
    if not re.fullmatch(r'[a-f0-9]{16}-[a-f0-9]{10}(?:-p\d{3,})?', lesson_id):
        raise RuntimeError('Niepoprawny identyfikator lekcji lub zadania')
    with (repo.state/'worker.lock').open('a+') as lock:
        acquire_maintenance_lock(lock)
        candidates = [x for x in lessons(repo) if x['_meta']['lesson_id'] == lesson_id
                      or x['_meta']['lesson_id'].startswith(lesson_id+'-p')]
        if not candidates:
            raise RuntimeError('Nie znaleziono zapisanej lekcji: '+lesson_id)
        if len(candidates) != 1:
            ids = ', '.join(x['_meta']['lesson_id'] for x in candidates)
            raise RuntimeError('Zadanie ma kilka lekcji. Wybierz jedną część: '+ids)
        lesson = candidates[0]
        meta = lesson['_meta']
        lid = meta['lesson_id']
        if lesson.get('self_test'):
            print('Ta lekcja ma już pytania. Użyj open; nie wywołano modelu.')
            return
        def check_branch():
            branch = git(repo.root,'rev-parse','--abbrev-ref','HEAD').decode().strip()
            ancestor = subprocess.run(['git','-C',str(repo.root),'merge-base','--is-ancestor',meta['commit'],'HEAD'],
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
            if branch != meta['branch'] or not ancestor:
                raise RuntimeError('Wróć na gałąź i historię zapisanej lekcji przed dodaniem ćwiczeń')
        check_branch()
        original_json = repo.note_path('lessons/'+lid+'/lesson.json')
        original_md = repo.note_path('lessons/'+lid+'/lesson.md')
        previous_md = original_md.read_bytes() if original_md.exists() else markdown(lesson).encode('utf-8')
        before = memory_signature(repo)
        cfg = repo.config()
        with tempfile.TemporaryDirectory(prefix='learning-practice-',dir=repo.state) as name:
            folder = Path(name)
            paths = [x['path'] for x in lesson['sources']]
            manifest = snapshot(repo,meta,paths,folder,cfg)
            current_sources = {x['path']:x['sha256'] for x in manifest['snapshot_files']}
            if any(current_sources.get(x['path']) != x['sha256'] for x in meta['source_files']):
                raise RuntimeError('Nie udało się odtworzyć źródeł oryginalnej lekcji')
            save(folder/'PRIOR_LESSON.json',lesson)
            output = repo.state/'results'/f'{lid}-practice.json'
            output.parent.mkdir(exist_ok=True)
            if saved_only:
                if not output.is_file():
                    raise RuntimeError('Brak zachowanych ćwiczeń; practice --recheck nie wywołuje modelu')
                result = load(output)
            else:
                if output.exists():output.unlink()
                result = run_codex(repo,cfg,folder,output,schema=PRACTICE_SCHEMA,
                                   prompt_name='practice-instructions.md')
            check_schema(result,PRACTICE_SCHEMA)
            validate_self_test(result['self_test'],manifest,folder,set(paths))
            if memory_signature(repo) != before or (original_md.exists() and original_md.read_bytes() != previous_md):
                raise RuntimeError('Notatki zmieniły się podczas analizy. Wynik zachowano; przejrzyj zmiany i użyj practice --recheck')
            check_branch()
            lesson['self_test'] = result['self_test']
            lesson['_meta']['practice_created_at'] = now()
            added = '\n'.join(self_test_markdown(lesson))+'\n'
            save(original_json,lesson)
            atomic(original_md,previous_md+b'\n'+added.encode('utf-8'))
        regenerate(repo)
        if cfg['auto_open']:
            try:open_browser(repo)
            except Exception as ex:repo.log('Ćwiczenia zapisane; otwarcie przeglądarki nieudane: '+str(ex))
    print('Dodano pytania i rozwiązania do lekcji: '+lid)
    print('Zachowano wcześniejsze wyjaśnienie, pojęcia i stan przeczytania.')
    if saved_only:print('Odzyskano zapisane ćwiczenia; model nie był wywoływany.')


def acquire_maintenance_lock(lock):
    """Allow an older idle timer to finish its 12s debounce, without waiting forever."""
    deadline=time.monotonic()+15
    announced=False
    while True:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if not announced:
                print('Czekam na zwolnienie kolejki (maksymalnie 15 sekund)...',flush=True)
                announced=True
            if time.monotonic()>=deadline:
                raise RuntimeError('Trwa inna analiza. Zaczekaj na jej zakończenie i ponów polecenie')
            time.sleep(0.2)


def discover_browser(cfg):
    if cfg['browser_command']:return ('command',cfg['browser_command'])
    if cfg['browser_desktop']:
        p=Path(cfg['browser_desktop']).expanduser()
        if p.is_file() and shutil.which('gio'):return ('desktop',str(p))
        raise RuntimeError('Nie znaleziono wskazanego pliku .desktop albo programu gio')
    directories=[Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'applications']
    directories += [Path(x)/'applications' for x in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':')]
    for directory in directories:
        for p in sorted(directory.glob('*.desktop')):
            try:s=p.read_text(encoding='utf-8')
            except (OSError,UnicodeError):continue
            if 'browseros' in p.name.lower() or re.search(r'^Name(?:\[[^]]+\])?=.*browseros',s,re.I|re.M):
                if shutil.which('gio'):return ('desktop',str(p))
    for name in ['browseros','BrowserOS','browseros-browser']:
        path=shutil.which(name)
        if path:return ('command',[path])
    raise RuntimeError('Nie znaleziono BrowserOS. Użyj configure --browser-executable /pełna/ścieżka albo --browser-desktop /ścieżka.desktop')


def open_browser(repo):
    cfg=repo.config()
    file=repo.state/'site/index.html'
    if not file.is_file():regenerate(repo)
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise RuntimeError('Brak sesji graficznej. Lekcja jest zapisana; otwórz ją później poleceniem open')
    mode,browser=discover_browser(cfg)
    url=file.as_uri()
    command=['gio','launch',browser,url] if mode=='desktop' else [*browser,url]
    with (repo.state/'browser.log').open('ab') as log:
        result=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True)
        try:
            if result.wait(timeout=1):raise RuntimeError('BrowserOS nie otworzył strony; zobacz browser.log')
        except subprocess.TimeoutExpired:
            pass  # A foreground browser may keep running; never terminate it as a timeout.


def work(repo):
    lock=(repo.state/'worker.lock').open('a+')
    try:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        save(repo.state/'running.json',{'pid':os.getpid(),'started_at':now()})
        with repo.lock('queue'):
            for p in repo.jobs():
                j=load(p)
                if j['status']=='running':
                    j.update(status='pending',error='Wznowienie po przerwaniu procesu')
                    save(p,j)
            if not any(load(p)['status']=='pending' for p in repo.jobs()):
                fcntl.flock(lock,fcntl.LOCK_UN)
                return  # An idle timer must not hold the lock through the debounce delay.
        cfg=repo.config()
        if cfg['debounce_seconds']:time.sleep(cfg['debounce_seconds'])
        changed=False
        while True:
            cfg=repo.config()
            if not cfg['enabled'] or not (repo.root/'LEARNING_AGENT.md').is_file():break
            with repo.lock('queue'):
                waiting=[p for p in repo.jobs() if load(p)['status']=='pending']
            if waiting:
                for p in waiting:
                    if not repo.config()['enabled']:break
                    try:
                        if process_job(repo,p,cfg):changed=True
                    except Exception as ex:
                        j=load(p);j.update(status='failed',error=str(ex),finished_at=now());save(p,j)
                        repo.log('Błąd '+j['id']+': '+str(ex))
                continue
            if changed:
                regenerate(repo)
                if cfg['auto_open']:
                    try:open_browser(repo)
                    except Exception as ex:repo.log('Lekcja zapisana; otwarcie przeglądarki nieudane: '+str(ex))
                changed=False
            # Release worker lock while holding queue lock: enqueue cannot race our exit.
            with repo.lock('queue'):
                if any(load(p)['status']=='pending' for p in repo.jobs()):continue
                fcntl.flock(lock,fcntl.LOCK_UN)
                return
    finally:
        lock.close()


def replace_region(text, block):
    region=BLOCK_START+'\n'+block.rstrip()+'\n'+BLOCK_END
    if BLOCK_START in text:
        if BLOCK_END not in text:raise RuntimeError('Niekompletna sekcja instrukcji; nie nadpisuję')
        return re.sub(re.escape(BLOCK_START)+'.*?'+re.escape(BLOCK_END),lambda _:region,text,flags=re.S)
    return text.rstrip()+'\n\n'+region+'\n'


def shell_quote(s):
    return "'"+str(s).replace("'", "'\"'\"'")+"'"


def timer_name(repo):
    return 'learning-agent-'+digest(str(repo.root).encode())[:12]


def unit_quote(s):
    return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'


def install(repo, with_timer, no_hook=False):
    custom=git(repo.root,'config','--get','core.hooksPath',check=False).decode().strip()
    if custom and not no_hook:raise RuntimeError('Repozytorium ma własny core.hooksPath. Użyj install --no-hook i dołącz wywołanie do istniejącego mechanizmu zgodnie z poradnikiem')
    common=Path(git(repo.root,'rev-parse','--git-common-dir').decode().strip())
    if not common.is_absolute():common=(repo.root/common).resolve()
    if common!=repo.gitdir and not no_hook:
        raise RuntimeError('Dodatkowy git worktree wymaga install --no-hook; nie zmieniam współdzielonych hooków')
    package=HERE.parent.parent
    if not (package/'LEARNING_AGENT.md').is_file():raise RuntimeError('Install uruchom z wersjonowanego tools/learning-agent, nie kopii runtime')
    if not shutil.which('git') or not shutil.which('python3'):raise RuntimeError('Brak Git/Python 3')
    role=repo.root/'LEARNING_AGENT.md'
    new_role=(package/'LEARNING_AGENT.md').read_bytes()
    if role.is_file() and role.read_bytes()!=new_role and not (repo.state/'installed.json').exists():
        backup=repo.state/'LEARNING_AGENT.before-install.md';atomic(backup,role.read_bytes())
    atomic(role,new_role)
    agents=repo.root/'AGENTS.md'
    old=agents.read_text() if agents.exists() else '# Instrukcje projektu\n'
    if agents.is_symlink():raise RuntimeError('AGENTS.md jest symlinkiem')
    if not (repo.state/'AGENTS.before-install.md').exists():atomic(repo.state/'AGENTS.before-install.md',old)
    block=(package/'DODAJ_DO_AGENTS.md').read_text()
    atomic(agents,replace_region(old,block))
    for rel in ['README.md','concepts/INDEX.md','files/INDEX.md']:
        dest=repo.note_path(rel)
        if not dest.exists():atomic(dest,(package/'docs/learning'/rel).read_bytes())
    for rel in ['concepts/INDEX.md','files/INDEX.md']:
        dest=repo.note_path(rel)
        contents=dest.read_text()
        link='\n\n[Materiały przygotowane automatycznie](AUTO_INDEX.md)\n'
        if '(AUTO_INDEX.md)' not in contents:atomic(dest,contents.rstrip()+link)
    runtime=repo.state/'runtime';runtime.mkdir(exist_ok=True)
    for name in RUNTIME_FILES:
        atomic(runtime/name,(HERE/name).read_bytes())
    if not repo.config_path.exists():save(repo.config_path,DEFAULTS)
    hook=repo.gitdir/'hooks/post-commit';hook.parent.mkdir(exist_ok=True)
    backup=repo.state/'post-commit.before-learning-agent'
    installation=load(repo.state/'installed.json',{})
    if not no_hook and hook.exists() and MARKER not in hook.read_text(errors='replace'):
        if backup.exists():raise RuntimeError('Istnieje wcześniejsza kopia hooka; nie nadpisuję zmodyfikowanego hooka')
        shutil.copy2(hook,backup)
    wrapper=f'''#!/usr/bin/env bash
{MARKER}
learning_status=0
if [[ -x {shell_quote(backup)} ]]; then
  {shell_quote(backup)} "$@" || learning_status=$?
fi
{shell_quote(sys.executable)} {shell_quote(runtime/'agent.py')} --repo {shell_quote(repo.root)} enqueue --background >>{shell_quote(repo.state/'hook.log')} 2>&1 || true
exit "$learning_status"
'''
    if not no_hook and hook.exists() and MARKER in hook.read_text(errors='replace'):
        expected=installation.get('hook_sha256')
        if expected and digest(hook.read_bytes())!=expected:raise RuntimeError('Zainstalowany hook został zmieniony ręcznie; zachowuję go')
    if not no_hook:
        atomic(hook,wrapper);hook.chmod(0o755)
        installation['hook_sha256']=digest(hook.read_bytes())
    installation.update(installed_at=now(),repo=str(repo.root))
    save(repo.state/'installed.json',installation)
    regenerate(repo)
    if with_timer:
        directory=Path.home()/'.config/systemd/user';directory.mkdir(parents=True,exist_ok=True)
        name=timer_name(repo)
        service=f'''[Unit]\nDescription=Lokalny nauczyciel kodu — kolejka lekcji\n[Service]\nType=oneshot\nExecStart={unit_quote(sys.executable)} {unit_quote(runtime/'agent.py')} --repo {unit_quote(repo.root)} work\nTimeoutStartSec=infinity\n'''
        timer=f'''[Unit]\nDescription=Wznawianie kolejki nauczyciela po zalogowaniu\n[Timer]\nOnStartupSec=45s\nOnUnitInactiveSec=60s\nUnit={name}.service\n[Install]\nWantedBy=timers.target\n'''
        atomic(directory/(name+'.service'),service);atomic(directory/(name+'.timer'),timer)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        subprocess.run(['systemctl','--user','enable','--now',name+'.timer'],check=True)
    print('Zainstalowano. Reguły i notatki: repozytorium. Konfiguracja lokalna:',repo.config_path)
    print('Przed pierwszą analizą wykonaj doctor oraz demo. Kod aplikacji nie został zmieniony.')


def uninstall(repo):
    cfg=repo.config();cfg['enabled']=False;save(repo.config_path,cfg)
    hook=repo.gitdir/'hooks/post-commit';meta=load(repo.state/'installed.json',{})
    if hook.exists() and digest(hook.read_bytes())==meta.get('hook_sha256'):
        backup=repo.state/'post-commit.before-learning-agent'
        if backup.exists():shutil.copy2(backup,hook)
        else:hook.unlink()
    elif hook.exists():print('Hook zmieniony poza instalatorem — pozostawiono go do ręcznego przeglądu.')
    name=timer_name(repo)
    if shutil.which('systemctl'):
        subprocess.run(['systemctl','--user','disable','--now',name+'.timer'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Wyłączono. Zachowano lekcje, reguły, konfigurację i kopie zapasowe. Bieżąca analiza, jeśli trwa, może dokończyć swoją część.')


def demo(repo):
    d=load(HERE/'example-lesson.json')
    d['_meta'].update(lesson_id='demo',created_at=now())
    atomic(repo.state/'site/index.html',page([d]));open_browser(repo)
    print('Otwarto demonstrację. Historia nauki pozostała bez zmian.')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default='.')
    sub=p.add_subparsers(dest='cmd',required=True)
    install_p=sub.add_parser('install');install_p.add_argument('--timer',action='store_true');install_p.add_argument('--no-hook',action='store_true')
    for command in ['work','status','doctor','retry','pause','resume','open','demo','uninstall','update']:sub.add_parser(command)
    recheck_p=sub.add_parser('recheck');recheck_p.add_argument('job_id')
    practice_p=sub.add_parser('practice');practice_p.add_argument('lesson_id');practice_p.add_argument('--recheck',action='store_true')
    enqueue_p=sub.add_parser('enqueue');enqueue_p.add_argument('--background',action='store_true')
    now_p=sub.add_parser('now');now_p.add_argument('--file',action='append',dest='files');now_p.add_argument('--background',action='store_true')
    c=sub.add_parser('configure')
    c.add_argument('--browser-executable');c.add_argument('--browser-desktop');c.add_argument('--auto-open',choices=['on','off'])
    c.add_argument('--reasoning',choices=['low','medium','high','xhigh','max']);c.add_argument('--model')
    c.add_argument('--debounce',type=int)
    a=p.parse_args(argv);repo=Repo(a.repo)
    if a.cmd=='install':install(repo,a.timer,a.no_hook)
    elif a.cmd=='update':update_runtime(repo)
    elif a.cmd=='recheck':recheck(repo,a.job_id)
    elif a.cmd=='practice':practice(repo,a.lesson_id,a.recheck)
    elif a.cmd=='uninstall':uninstall(repo)
    elif a.cmd=='work':work(repo)
    elif a.cmd in {'enqueue','now'}:
        ident=enqueue(repo,explicit=getattr(a,'files',None),force=a.cmd=='now',background=a.background)
        print('W kolejce: '+ident if ident else 'Brak zmian własnego kodu do analizy.')
        if a.cmd=='now' and ident and not a.background:
            cfg=repo.config()
            if not cfg['enabled']:print('Agent jest wstrzymany. Użyj resume.');return
            work(repo)
            job=load(repo.state/'jobs'/f'{ident}.json')
            print('Stan:',job['status'])
            if job['status']=='failed':raise RuntimeError(job['error'])
            if job['status']=='done':print('Gotowa lekcja:',repo.state/'site/index.html')
    elif a.cmd in {'pause','resume'}:
        cfg=repo.config();cfg['enabled']=a.cmd=='resume';save(repo.config_path,cfg)
        if a.cmd=='resume':spawn(repo)
        print('Wznowiono kolejkę.' if a.cmd=='resume' else 'Wstrzymano. Trwająca część może zostać ukończona; kolejne nie wystartują.')
    elif a.cmd=='retry':
        with repo.lock('queue'):
            for path in repo.jobs():
                job=load(path)
                if job['status']=='failed':job.update(status='pending',error='');save(path,job)
        spawn(repo);print('Ponowiono nieudane zadania; zapisane części zostaną zachowane.')
    elif a.cmd=='configure':
        cfg=repo.config()
        if a.browser_executable:
            cfg['browser_command']=[str(Path(a.browser_executable).expanduser().resolve())];cfg['browser_desktop']=''
        if a.browser_desktop:cfg['browser_desktop']=str(Path(a.browser_desktop).expanduser().resolve());cfg['browser_command']=[]
        if a.auto_open:cfg['auto_open']=a.auto_open=='on'
        if a.reasoning:cfg['reasoning']=a.reasoning
        if a.model:cfg['model']=a.model
        if a.debounce is not None:cfg['debounce_seconds']=a.debounce
        save(repo.config_path,cfg);repo.config();print(repo.config_path)
    elif a.cmd=='status':
        print('Repozytorium:',repo.root,'\nGałąź:',git(repo.root,'rev-parse','--abbrev-ref','HEAD').decode().strip())
        print('Włączony:',repo.config()['enabled'],'\nKonfiguracja:',repo.config_path,'\nLog:',repo.state/'agent.log')
        for path in repo.jobs():
            job=load(path);print(job['id'],job['status'],job['error'])
    elif a.cmd=='doctor':
        cfg=repo.config()
        print('Python:',sys.version.split()[0]);print('Git:',git(repo.root,'--version').decode().strip())
        try:
            result=subprocess.run([*cfg['codex_command'],'--version'],capture_output=True,text=True,timeout=15)
            print('Codex:',result.stdout.strip() or result.stderr.strip())
        except (OSError,subprocess.TimeoutExpired) as ex:print('Codex niedostępny:',ex)
        try:print('BrowserOS:',discover_browser(cfg))
        except RuntimeError as ex:print(ex)
        print('Sesja graficzna:',bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')))
        print('Hook:',(repo.gitdir/'hooks/post-commit').exists(),'\nReguły:',(repo.root/'LEARNING_AGENT.md').exists())
        print('Logowanie Codexa sprawdź osobno: codex login status. Nie odczytuj plików poświadczeń.')
    elif a.cmd=='open':regenerate(repo);open_browser(repo)
    elif a.cmd=='demo':demo(repo)


if __name__=='__main__':
    try:main()
    except Exception as ex:
        print('Błąd nauczyciela:',str(ex),file=sys.stderr)
        sys.exit(1)
