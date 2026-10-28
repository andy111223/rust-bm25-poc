import importlib.util
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

TOOL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOL))
import agent
from schema import validate, validate_self_test
from view import page, markdown


def practice_response(path):
    def question(index, kind, skill, prompt, text, explanation):
        return {'id':f'q{index}', 'kind':kind, 'skill':skill, 'prompt':prompt,
                'source_path':path, 'symbol':'Example', 'code_language':'', 'code':'',
                'code_origin':'none', 'options':[],
                'answer':{'text':text, 'explanation':explanation, 'correct_option_id':'',
                          'checkpoints':['Opis danych.', 'Opis zachowania.']}}
    questions = [
        question(1,'open','explain','Wyjaśnij własnymi słowami rolę klasy.',
                 'Klasa grupuje dane i zachowania.', 'Wspólny opis umożliwia tworzenie obiektów.'),
        question(2,'open','apply','Kiedy przyda się osobna klasa i czego sama nie zrobi?',
                 'Porządkuje dane i metody, ale deklaracja nie uruchamia aplikacji.',
                 'To opis typu, a nie dowód wykonania.'),
        question(3,'single_choice','predict','Czy samo przeczytanie kodu potwierdza działanie aplikacji?',
                 'Nie, do potwierdzenia działania potrzebne jest sprawdzenie uruchomienia.',
                 'Analiza statyczna opisuje kod, a nie wynik jego wykonania.'),
        question(4,'single_choice','compare','Co grupuje klasa?',
                 'Powiązane dane i zachowania.', 'Klasa definiuje wspólny typ.')]
    questions[2]['options'] = [
        {'id':'a','text':'Tak, przeczytanie kodu jest testem aplikacji.','explanation':'Nie uruchomiono aplikacji.'},
        {'id':'b','text':questions[2]['answer']['text'],'explanation':'Źródła pozwalają opisać mechanizm, nie potwierdzić wykonania.'}]
    questions[2]['answer'].update(correct_option_id='b',checkpoints=[])
    questions[3]['options'] = [
        {'id':'a','text':questions[3]['answer']['text'],'explanation':'To cel grupowania w typie.'},
        {'id':'b','text':'Wyłącznie uruchomione okna programu.','explanation':'Klasa nie jest ekranem.'}]
    questions[3]['answer'].update(correct_option_id='a',checkpoints=[])
    return {'questions':questions}


