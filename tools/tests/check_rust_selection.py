"""Offline synthetic checks; each tool runs in a separate interpreter."""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
if len(sys.argv) == 1:
    for tool in ('learning-agent', 'legal-agent'):
        subprocess.run([sys.executable, __file__, tool], check=True)
    sys.exit()
tool = sys.argv[1]
sys.path.insert(0, str(ROOT / 'tools' / tool))
import agent as a

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    def git(*args):
        return subprocess.check_output(['git', '-C', tmp, *args]).decode().strip()
    git('init', '-q')
    contents = {'src/main.rs': 'fn main() {}\n', 'Cargo.toml': '[package]\nname="synthetic"\n',
                'Cargo.lock': 'version = 4\n', 'target/generated.rs': 'GENERATED',
                'nested/target/Cargo.toml': 'GENERATED', '.env': 'DO_NOT_READ',
                'credentials.json': 'DO_NOT_READ', 'private-key.rs': 'DO_NOT_READ',
                'docs/APP_PLAN.md': '# Synthetic plan\n'}
    for name, text in contents.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'synthetic')
    repo = a.Repo(root)
    # Exercise installer requirements only inside disposable synthetic repos.
    if tool == 'learning-agent':
        a.install(repo, False, no_hook=True)
        select = a.is_source
        cfg = dict(a.DEFAULTS)
        cfg['plan_files'] = ['docs/APP_PLAN.md', 'target/generated.rs', '.env']
        folder = root / 'snapshot'
        folder.mkdir()
        manifest = a.snapshot(repo, {'commit': git('rev-parse', 'HEAD'), 'branch': 'test'},
                              ['src/main.rs'], folder, cfg)
        paths = {x['path'] for x in manifest['snapshot_files']}
    else:
        a.install(repo, timer=False)
        cfg = repo.cfg()
        cfg.update(refresh_sources=False, auto_open=False)
        a.save(repo.config_path, cfg)
        select = a.candidate
        ident = a.enqueue(repo, 'baseline', manual=True)
        job = a.load(repo.state / 'jobs' / (ident + '.json'))
        bundle = a.build_bundle(repo, job, job['targets'])
        paths = {x['path'] for x in bundle['files']}
        a.CONTEXT_PATHS += ['target/generated.rs', '.env']
        assert not {'target/generated.rs', '.env'} & {x['path'] for x in a.context(repo)[0]}
        try:
            a.enqueue(repo, 'baseline', files=['target/generated.rs'], manual=True)
        except RuntimeError:
            pass
        else:
            raise AssertionError('explicit target accepted')
    for name in ('src/main.rs', 'Cargo.toml', 'Cargo.lock'):
        assert select(name), name
        assert name in paths, (name, paths)
    for name in ('target/generated.rs', 'nested/target/Cargo.toml', '.env', 'credentials.json', 'private-key.rs'):
        assert not select(name), name
        assert name not in paths, name
    print(tool + ': selection, snapshot/context, Cargo and secret exclusions OK')
