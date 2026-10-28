from __future__ import annotations
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import agent as a
import schema
import sources
import view


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.tmp = tempfile.TemporaryDirectory(prefix="legal-test-")
        self.root = Path(self.tmp.name) / "projekt ze spacjami"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "AGENTS.md").write_text("# Zasady\nDomyślnie dokumentacja.\n")
        (self.root / "ENGINEERING_RULES.md").write_text("# Reguły\nZachowaj zmiany autora.\n")
        (self.root / "backend").mkdir()
        (self.root / "backend/main.py").write_text("def transcribe(audio):\n    save_audio(audio)\n")
        self.commit("initial")
        self.repo = a.Repo(self.root)
        a.install(self.repo)
        cfg = self.repo.cfg()
        cfg.update(codex_command=[sys.executable, str(HERE / "tests/fake_codex.py")], auto_open=False,
                   refresh_sources=False, files_per_part=1)
        a.save(self.repo.config_path, cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def baseline(self):
        ident = a.enqueue(self.repo, "baseline", manual=True)
        a.work(self.repo)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ident+".json"))["status"], "done")
        return ident

    def test_install_preserves_hook_and_learning_agent(self):
        hook = self.repo.gitdir / "hooks/post-commit"
        hook.write_text("#!/bin/bash\n# learning-agent managed hook v2\nexit 0\n")
        hook.chmod(0o755)
        (self.root/"LEARNING_AGENT.md").write_text("reguły nauki")
        before = hook.read_bytes()
        a.install(self.repo)
        self.assertEqual(hook.read_bytes(), before)
        self.assertEqual((self.root/"LEARNING_AGENT.md").read_text(), "reguły nauki")
        agents = (self.root/"AGENTS.md").read_text()
        self.assertEqual(agents.count(a.BEGIN), 1)
        self.assertIn("Domyślnie dokumentacja.", agents)

    def test_update_preserves_profile_rules_config(self):
        for name in ("APP_PROFILE.md", "DECISIONS.md"):
            self.repo.note(name).write_text("własny wpis autora\n")
        (self.root/"LEGAL_AGENT.md").write_text("własne reguły\n")
        config = self.repo.config_path.read_bytes()
        a.update(self.repo)
        self.assertEqual(self.repo.config_path.read_bytes(), config)
        self.assertEqual(self.repo.note("APP_PROFILE.md").read_text(), "własny wpis autora\n")
        self.assertEqual((self.root/"LEGAL_AGENT.md").read_text(), "własne reguły\n")

    def test_timer_install_uses_own_unit_and_no_hook(self):
        calls = []
        real = subprocess.run
        def run(args, **kw):
            if args[0] == "systemctl":
                calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            return real(args, **kw)
        home = Path(self.tmp.name)/"home"
        with patch.object(Path, "home", return_value=home), patch.object(a.subprocess, "run", side_effect=run):
            a.install(self.repo, timer=True)
        unit = home/".config/systemd/user"/(a.unit_name(self.repo)+".service")
        self.assertIn(" tick\n", unit.read_text())
        self.assertTrue(any("enable" in c for c in calls))
        self.assertFalse((self.repo.gitdir/"hooks/post-commit").exists())

    def test_full_pipeline_and_local_state_not_in_git(self):
        before = (self.root/"backend/main.py").read_bytes()
        self.baseline()
        self.assertEqual((self.root/"backend/main.py").read_bytes(), before)
        self.assertIn("LEGAL-", self.repo.note("FINDINGS.md").read_text())
        self.assertIn("Audio", self.repo.note("DATA_MAP.md").read_text())
        self.assertTrue((self.repo.state/"site/index.html").is_file())
        status = self.git("status", "--short", "--untracked-files=all")
        self.assertNotIn("codex.log", status)
        self.assertNotIn("inputs/", status)
        self.assertNotIn("worker.lock", status)

    def test_snapshot_is_commit_not_dirty_worktree(self):
        ident = a.enqueue(self.repo, "baseline", manual=True)
        job = a.load(self.repo.state/"jobs"/(ident+".json"))
        (self.root/"backend/main.py").write_text("print('DIRTY_WORKTREE')\n")
        bundle = a.build_bundle(self.repo, job, job["targets"])
        text = next(x["text"] for x in bundle["files"] if x["path"] == "backend/main.py" and x["version"] == "after")
        self.assertIn("save_audio", text)
        self.assertNotIn("DIRTY_WORKTREE", text)

    def test_scanner_handles_multiple_commits_and_ignores_reports(self):
        expected=[]
        for i in range(3):
            (self.root/"backend/main.py").write_text(f"def f{i}():\n    pass\n")
            expected.append(self.commit("change"+str(i)))
        ids = a.scan(self.repo)
        self.assertEqual([a.load(self.repo.state/"jobs"/(i+".json"))["commit"] for i in ids], expected)
        self.assertEqual(a.scan(self.repo), [])
        self.repo.note("FINDINGS.md").write_text("raport\n")
        self.commit("report only")
        self.assertEqual(a.scan(self.repo), [])

    def test_profile_change_triggers_context_review(self):
        self.repo.note("APP_PROFILE.md").write_text("Zmiana celu aplikacji\n")
        ids=a.scan(self.repo)
        self.assertEqual(len(ids),1)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ids[0]+".json"))["kind"],"context")

    def test_deletion_uses_before_version(self):
        (self.root/"backend/main.py").unlink()
        self.commit("remove source")
        ident=a.enqueue(self.repo,"review",manual=True)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        self.assertEqual(job["targets"],[dict(path="backend/main.py",version="before")])
        a.work(self.repo)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ident+".json"))["status"],"done")

    def test_secrets_vendor_and_symlinks_are_excluded(self):
        (self.root/".env").write_text("PASSWORD=secret\n")
        (self.root/"backend/passwords.py").write_text('password = "VERY_SECRET_VALUE"\n')
        (self.root/"backend/token.py").write_text('api_key = "VERY_SECRET_VALUE"\n')
        (self.root/"backend/link.py").symlink_to("token.py")
        self.commit("configuration")
        ident=a.enqueue(self.repo,"baseline",manual=True)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        bundle=a.build_bundle(self.repo,job,job["targets"])
        text=json.dumps(bundle)
        self.assertNotIn("VERY_SECRET_VALUE",text)
        self.assertNotIn('"path": ".env"',text)
        self.assertNotIn('"path": "backend/link.py"',text)
        self.assertFalse(a.candidate("tools/learning-agent/agent.py"))
        self.assertFalse(a.candidate("docs/legal/report.py"))

    def test_schema_rejects_fabricated_quote_reference_and_coverage(self):
        ident=self.baseline()
        bundle=a.load(self.repo.state/"inputs"/(ident+"-p001.json"))
        good=a.load(self.repo.state/"results"/(ident+"-p001.json"))
        for mutate in (lambda r:r["findings"][0]["evidence"][0].update(quote="NOT_IN_FILE"),
                       lambda r:r["findings"][0]["references"][0].update(source_id="FAKE"),
                       lambda r:r["findings"][0]["references"][0].update(section="art. 999"),
                       lambda r:r["coverage"].clear(),
                       lambda r:r.update(fake="field")):
            bad=copy.deepcopy(good)
            mutate(bad)
            with self.assertRaises(ValueError):
                schema.validate(bad,bundle)

    def test_failed_response_can_be_rechecked_without_model(self):
        ident=a.enqueue(self.repo,"baseline",manual=True)
        jobfile=self.repo.state/"jobs"/(ident+".json")
        original=a.run_codex
        def corrupt(repo,bundle,path):
            value=original(repo,bundle,path)
            value["coverage"]=[]
            a.save(path,value)
            return value
        with patch.object(a,"run_codex",side_effect=corrupt):
            a.work(self.repo)
        self.assertEqual(a.load(jobfile)["status"],"failed")
        output=self.repo.state/"results"/(ident+"-p001.json")
        response=a.load(output)
        bundle=a.load(self.repo.state/"inputs"/(ident+"-p001.json"))
        response["coverage"]=[dict(t,description="Odczyt") for t in bundle["targets"]]
        a.save(output,response)
        with patch.object(a,"run_codex",side_effect=AssertionError("model must not run")):
            a.process(self.repo,jobfile,saved_only=True)
        self.assertEqual(a.load(jobfile)["status"],"done")

    def test_restart_reuses_saved_response(self):
        ident=a.enqueue(self.repo,"baseline",manual=True)
        jobfile=self.repo.state/"jobs"/(ident+".json")
        with patch.object(a,"publish",side_effect=RuntimeError("simulated power interruption")):
            a.work(self.repo)
        job=a.load(jobfile)
        job["status"]="running"
        a.save(jobfile,job)
        with patch.object(a,"run_codex",side_effect=AssertionError("saved response should be reused")):
            a.work(self.repo)
        self.assertEqual(a.load(jobfile)["status"],"done")

    def test_branch_switch_does_not_publish_other_branch(self):
        ident=a.enqueue(self.repo,"baseline",manual=True)
        self.git("checkout","-qb","other")
        a.work(self.repo)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ident+".json"))["status"],"pending")
        self.assertEqual(a.all_reports(self.repo),[])
        self.git("checkout","-q","main")
        a.work(self.repo)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ident+".json"))["status"],"done")

    def test_decisions_persist_but_new_observation_requires_review(self):
        self.baseline()
        findings,_=a.registry_state(self.repo)
        f=findings[0]
        a.main(["--repo",str(self.root),"decide",f["id"],"--status","verified","--note","Sprawdzono na danych syntetycznych."])
        self.assertEqual(a.registry_state(self.repo)[0][0]["status"],"verified")
        (self.root/"backend/main.py").write_text("def transcribe(audio):\n    save_audio(audio)\n    print('changed')\n")
        self.commit("changed flow")
        a.enqueue(self.repo,"review",manual=True)
        a.work(self.repo)
        f=a.registry_state(self.repo)[0][0]
        self.assertEqual(f["status"],"review_again")
        self.assertIn("syntetycznych",f["decision"]["note"])

    def test_symlink_output_is_rejected(self):
        other=Path(self.tmp.name)/"outside"
        other.mkdir()
        self.repo.note("reviews").symlink_to(other,target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.repo.note("reviews/test/report.json")

    def test_no_silent_network_or_law_currency_claim(self):
        with patch.object(a,"fetch",return_value=dict(id="EDPB_BASICS",status="unavailable",attempted_at=a.now(),retrieved_at="",content_sha256="",excerpt="",note="offline")):
            a.refresh_sources(self.repo,force=True)
        ident=a.enqueue(self.repo,"baseline",manual=True)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        cards=a.source_cards(job)
        self.assertEqual(cards[0]["retrieval_status"],"unavailable")
        self.assertIn("Nie potwierdza",cards[0]["currency"])

    def test_lock_prevents_duplicate_model_runs(self):
        a.enqueue(self.repo,"baseline",manual=True)
        with self.repo.lock("worker"):
            with patch.object(a,"run_codex",side_effect=AssertionError("locked")):
                a.work(self.repo)
        self.assertEqual(a.all_reports(self.repo),[])

    def test_html_escapes_untrusted_content(self):
        demo=a.load(HERE/"demo.json")
        demo["findings"][0]["title"]='<script>alert(1)</script>'
        result=view.render(**demo,signature="demo",demo=True)
        self.assertNotIn("<script>",result)
        self.assertIn("&lt;script&gt;",result)
        self.assertIn("Content-Security-Policy",result)
        self.assertIn('<svg role="img"',result)
        self.assertEqual(view.safe_url("javascript:alert(1)"),"#")

    def test_public_sources_restrict_hosts_and_keep_registry_valid(self):
        sources.validate_registry(a.load(self.repo.note("SOURCES.json")))
        for url in ("http://uodo.gov.pl", "https://uodo.gov.pl.evil.example/", "https://localhost/", "https://user:pass@uodo.gov.pl/"):
            self.assertFalse(sources.allowed_url(url))
        self.assertTrue(sources.allowed_url("https://uodo.gov.pl/pl/598/3617"))

    def test_mcp_listing_failure_stops_analysis(self):
        with patch.object(a.subprocess,"run",return_value=subprocess.CompletedProcess([],1,b"",b"failed")):
            with self.assertRaises(RuntimeError):
                a.codex_options(self.repo,self.repo.cfg())

    def test_large_changed_files_are_split_without_losing_coverage(self):
        for name in ("a", "b", "c"):
            (self.root/f"backend/{name}.py").write_text("# synthetic fixture\n"*3500)
        self.commit("large source files")
        cfg=self.repo.cfg()
        cfg.update(files_per_part=3,max_input_bytes=120000)
        a.save(self.repo.config_path,cfg)
        ident=a.enqueue(self.repo,"baseline",manual=True)
        a.work(self.repo)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        self.assertEqual(job["status"],"done")
        self.assertGreater(len(job["part_targets"]),2)
        expected={(t["version"],t["path"]) for t in job["targets"]}
        actual={(t["version"],t["path"]) for group in job["part_targets"] for t in group}
        self.assertEqual(actual,expected)
        findings,_=a.registry_state(self.repo)
        self.assertEqual(len(findings),1)
        self.assertGreater(len(findings[0]["evidence"]),1)

    def test_pull_after_offline_period_queues_all_new_first_parent_commits(self):
        self.commit("agent files")
        clone=Path(self.tmp.name)/"laptop"
        subprocess.run(["git","clone","-q",str(self.root),str(clone)],check=True)
        laptop=a.Repo(clone)
        a.install(laptop)
        expected=[]
        for i in range(2):
            (self.root/"backend/main.py").write_text(f"def change{i}():\n    pass\n")
            expected.append(self.commit("desktop change"))
        subprocess.run(["git","-C",str(clone),"pull","--ff-only"],check=True,capture_output=True)
        ids=a.scan(laptop)
        commits=[a.load(laptop.state/"jobs"/(i+".json"))["commit"] for i in ids]
        self.assertEqual(commits,expected)

    def test_pause_prevents_model_and_force_creates_new_manual_task(self):
        ident=a.enqueue(self.repo,"baseline",manual=True)
        cfg=self.repo.cfg()
        cfg["enabled"]=False
        a.save(self.repo.config_path,cfg)
        with patch.object(a,"run_codex",side_effect=AssertionError("paused")):
            a.work(self.repo)
        self.assertEqual(a.load(self.repo.state/"jobs"/(ident+".json"))["status"],"pending")
        cfg["enabled"]=True
        a.save(self.repo.config_path,cfg)
        forced=a.enqueue(self.repo,"baseline",manual=True,force=True)
        self.assertNotEqual(forced,ident)

    def test_source_fetch_does_not_treat_robot_page_as_verified(self):
        source=a.load(self.repo.note("SOURCES.json"))["sources"][0]
        class Response:
            url=source["url"]
            def __init__(self):
                from email.message import Message
                self.headers=Message()
                self.headers['Content-Type']='text/html; charset=utf-8'
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b"<html>verify that you're not a robot"+b"."*600+b"</html>"
        opener=unittest.mock.Mock()
        opener.open.return_value=Response()
        with patch.object(sources.urllib.request,"build_opener",return_value=opener):
            result=sources.fetch(source)
        self.assertEqual(result["status"],"unavailable")
        self.assertEqual(result["retrieved_at"],"")

    def test_report_keeps_file_hashes_and_omissions(self):
        ident=self.baseline()
        report=a.load(self.repo.note("reviews/"+ident+"/report.json"))
        self.assertTrue(report["manifests"])
        source=next(x for x in report["manifests"][0]["files"] if x["path"]=="backend/main.py")
        self.assertEqual(len(source["sha256"]),64)
        self.assertNotIn("text",source)
        self.assertIn("Zakres przygotowanych migawek",self.repo.note("reviews/"+ident+"/report.md").read_text())

    def test_observed_change_to_old_finding_requires_new_author_decision(self):
        self.baseline()
        f=a.registry_state(self.repo)[0][0]
        a.main(["--repo",str(self.root),"decide",f["id"],"--status","verified","--note","Dowód poprzedniej obserwacji."])
        (self.root/"backend/main.py").write_text("def transcribe(audio):\n    delete_audio(audio)\n")
        self.commit("cleanup")
        ident=a.enqueue(self.repo,"review",manual=True)
        original=a.run_codex
        def changed(repo,bundle,path):
            response=original(repo,bundle,path)
            e=response["findings"][0]["evidence"]
            response["findings"]=[]
            response["previous_findings"]=[dict(key="speech-audio-retention",assessment="change_observed",
                explanation="W nowej migawce zmienił się sposób obsługi audio; działanie nie jest sprawdzone.",evidence=e)]
            a.save(path,response)
            return response
        with patch.object(a,"run_codex",side_effect=changed):
            a.work(self.repo)
        self.assertEqual(a.registry_state(self.repo)[0][0]["status"],"review_again")
        a.main(["--repo",str(self.root),"decide",f["id"],"--status","verified","--note","Dowód po zmianie."])
        self.assertEqual(a.registry_state(self.repo)[0][0]["status"],"verified")

    def big_scene(self):
        scene=self.root/"Assets/Scenes/CanvasModes_XREAL.unity"
        scene.parent.mkdir(parents=True,exist_ok=True)
        text="%YAML 1.1\n"+"\n".join(f"  m_Name: Synthetic object {i:05d} for legal agent size regression fixture" for i in range(4200))+"\n"
        scene.write_text(text)
        self.assertGreater(scene.stat().st_size,self.repo.cfg()["max_blob_bytes"])
        self.commit("large Unity scene")
        return scene,text

    def test_unity_scene_over_blob_limit_is_processed_in_complete_line_windows(self):
        scene,text=self.big_scene()
        ident=a.enqueue(self.repo,"baseline",manual=True)
        a.work(self.repo)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        self.assertEqual(job["status"],"done",job["error"])
        windows=[t for group in job["part_targets"] for t in group if t["path"]=="Assets/Scenes/CanvasModes_XREAL.unity"]
        self.assertGreater(len(windows),1)
        self.assertEqual(windows[0]["first_line"],1)
        for previous,current in zip(windows,windows[1:]):
            self.assertEqual(previous["last_line"]+1,current["first_line"])
        self.assertEqual(windows[-1]["last_line"],len(text.splitlines()))
        fragments=[]
        for path in sorted((self.repo.state/"inputs").glob(ident+"-p*.json")):
            bundle=a.load(path)
            for f in bundle["files"]:
                if f["path"]=="Assets/Scenes/CanvasModes_XREAL.unity" and "first_line" in f:
                    fragments.append(f)
        self.assertEqual("\n".join(f["text"] for f in fragments),a.redact(text)[0])
        self.assertEqual({f["sha256"] for f in fragments},{a.digest(text.encode())})
        self.assertTrue(all(len(json.dumps(f).encode())<self.repo.cfg()["max_blob_bytes"] for f in fragments))
        report=a.load(self.repo.note("reviews/"+ident+"/report.json"))
        self.assertTrue(any("oryginalne linie" in p["scope_note"] for p in report["parts"]))

    def test_window_evidence_uses_original_line_numbers_and_rejects_local_numbers(self):
        self.big_scene()
        ident=a.enqueue(self.repo,"review",files=["Assets/Scenes/CanvasModes_XREAL.unity"],manual=True)
        a.work(self.repo)
        inputs=sorted((self.repo.state/"inputs").glob(ident+"-p*.json"))
        second=inputs[1]
        bundle=a.load(second)
        response=a.load(self.repo.state/"results"/second.name)
        schema.validate(response,bundle)
        evidence=response["findings"][0]["evidence"][0]
        self.assertGreater(evidence["first_line"],1)
        evidence.update(first_line=1,last_line=1)
        with self.assertRaises(ValueError):schema.validate(response,bundle)

    def test_old_size_failure_is_recoverable_without_changing_config_or_job_id(self):
        self.big_scene()
        ident=a.enqueue(self.repo,"baseline",manual=True)
        path=self.repo.state/"jobs"/(ident+".json")
        job=a.load(path)
        job.update(status="failed",error="Wybrany plik przekracza max_blob_bytes: Assets/Scenes/CanvasModes_XREAL.unity")
        a.save(path,job)
        config=self.repo.config_path.read_bytes()
        job.update(status="pending",error="")
        a.save(path,job)
        a.work(self.repo)
        self.assertEqual(a.load(path)["status"],"done")
        self.assertEqual(a.load(path)["id"],ident)
        self.assertEqual(self.repo.config_path.read_bytes(),config)

    def test_large_deleted_scene_is_split_from_before_commit(self):
        scene,text=self.big_scene()
        scene.unlink()
        self.commit("remove large scene")
        ident=a.enqueue(self.repo,"review",manual=True)
        a.work(self.repo)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        self.assertEqual(job["status"],"done",job["error"])
        self.assertTrue(all(t["version"]=="before" for group in job["part_targets"] for t in group))

    def test_resume_reuses_large_scene_responses_after_interruption(self):
        self.big_scene()
        ident=a.enqueue(self.repo,"baseline",manual=True)
        path=self.repo.state/"jobs"/(ident+".json")
        with patch.object(a,"publish",side_effect=RuntimeError("power interruption")):
            a.work(self.repo)
        job=a.load(path)
        self.assertEqual(job["status"],"failed")
        job["status"]="running"
        a.save(path,job)
        with patch.object(a,"run_codex",side_effect=AssertionError("do not repeat completed windows")):
            a.work(self.repo)
        self.assertEqual(a.load(path)["status"],"done")

    def test_saved_shifted_response_recovers_without_model_or_raw_mutation(self):
        ident = self.baseline()
        path = self.repo.state / "jobs" / (ident + ".json")
        output = self.repo.state / "results" / (ident + "-p001.json")
        raw = a.load(output)
        for section in ("findings", "flows"):
            raw[section][0]["evidence"][0].update(first_line=99, last_line=100)
        a.save(output, raw)
        original = output.read_bytes()
        shutil.rmtree(self.repo.note("reviews/" + ident))
        job = a.load(path)
        job.update(status="failed", parts_done=[])
        a.save(path, job)
        with patch.object(a, "run_codex", side_effect=AssertionError("must reuse saved response")):
            a.process(self.repo, path, saved_only=True)
        self.assertEqual(a.load(path)["status"], "done")
        self.assertEqual(output.read_bytes(), original)
        audit = a.load(self.repo.state / "repairs" / output.name)
        self.assertEqual(len(audit["changes"]), 2)
        record = a.load(self.repo.note("reviews/" + ident + "/report.json"))
        self.assertEqual(record["manifests"][0]["line_repairs"], audit)

    def test_single_line_html_uses_a_short_grounded_quote(self):
        (self.root/"page.html").write_text('<html><body>'+('synthetic text '*500)+'</body></html>')
        self.commit("single line HTML")
        ident=a.enqueue(self.repo,"review",files=["page.html"],manual=True)
        a.work(self.repo)
        job=a.load(self.repo.state/"jobs"/(ident+".json"))
        self.assertEqual(job["status"],"done",job["error"])

    def test_retry_new_response_skips_archives_and_keeps_accepted_parts(self):
        ident = self.baseline()
        jobpath = self.repo.state / "jobs" / (ident + ".json")
        job = a.load(jobpath)
        job.update(status="failed", parts_done=[1])
        a.save(jobpath, job)
        folder = self.repo.state / "results"
        accepted = folder / (ident + "-p001.json")
        original = accepted.read_bytes()
        archive = folder / (ident + "-p002.rejected-abcdef12.json")
        archive.write_text("old archive")
        rejected = folder / (ident + "-p002.json")
        rejected.write_text("new rejected response")
        with patch.object(a, "spawn"):
            a.main(["--repo", str(self.root), "retry", ident, "--new-response"])
        self.assertEqual(accepted.read_bytes(), original)
        self.assertEqual(archive.read_text(), "old archive")
        self.assertFalse(rejected.exists())
        self.assertEqual(len(list(folder.glob(ident + "-p002.rejected-*.json"))), 2)

    def test_status_failed_job_does_not_request_new_baseline(self):
        ident = a.enqueue(self.repo, "baseline", manual=True)
        path = self.repo.state / "jobs" / (ident + ".json")
        job = a.load(path)
        job.update(status="failed", error="test")
        a.save(path, job)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            a.main(["--repo", str(self.root), "status"])
        self.assertIn("retry ID", captured.getvalue())
        self.assertNotIn("Wykonaj baseline", captured.getvalue())


class EvidenceLocationTests(unittest.TestCase):
    def fixture(self, text="alpha\nbeta\ngamma", quote="beta", first=9, last=10, offset=1):
        evidence = dict(path="test.cs", version="after", quote=quote, first_line=first, last_line=last)
        report = dict(title="t", summary="s", scope_note="s", coverage=[dict(path="test.cs", version="after", description="d")],
                      assumptions=[], findings=[], previous_findings=[], profile_suggestions=[], next_steps=[], limitations=["l"],
                      flows=[dict(key="test-flow", purpose="p", data="d", origin="o", destination="d", retention="r",
                                  confidence="low", evidence=[evidence], unknowns=[])])
        bundle = dict(files=[dict(path="test.cs", version="after", text=text, first_line=offset)],
                      targets=[dict(path="test.cs", version="after")], legal_sources=[], previous_findings=[])
        return report, bundle

    def test_unique_literal_correction_is_copy_and_preserves_quote(self):
        report, bundle = self.fixture()
        original = copy.deepcopy(report)
        corrected, changes = schema.normalize_evidence_locations(report, bundle)
        schema.validate(corrected, bundle)
        self.assertEqual(report, original)
        self.assertEqual(changes[0]["corrected_lines"], [2, 2])
        self.assertEqual(corrected["flows"][0]["evidence"][0]["quote"], "beta")

    def test_global_chunk_offset(self):
        report, bundle = self.fixture(offset=101, quote="beta\ngamma")
        corrected, changes = schema.normalize_evidence_locations(report, bundle)
        schema.validate(corrected, bundle)
        self.assertEqual(changes[0]["corrected_lines"], [102, 103])

    def test_ambiguous_quote_stays_rejected(self):
        report, bundle = self.fixture(text="beta\nalpha\nbeta")
        corrected, changes = schema.normalize_evidence_locations(report, bundle)
        self.assertFalse(changes)
        with self.assertRaises(ValueError):
            schema.validate(corrected, bundle)

    def test_valid_repeated_quote_keeps_existing_location(self):
        report, bundle = self.fixture(text="beta\nalpha\nbeta", first=3, last=3)
        corrected, changes = schema.normalize_evidence_locations(report, bundle)
        self.assertFalse(changes)
        self.assertEqual(corrected, report)
        schema.validate(corrected, bundle)

    def test_absent_and_whitespace_changed_quotes_stay_rejected(self):
        for quote in ("absent", "alpha beta", "   "):
            report, bundle = self.fixture(quote=quote)
            corrected, changes = schema.normalize_evidence_locations(report, bundle)
            self.assertFalse(changes)
            with self.assertRaises(ValueError):
                schema.validate(corrected, bundle)

    def test_span_and_size_limits_not_bypassed(self):
        for quote in ("\n".join(str(i) for i in range(52)), "x" * 1501):
            report, bundle = self.fixture(text=quote, quote=quote, first=0, last=999)
            corrected, changes = schema.normalize_evidence_locations(report, bundle)
            self.assertFalse(changes)
            with self.assertRaises(ValueError):
                schema.validate(corrected, bundle)

    def test_wrong_source_version_not_relocated(self):
        report, bundle = self.fixture()
        bundle["files"][0]["version"] = "before"
        corrected, changes = schema.normalize_evidence_locations(report, bundle)
        self.assertFalse(changes)
        with self.assertRaises(ValueError):
            schema.validate(corrected, bundle)


if __name__ == "__main__":
    unittest.main()