def response(folder):
    m=json.loads((folder/'SOURCE_MANIFEST.json').read_text())
    p=m['lesson_files'][0]['path']
    content=(folder/m['lesson_files'][0]['snapshot_path']).read_text()
    key='csharp.syntax.class'
    known=key in m['known_concept_keys']
    return {'title':'Lekcja <test>', 'overview':'Klasa grupuje dane i zachowania.',
        'plan_connection':{'current_goal':'Plan z pliku' if m['plan_files'] else 'Nieustalony',
          'role_now':'Przykład kodu.', 'next_gap':'Sprawdzić dalsze metody.', 'uncertainty':'Analiza statyczna.',
          'evidence':[{'path':m['plan_files'][0],'symbol':'Cel','explanation':'Zapis w planie.'}] if m['plan_files'] else []},
        'sources':[{'path':x['path'],'summary':'Przykładowa klasa.','coverage':'full','remaining':''} for x in m['lesson_files']],
        'methods':[{'source_path':p,'name':'Run','when':'Nieustalone','input':'Brak','does':'Zwraca wartość','returns':'Liczba'}],
        'sections':[{'heading':'Co oznacza zapis?','explanation':'To fragment źródła.','source_path':p,'symbol':'Example','code_language':'csharp','code':content.strip(),'code_explanation':'Słowo class rozpoczyna klasę.'}],
        'new_concepts':[] if known else [{'key':key,'title':'Klasa','language':'C#','category':'składnia',
             'meaning':'Wspólne miejsce na dane i zachowania.','why':'Porządkuje kod.','example':'class Box {}',
             'example_explanation':'Box to nazwa klasy.','pitfall':'Nie jest pojedynczym obiektem.'}],
        'reused_concepts':[{'key':key,'reminder':'Tutaj też definiujemy klasę.'}] if known else [],
        'diagrams':[{'title':'Przepływ','kind':'flow','nodes':[{'id':'a','label':'Wejście'},{'id':'b','label':'Warunek'},{'id':'c','label':'Wynik'},{'id':'d','label':'Błąd'}],
          'edges':[{'source':'a','target':'b','label':''},{'source':'b','target':'c','label':'tak'},{'source':'b','target':'d','label':'nie'}],'explanation':'Przykład diagramu.'}],
        'next_step':'Przeczytaj kolejną metodę.','limitations':['Nie uruchamiano kodu.'],
        'self_test':practice_response(p)}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='learning test ')
        self.root=Path(self.temp.name)/'repo ze spacją'
        self.root.mkdir()
        for args in [('init','-b','main'),('config','user.email','test@example.invalid'),('config','user.name','Test')]:
            self.g(*args)
        (self.root/'AGENTS.md').write_text('# Zachowaj tę instrukcję\n')
        (self.root/'LEARNING_AGENT.md').write_text('Zasady nauki\n')
        (self.root/'docs').mkdir()
        (self.root/'docs/APP_PLAN.md').write_text('# Plan\nCel: prosty widok.\n')
        (self.root/'Example.cs').write_text('public class Example { public int Run() { return 1; } }\n')
        self.g('add','.');self.g('commit','-qm','start')
        self.repo=agent.Repo(self.root)
        cfg=dict(agent.DEFAULTS);cfg.update(auto_open=False,debounce_seconds=0,max_files_per_lesson=1)
        agent.save(self.repo.config_path,cfg)

    def tearDown(self):self.temp.cleanup()

    def g(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()

    def fake(self,repo,cfg,folder,output):
        value=response(folder);agent.save(output,value);return value

    def execute(self,explicit=None):
        jid=agent.enqueue(self.repo,explicit=explicit)
        with patch.object(agent,'run_codex',side_effect=self.fake):agent.work(self.repo)
        return agent.load(self.repo.state/'jobs'/f'{jid}.json')

    def test_snapshot_reads_committed_code_not_new_edits(self):
        committed=(self.root/'Example.cs').read_bytes()
        (self.root/'Example.cs').write_text('UNCOMMITTED CHANGE\n')
        job=self.execute()
        self.assertEqual(job['status'],'done')
        lesson=agent.lessons(self.repo)[0]
        self.assertEqual(lesson['_meta']['source_files'][0]['sha256'],agent.digest(committed))
        self.assertEqual((self.root/'Example.cs').read_text(),'UNCOMMITTED CHANGE\n')

    def test_code_commit_adds_concept_once_and_later_reuses_it(self):
        self.execute()
        (self.root/'Example.cs').write_text('public class Example { public int Run() { return 2; } }\n')
        self.g('add','Example.cs');self.g('commit','-qm','change')
        self.execute()
        lessons=agent.lessons(self.repo)
        self.assertEqual(sum(len(x['new_concepts']) for x in lessons),1)
        self.assertEqual(sum(len(x['reused_concepts']) for x in lessons),1)
        self.assertTrue((self.repo.notes/'concepts/auto/csharp.syntax.class.md').exists())

    def test_documentation_only_commit_does_not_enqueue(self):
        (self.root/'docs/NOTE.md').write_text('notatka')
        self.g('add','docs');self.g('commit','-qm','docs only')
        self.assertIsNone(agent.enqueue(self.repo))

    def test_removed_file_uses_parent_version_and_records_deletion(self):
        self.g('rm','Example.cs');self.g('commit','-qm','delete')
        job=self.execute()
        self.assertEqual(job['status'],'done')
        self.assertEqual(agent.lessons(self.repo)[0]['_meta']['source_files'][0]['status'],'deleted')

    def test_failure_is_persisted_and_not_retried_by_timer(self):
        jid=agent.enqueue(self.repo)
        with patch.object(agent,'run_codex',side_effect=RuntimeError('no connection')) as call:
            agent.work(self.repo);agent.work(self.repo)
            self.assertEqual(call.call_count,1)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{jid}.json')['status'],'failed')
        self.assertEqual(agent.lessons(self.repo),[])

    def test_running_job_recovers_after_interruption(self):
        jid=agent.enqueue(self.repo)
        p=self.repo.state/'jobs'/f'{jid}.json'
        j=agent.load(p);j['status']='running';agent.save(p,j)
        with patch.object(agent,'run_codex',side_effect=self.fake):agent.work(self.repo)
        self.assertEqual(agent.load(p)['status'],'done')

    def test_branch_switch_during_analysis_prevents_publication(self):
        def switch(repo,cfg,folder,output):
            value=self.fake(repo,cfg,folder,output)
            self.g('switch','-c','other')
            return value
        jid=agent.enqueue(self.repo)
        with patch.object(agent,'run_codex',side_effect=switch):agent.work(self.repo)
        j=agent.load(self.repo.state/'jobs'/f'{jid}.json')
        self.assertEqual(j['status'],'failed')
        self.assertIn('gałąź',j['error'])
        self.assertEqual(agent.lessons(self.repo),[])

    def test_concurrent_manual_memory_change_prevents_overwrite(self):
        self.repo.note_path('concepts').mkdir(parents=True)
        def changed(repo,cfg,folder,output):
            value=self.fake(repo,cfg,folder,output)
            self.repo.note_path('concepts/INDEX.md').write_text('Moje nowsze notatki')
            return value
        jid=agent.enqueue(self.repo)
        with patch.object(agent,'run_codex',side_effect=changed):agent.work(self.repo)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{jid}.json')['status'],'failed')
        self.assertEqual(self.repo.note_path('concepts/INDEX.md').read_text(),'Moje nowsze notatki')

    def test_schema_rejects_invented_code_and_duplicate_concept(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            job={'commit':self.repo.head(),'branch':'main'}
            m=agent.snapshot(self.repo,job,['Example.cs'],folder,self.repo.config())
            value=response(folder)
            value['sections'][0]['code']='INVENTED CODE'
            with self.assertRaises(ValueError):validate(value,m,folder,set())
            value=response(folder)
            with self.assertRaises(ValueError):validate(value,m,folder,{'csharp.syntax.class'})

    def test_browser_content_is_escaped_and_no_remote_scripts(self):
        self.execute()
        lesson=agent.lessons(self.repo)[0]
        lesson['overview']='<script>alert(1)</script>'
        html=page([lesson])
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('<svg',html)
        self.assertNotIn('https://',html)

    def test_symlink_note_target_is_rejected(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        (self.root/'docs/learning').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(RuntimeError):self.repo.note_path('lessons')

    def test_hook_existing_behavior_is_preserved_and_uninstall_restores_it(self):
        hook=self.repo.gitdir/'hooks/post-commit'
        old='#!/usr/bin/env bash\nprintf old-hook >> "$(git rev-parse --git-path original-hook-output)"\n'
        hook.write_text(old);hook.chmod(0o755)
        with patch.object(agent,'HERE',TOOL):agent.install(self.repo,False)
        self.assertIn(agent.MARKER,hook.read_text())
        # Disable model execution while still checking actual post-commit chaining.
        cfg=self.repo.config();cfg['enabled']=False;agent.save(self.repo.config_path,cfg)
        (self.root/'Example.cs').write_text('public class Example {}\n')
        self.g('add','Example.cs');self.g('commit','-qm','hook test')
        self.assertEqual((self.repo.gitdir/'original-hook-output').read_text(),'old-hook')
        with patch('subprocess.run',wraps=subprocess.run) as run:
            agent.uninstall(self.repo)
        self.assertEqual(hook.read_text(),old)
        self.assertIn('Zachowaj tę instrukcję',(self.root/'AGENTS.md').read_text())

    def test_reinstall_does_not_duplicate_instructions_or_erase_manual_notes(self):
        with patch.object(agent,'HERE',TOOL):agent.install(self.repo,False)
        self.repo.note_path('concepts/INDEX.md').write_text('MOJA HISTORIA\n')
        with patch.object(agent,'HERE',TOOL):agent.install(self.repo,False)
        self.assertIn('MOJA HISTORIA',self.repo.note_path('concepts/INDEX.md').read_text())
        self.assertEqual((self.root/'AGENTS.md').read_text().count(agent.BLOCK_START),1)

    def test_all_changed_files_are_split_without_silently_skipping(self):
        (self.root/'Other.cs').write_text('public class Other {}\n')
        self.g('add','Other.cs');self.g('commit','-qm','two changes')
        job=self.execute(explicit=['Example.cs','Other.cs'])
        self.assertEqual(job['parts_done'],[1,2])
        self.assertEqual(len(agent.lessons(self.repo)),2)

    def test_real_subprocess_contract_with_fake_codex_cli(self):
        fake=Path(self.temp.name)/'fake_codex.py'
        fake.write_text('''import sys,json\nfrom pathlib import Path\nsys.path.insert(0,''' +repr(str(Path(__file__).resolve().parent))+''')\nfrom test_agent import response\na=sys.argv\nout=Path(a[a.index('--output-last-message')+1])\nout.write_text(json.dumps(response(Path.cwd()),ensure_ascii=False))\n''')
        cfg=self.repo.config();cfg['codex_command']=[sys.executable,str(fake)];agent.save(self.repo.config_path,cfg)
        jid=agent.enqueue(self.repo)
        agent.work(self.repo)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{jid}.json')['status'],'done')
        self.assertTrue((self.repo.state/'site/index.html').is_file())

    def test_second_worker_does_not_start_duplicate_analysis(self):
        agent.enqueue(self.repo)
        with (self.repo.state/'worker.lock').open('a+') as held:
            agent.fcntl.flock(held,agent.fcntl.LOCK_EX|agent.fcntl.LOCK_NB)
            with patch.object(agent,'run_codex') as call:
                agent.work(self.repo)
                call.assert_not_called()

    def test_two_queued_commits_open_only_once_after_processing(self):
        first=agent.enqueue(self.repo)
        (self.root/'Example.cs').write_text('public class Example { public int Run() { return 3; } }\n')
        self.g('add','Example.cs');self.g('commit','-qm','next commit')
        second=agent.enqueue(self.repo)
        cfg=self.repo.config();cfg['auto_open']=True;agent.save(self.repo.config_path,cfg)
        with patch.object(agent,'run_codex',side_effect=self.fake),patch.object(agent,'open_browser') as browser:
            agent.work(self.repo)
            self.assertEqual(browser.call_count,1)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{first}.json')['status'],'done')
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{second}.json')['status'],'done')

    def test_custom_hooks_path_is_not_overwritten(self):
        before=(self.root/'AGENTS.md').read_bytes()
        self.g('config','core.hooksPath','custom-hooks')
        with self.assertRaises(RuntimeError):agent.install(self.repo,False)
        self.assertEqual((self.root/'AGENTS.md').read_bytes(),before)

    def test_browser_foreground_process_is_not_killed_after_one_second(self):
        cfg=self.repo.config();cfg['browser_command']=['browseros'];agent.save(self.repo.config_path,cfg)
        agent.atomic(self.repo.state/'site/index.html','<html>test</html>')
        process=unittest.mock.Mock()
        process.wait.side_effect=subprocess.TimeoutExpired('browseros',1)
        with patch.dict(os.environ,{'DISPLAY':':test'}),patch.object(agent.subprocess,'Popen',return_value=process):
            agent.open_browser(self.repo)
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def add_dependencies(self):
        for name in ['PresentationController.cs','RagQuestionController.cs','SpeechInputController.cs']:
            (self.root/name).write_text('public class Dependency {}\n')
        self.g('add','*.cs');self.g('commit','-qm','dependencies')

    def contextual_response(self,folder):
        value=response(folder)
        for name in ['PresentationController.cs','RagQuestionController.cs','SpeechInputController.cs']:
            value['sources'].append({'path':name,'summary':'Zależność głównego pliku.','coverage':'partial','remaining':''})
        return value

    def test_target_and_three_real_dependencies_are_valid_context_not_three_extra_lessons(self):
        self.add_dependencies()
        def context(repo,cfg,folder,output):
            value=self.contextual_response(folder);agent.save(output,value);return value
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        with patch.object(agent,'run_codex',side_effect=context):agent.work(self.repo)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{jid}.json')['status'],'done')
        lesson=agent.lessons(self.repo)[0]
        self.assertEqual(lesson['_meta']['lesson_file_paths'],['Example.cs'])
        self.assertEqual(len(lesson['_meta']['context_file_paths']),3)
        self.assertEqual(len(lesson['_meta']['source_files']),4)
        index=self.repo.note_path('files/AUTO_INDEX.md').read_text()
        self.assertIn('Example.cs',index)
        self.assertNotIn('RagQuestionController.cs',index)
        self.assertIn('Kontekst — zależność',(self.repo.state/'site/index.html').read_text())

    def test_recheck_recovers_saved_user_failure_without_model_or_changing_raw_result(self):
        self.add_dependencies()
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        job_path=self.repo.state/'jobs'/f'{jid}.json'
        job=agent.load(job_path);job.update(status='failed',error='Wynik nie obejmuje wszystkich plików tej części');agent.save(job_path,job)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            agent.snapshot(self.repo,job,['Example.cs'],folder,self.repo.config())
            result=self.contextual_response(folder)
            output=self.repo.state/'results'/f'{jid}-p001.json'
            agent.save(output,result)
            before=output.read_bytes()
        with patch.object(agent,'run_codex') as call:
            agent.recheck(self.repo,jid)
            call.assert_not_called()
        self.assertEqual(agent.load(job_path)['status'],'done')
        self.assertEqual(output.read_bytes(),before)
        self.assertEqual(len(agent.lessons(self.repo)),1)

    def test_recheck_without_saved_result_does_not_start_model(self):
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        with patch.object(agent,'run_codex') as call:
            with self.assertRaisesRegex(RuntimeError,'Brak zapisanej odpowiedzi'):agent.recheck(self.repo,jid)
            call.assert_not_called()
        self.assertEqual(agent.lessons(self.repo),[])

    def test_missing_target_has_explicit_error_even_when_context_is_present(self):
        self.add_dependencies()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            manifest=agent.snapshot(self.repo,{'commit':self.repo.head(),'branch':'main'},['Example.cs'],folder,self.repo.config())
            value=self.contextual_response(folder)
            value['sources']=[x for x in value['sources'] if x['path']!='Example.cs']
            with self.assertRaisesRegex(ValueError,'brak wymaganych: Example.cs'):validate(value,manifest,folder,set())

    def test_unavailable_context_and_duplicate_sources_remain_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            manifest=agent.snapshot(self.repo,{'commit':self.repo.head(),'branch':'main'},['Example.cs'],folder,self.repo.config())
            value=response(folder)
            value['sources'].append({'path':'Invented.cs','summary':'Nie istnieje','coverage':'full','remaining':''})
            with self.assertRaisesRegex(ValueError,'pliki spoza migawki: Invented.cs'):validate(value,manifest,folder,set())
            value=response(folder);value['sources'].append(dict(value['sources'][0]))
            with self.assertRaisesRegex(ValueError,'powtórzone ścieżki'):validate(value,manifest,folder,set())

    def test_update_refreshes_runtime_without_reinstalling_or_touching_rules_and_config(self):
        with patch.object(agent,'HERE',TOOL):agent.install(self.repo,False)
        before_agents=(self.root/'AGENTS.md').read_bytes()
        before_config=self.repo.config_path.read_bytes()
        hook=self.repo.gitdir/'hooks/post-commit'
        before_hook=hook.read_bytes()
        (self.repo.state/'runtime/schema.py').write_text('stara wersja')
        agent.update_runtime(self.repo)
        self.assertEqual((self.repo.state/'runtime/schema.py').read_bytes(),(TOOL/'schema.py').read_bytes())
        self.assertEqual((self.root/'AGENTS.md').read_bytes(),before_agents)
        self.assertEqual(self.repo.config_path.read_bytes(),before_config)
        self.assertEqual(hook.read_bytes(),before_hook)

    def test_idle_timer_does_not_sleep_while_holding_worker_lock(self):
        cfg=self.repo.config();cfg['debounce_seconds']=12;agent.save(self.repo.config_path,cfg)
        with patch.object(agent.time,'sleep') as sleep:
            agent.work(self.repo)
            sleep.assert_not_called()

    def legacy_lesson(self):
        job = self.execute()
        lesson = agent.lessons(self.repo)[0]
        del lesson['self_test']
        lesson['_meta'].pop('lesson_format_version',None)
        folder = 'lessons/'+lesson['_meta']['lesson_id']+'/'
        agent.save(self.repo.note_path(folder+'lesson.json'),lesson)
        agent.atomic(self.repo.note_path(folder+'lesson.md'),markdown(lesson))
        return job, lesson

    def fake_practice(self,repo,cfg,folder,output,**kwargs):
        self.assertEqual(kwargs['schema'],agent.PRACTICE_SCHEMA)
        self.assertEqual(kwargs['prompt_name'],'practice-instructions.md')
        prior = agent.load(folder/'PRIOR_LESSON.json')
        value = {'self_test':practice_response(prior['sources'][0]['path'])}
        agent.save(output,value)
        return value

    def test_question_validation_rejects_short_keys_missing_reasons_and_bad_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = agent.snapshot(self.repo,{'commit':self.repo.head(),'branch':'main'},['Example.cs'],folder,self.repo.config())
            mutations = [
                lambda x: x['questions'][2]['answer'].update(text='B'),
                lambda x: x['questions'][2]['answer'].update(correct_option_id='d'),
                lambda x: x['questions'][2]['options'][0].update(explanation=''),
                lambda x: x['questions'][0].update(source_path='Missing.cs'),
                lambda x: x['questions'][1].update(id='q1'),
                lambda x: x['questions'][0]['answer'].update(checkpoints=[]),
                lambda x: x['questions'][0].update(code='INVENTED',code_origin='source',code_language='csharp'),
                lambda x: x['questions'].pop(),
                lambda x: x['questions'][1].update(skill='recall'),
            ]
            for mutate in mutations:
                value = practice_response('Example.cs')
                mutate(value)
                with self.subTest(mutation=mutate),self.assertRaises(ValueError):
                    validate_self_test(value,manifest,folder,{'Example.cs'})
            value = practice_response('Example.cs')
            value['questions'][0].update(code='return 42;',code_origin='hypothetical',code_language='csharp')
            validate_self_test(value,manifest,folder,{'Example.cs'})

    def test_new_output_requires_questions_and_only_old_jobs_can_recheck_without_them(self):
        jid = agent.enqueue(self.repo,explicit=['Example.cs'])
        job_path = self.repo.state/'jobs'/f'{jid}.json'
        job = agent.load(job_path)
        output = self.repo.state/'results'/f'{jid}-p001.json'
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = agent.snapshot(self.repo,job,['Example.cs'],folder,self.repo.config())
            value = response(folder)
            del value['self_test']
            with self.assertRaises(ValueError):validate(value,manifest,folder,set())
            validate(value,manifest,folder,set(),allow_legacy=True)
            agent.save(output,value)
        with patch.object(agent,'run_codex') as call:
            with self.assertRaises(ValueError):agent.recheck(self.repo,jid)
            job = agent.load(job_path);job.pop('lesson_format_version');agent.save(job_path,job)
            agent.recheck(self.repo,jid)
            call.assert_not_called()
        self.assertNotIn('self_test',agent.lessons(self.repo)[0])
        agent.regenerate(self.repo)
        self.assertIn('Ta starsza lekcja',(self.repo.state/'site/index.html').read_text())

    def test_questions_precede_collapsed_solutions_and_answers_repeat_full_question(self):
        self.execute()
        lesson = agent.lessons(self.repo)[0]
        html = page([lesson])
        question_part, solution_part = html.split('<h2>Odpowiedzi i wyjaśnienia</h2>')
        for q in lesson['self_test']['questions']:
            self.assertIn(q['prompt'],question_part)
            self.assertIn(q['prompt'],solution_part)
            self.assertNotIn(q['answer']['explanation'],question_part)
            self.assertIn(q['answer']['text'],solution_part)
            self.assertIn(q['answer']['explanation'],solution_part)
            for option in q['options']:
                self.assertNotIn(option['explanation'],question_part)
                self.assertIn(option['explanation'],solution_part)
        class Details(HTMLParser):
            def __init__(self):super().__init__();self.solutions=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='details' and attrs.get('class')=='solution':self.solutions.append(attrs)
        parser=Details();parser.feed(html)
        self.assertEqual(len(parser.solutions),4)
        self.assertTrue(all('open' not in x for x in parser.solutions))
        self.assertNotIn('<script',html)
        text=markdown(lesson)
        self.assertLess(text.index('Sprawdź się'),text.index('Odpowiedzi i wyjaśnienia'))
        self.assertEqual(text.count(lesson['self_test']['questions'][0]['prompt']),2)

    def test_exercise_markup_escapes_model_content_and_radio_groups_differ_between_lessons(self):
        self.execute()
        one=agent.lessons(self.repo)[0];two=deepcopy(one)
        two['_meta']['lesson_id']='second'
        one['self_test']['questions'][0]['prompt']='<script>alert(1)</script>'
        one['self_test']['questions'][0]['answer']['text']='<img src=x onerror=alert(1)>'
        html=page([one,two])
        self.assertNotIn('<script',html);self.assertNotIn('<img src=x',html)
        self.assertIn('&lt;script&gt;',html);self.assertIn('&lt;img',html)
        self.assertIn('name="second-q3"',html)
        self.assertIn('name="'+one['_meta']['lesson_id']+'-q3"',html)

    def test_hypothetical_question_code_is_labeled_and_repeated_in_solution(self):
        self.execute()
        lesson=agent.lessons(self.repo)[0]
        lesson['self_test']['questions'][0].update(code_origin='hypothetical',code_language='csharp',code='return 42;')
        html=page([lesson])
        questions,answers=html.split('<h2>Odpowiedzi i wyjaśnienia</h2>')
        for part in [questions,answers]:
            self.assertIn('Przykład pomocniczy — zmieniony lub wymyślony kod',part)
            self.assertIn('<span class="num">42</span>',part)
        self.assertEqual(markdown(lesson).count('return 42;'),2)

    def test_practice_preserves_explanation_memory_reading_state_and_uncommitted_code(self):
        job,old=self.legacy_lesson()
        lid=old['_meta']['lesson_id']
        md=self.repo.note_path('lessons/'+lid+'/lesson.md')
        previous=md.read_bytes()+b'\nMOJA UWAGA W STARYM PLIKU\n'
        md.write_bytes(previous)
        cards={p.name:p.read_bytes() for p in self.repo.note_path('concepts/auto').glob('*.md')}
        code='public class Example { public int Run() { return 999; } }\n'
        (self.root/'Example.cs').write_text(code)
        with patch.object(agent,'run_codex',side_effect=self.fake_practice) as call:
            agent.practice(self.repo,job['id'])
            self.assertEqual(call.call_count,1)
        result=agent.lessons(self.repo)[0]
        added=result.pop('self_test');self.assertEqual(len(added['questions']),4)
        result['_meta'].pop('practice_created_at')
        self.assertEqual(result,old)
        self.assertTrue(md.read_bytes().startswith(previous))
        self.assertEqual((self.root/'Example.cs').read_text(),code)
        self.assertEqual(cards,{p.name:p.read_bytes() for p in self.repo.note_path('concepts/auto').glob('*.md')})
        self.assertFalse(result['_meta']['reading_confirmed'])
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{job["id"]}.json'),job)

    def test_practice_recheck_publishes_saved_questions_without_model_or_raw_result_change(self):
        job,old=self.legacy_lesson();lid=old['_meta']['lesson_id']
        output=self.repo.state/'results'/f'{lid}-practice.json'
        agent.save(output,{'self_test':practice_response('Example.cs')})
        before=output.read_bytes()
        with patch.object(agent,'run_codex') as call:
            agent.practice(self.repo,lid,saved_only=True)
            call.assert_not_called()
        self.assertEqual(output.read_bytes(),before)
        self.assertIn('self_test',agent.lessons(self.repo)[0])

    def test_practice_bad_result_does_not_change_lesson_or_concept_history(self):
        job,old=self.legacy_lesson();before=agent.memory_signature(self.repo)
        def bad(*args,**kwargs):
            result=self.fake_practice(*args,**kwargs)
            result['self_test']['questions'][2]['answer']['text']='B'
            return result
        with patch.object(agent,'run_codex',side_effect=bad):
            with self.assertRaisesRegex(ValueError,'pełną treść'):agent.practice(self.repo,job['id'])
        self.assertEqual(agent.memory_signature(self.repo),before)
        self.assertEqual(agent.lessons(self.repo)[0],old)

    def test_practice_manual_change_during_generation_is_preserved(self):
        job,old=self.legacy_lesson()
        note=self.repo.note_path('lessons/'+old['_meta']['lesson_id']+'/lesson.md')
        def changed(*args,**kwargs):
            result=self.fake_practice(*args,**kwargs)
            note.write_text('Nowsza ręczna uwaga')
            return result
        with patch.object(agent,'run_codex',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'Notatki zmieniły'):agent.practice(self.repo,job['id'])
        self.assertEqual(note.read_text(),'Nowsza ręczna uwaga')
        self.assertNotIn('self_test',agent.lessons(self.repo)[0])

    def test_practice_branch_change_prevents_publication(self):
        job,old=self.legacy_lesson()
        def switched(*args,**kwargs):
            result=self.fake_practice(*args,**kwargs);self.g('switch','-c','other');return result
        with patch.object(agent,'run_codex',side_effect=switched):
            with self.assertRaisesRegex(RuntimeError,'gałąź'):agent.practice(self.repo,job['id'])
        self.assertEqual(agent.lessons(self.repo)[0],old)

    def test_practice_with_existing_questions_or_missing_saved_result_does_not_call_model(self):
        job=self.execute()
        with patch.object(agent,'run_codex') as call:
            agent.practice(self.repo,job['id'])
            call.assert_not_called()
        path=self.repo.note_path('lessons/'+job['id']+'-p001/lesson.json')
        value=agent.load(path);del value['self_test'];agent.save(path,value)
        with patch.object(agent,'run_codex') as call:
            with self.assertRaisesRegex(RuntimeError,'Brak zachowanych ćwiczeń'):
                agent.practice(self.repo,job['id'],saved_only=True)
            call.assert_not_called()

    def test_practice_works_after_pull_without_local_job_and_uses_original_commit(self):
        job,old=self.legacy_lesson()
        (self.repo.state/'jobs'/f'{job["id"]}.json').unlink()
        (self.root/'Example.cs').write_text('public class Example { public int Run() { return 77; } }\n')
        self.g('add','Example.cs');self.g('commit','-qm','later version')
        def check_snapshot(repo,cfg,folder,output,**kwargs):
            self.assertIn('return 1;', (folder/'Example.cs').read_text())
            self.assertNotIn('return 77;', (folder/'Example.cs').read_text())
            return self.fake_practice(repo,cfg,folder,output,**kwargs)
        with patch.object(agent,'run_codex',side_effect=check_snapshot):agent.practice(self.repo,job['id'])
        self.assertEqual(agent.lessons(self.repo)[0]['_meta']['commit'],old['_meta']['commit'])

    def test_practice_real_subprocess_receives_small_schema_and_old_lesson(self):
        job,old=self.legacy_lesson()
        fake=Path(self.temp.name)/'practice_cli.py'
        fake.write_text('''import sys,json
from pathlib import Path
sys.path.insert(0,'''+repr(str(Path(__file__).resolve().parent))+''')
from test_agent import practice_response
schema=json.loads(Path(sys.argv[sys.argv.index('--output-schema')+1]).read_text())
assert set(schema['properties'])=={'self_test'}
prior=json.loads(Path('PRIOR_LESSON.json').read_text())
assert 'self_test' not in prior
assert 'PRIOR_LESSON.json' in sys.stdin.read()
out=Path(sys.argv[sys.argv.index('--output-last-message')+1])
out.write_text(json.dumps({'self_test':practice_response(prior['sources'][0]['path'])},ensure_ascii=False))
''')
        cfg=self.repo.config();cfg['codex_command']=[sys.executable,str(fake)];agent.save(self.repo.config_path,cfg)
        agent.main(['--repo',str(self.root),'practice',job['id']])
        self.assertIn('self_test',agent.lessons(self.repo)[0])

    def test_demo_shows_questions_without_changing_history_or_calling_model(self):
        before=agent.memory_signature(self.repo)
        with patch.object(agent,'run_codex') as call,patch.object(agent,'open_browser'):
            agent.demo(self.repo)
            call.assert_not_called()
        self.assertEqual(agent.memory_signature(self.repo),before)
        html=(self.repo.state/'site/index.html').read_text()
        self.assertIn('Odpowiedzi i wyjaśnienia',html)
        self.assertEqual(html.count('class="solution"'),5)

    def add_user_evidence_files(self):
        files={
            'docs/DECISIONS.md':'# D-004\nHTTP pobiera dane; WebSocket sygnalizuje zmianę.\n',
            'docs/PROJECT_STATUS.md':'# Implementacja i weryfikacja\n## Plany i zadania\n',
            'Assets/Scripts/Presentation/PresentationController.cs':'public class PresentationController { public void Update() {} }\n',
            'backend/main.py':'class ConnectionManager:\n    def broadcast_active_changed(self):\n        return "active_presentation_changed:"\n',
        }
        for name,content in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        self.g('add','.');self.g('commit','-qm','mixed reference sources')

    def user_evidence_response(self,folder):
        value=response(folder)
        value['plan_connection']['evidence']=[
            {'path':'docs/DECISIONS.md','symbol':'D-004','explanation':'Podział odpowiedzialności HTTP i WebSocket.'},
            {'path':'docs/PROJECT_STATUS.md','symbol':'Implementacja i weryfikacja','explanation':'Oddziela kod od weryfikacji.'},
            {'path':'docs/PROJECT_STATUS.md','symbol':'Plany i zadania','explanation':'Nie wskazuje następnego zadania.'},
            {'path':'Assets/Scripts/Presentation/PresentationController.cs','symbol':'PresentationController.Update','explanation':'Kod odświeżania widoku.'},
            {'path':'backend/main.py','symbol':'ConnectionManager.broadcast_active_changed','explanation':'Implementacja komunikatu.'},
        ]
        return value

    def test_user_mixed_plan_and_code_references_are_labeled_without_expanding_lesson_coverage(self):
        self.add_user_evidence_files()
        def mixed(repo,cfg,folder,output):
            value=self.user_evidence_response(folder);agent.save(output,value);return value
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        with patch.object(agent,'run_codex',side_effect=mixed):agent.work(self.repo)
        self.assertEqual(agent.load(self.repo.state/'jobs'/f'{jid}.json')['status'],'done')
        lesson=agent.lessons(self.repo)[0]
        evidence={x['path']:x for x in lesson['_meta']['evidence_files']}
        self.assertEqual(evidence['docs/DECISIONS.md']['kind'],'plan')
        self.assertEqual(evidence['backend/main.py']['kind'],'implementation')
        self.assertTrue(evidence['backend/main.py']['sha256'])
        html=page([lesson]);md=markdown(lesson)
        self.assertIn('Plan / ustalenia: <code>docs/DECISIONS.md',html)
        self.assertIn('Implementacja: <code>backend/main.py',html)
        self.assertIn('Implementacja: `backend/main.py`',md)
        self.assertNotIn('backend/main.py',self.repo.note_path('files/AUTO_INDEX.md').read_text())

    def test_reference_to_missing_or_size_omitted_file_remains_rejected(self):
        large=self.root/'Omitted.py';large.write_text('x'*350001)
        self.g('add','Omitted.py');self.g('commit','-qm','large context')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            manifest=agent.snapshot(self.repo,{'commit':self.repo.head(),'branch':'main'},['Example.cs'],folder,self.repo.config())
            self.assertTrue(any('Omitted.py' in x for x in manifest['omitted']))
            for name in ['DoesNotExist.py','Omitted.py']:
                value=response(folder)
                value['plan_connection']['evidence'].append({'path':name,'symbol':'Anything','explanation':'Niedostępne.'})
                with self.subTest(path=name),self.assertRaisesRegex(ValueError,'spoza migawki: '+name):
                    validate(value,manifest,folder,set())

    def test_recheck_user_mixed_reference_result_does_not_call_model_or_edit_raw_answer(self):
        self.add_user_evidence_files()
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        job_path=self.repo.state/'jobs'/f'{jid}.json';job=agent.load(job_path)
        job.update(status='failed',error='Źródło planu nie jest jednym z dostępnych dokumentów planowania');agent.save(job_path,job)
        output=self.repo.state/'results'/f'{jid}-p001.json'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);agent.snapshot(self.repo,job,['Example.cs'],folder,self.repo.config())
            agent.save(output,self.user_evidence_response(folder))
        before=output.read_bytes()
        with patch.object(agent,'run_codex') as call:
            agent.recheck(self.repo,jid);call.assert_not_called()
        self.assertEqual(output.read_bytes(),before)
        self.assertEqual(agent.load(job_path)['status'],'done')
        self.assertEqual(len(agent.lessons(self.repo)[0]['_meta']['evidence_files']),4)

    def test_recheck_reuses_concept_published_by_later_lesson_without_redefining_or_editing_raw_answer(self):
        jid=agent.enqueue(self.repo,explicit=['Example.cs'])
        job_path=self.repo.state/'jobs'/f'{jid}.json';job=agent.load(job_path)
        output=self.repo.state/'results'/f'{jid}-p001.json'
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);agent.snapshot(self.repo,job,['Example.cs'],folder,self.repo.config())
            agent.save(output,response(folder))
        job.update(status='failed',error='Poprzednia kontrola źródeł');agent.save(job_path,job)
        before=output.read_bytes()
        (self.root/'Other.cs').write_text('public class Other {}\n')
        self.g('add','Other.cs');self.g('commit','-qm','later lesson')
        self.execute(explicit=['Other.cs'])
        card=self.repo.note_path('concepts/auto/csharp.syntax.class.md')
        before_card=card.read_bytes()
        with patch.object(agent,'run_codex') as call:
            agent.recheck(self.repo,jid);call.assert_not_called()
        lesson=next(x for x in agent.lessons(self.repo) if x['_meta']['lesson_id']==jid+'-p001')
        self.assertEqual(lesson['new_concepts'],[])
        self.assertEqual(lesson['reused_concepts'][0]['key'],'csharp.syntax.class')
        self.assertEqual(lesson['_meta']['reused_after_recheck'],['csharp.syntax.class'])
        self.assertEqual(card.read_bytes(),before_card)
        self.assertEqual(output.read_bytes(),before)
        self.assertEqual(sum(len(x['new_concepts']) for x in agent.lessons(self.repo)),1)
        self.assertEqual(agent.load(job_path)['status'],'done')

    def test_saved_recheck_still_rejects_duplicate_or_malformed_new_concept_definitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            manifest=agent.snapshot(self.repo,{'commit':self.repo.head(),'branch':'main'},['Example.cs'],folder,self.repo.config())
            value=response(folder);value['new_concepts'].append(deepcopy(value['new_concepts'][0]))
            with self.assertRaisesRegex(ValueError,'zduplikowany klucz'):
                validate(value,manifest,folder,{'csharp.syntax.class'},allow_known_new=True)
            value=response(folder);value['sections'][0]['code']='Invented source quote'
            with self.assertRaisesRegex(ValueError,'dokładnym fragmentem'):
                validate(value,manifest,folder,{'csharp.syntax.class'},allow_known_new=True)


if __name__=='__main__':unittest.main()
