"""Local, dependency-free HTML and SVG rendering. Never executes model HTML/JS."""
from html import escape as e
import json
import re
import textwrap


def paras(text):
    return ''.join('<p>' + e(p).replace('\n', '<br>') + '</p>'
                   for p in text.split('\n\n') if p.strip())


def code(text):
    pattern = r'("(?:\\.|[^"\\])*"|\b(?:public|private|class|def|return|async|await|if|else|for|var|new|void|int|string|None|True|False|func|package|import|using|try|catch|throw)\b|\b\d+(?:\.\d+)?\b)'
    parts, pos = [], 0
    for match in re.finditer(pattern, text):
        parts.append(e(text[pos:match.start()]))
        token = match.group()
        cls = 'str' if token.startswith('"') else ('num' if token[0].isdigit() else 'kw')
        parts.append(f'<span class="{cls}">{e(token)}</span>')
        pos = match.end()
    parts.append(e(text[pos:]))
    return '<pre><code>' + ''.join(parts) + '</code></pre>'


def svg_text(x, y, label, width=25):
    lines = textwrap.wrap(label, width=width)[:4] or ['']
    return '<text text-anchor="middle" x="%s" y="%s">%s</text>' % (
        x, y, ''.join(f'<tspan x="{x}" dy="{0 if i == 0 else 17}">{e(line)}</tspan>'
                     for i, line in enumerate(lines)))


def diagram_svg(d):
    nodes, edges = d['nodes'], d['edges']
    positions = {}
    pieces = []
    if d['kind'] == 'sequence':
        width = max(360, len(nodes) * 190)
        height = 130 + len(edges) * 70
        for i, node in enumerate(nodes):
            x = 95 + i * 190
            positions[node['id']] = (x, 40)
            pieces.append(f'<rect x="{x-80}" y="10" width="160" height="64" rx="10"/>')
            pieces.append(svg_text(x, 31, node['label'], 19))
            pieces.append(f'<path class="lifeline" d="M{x},74 V{height-10}"/>')
        for i, edge in enumerate(edges):
            x1 = positions[edge['source']][0]
            x2 = positions[edge['target']][0]
            y = 115 + i * 70
            if x1 == x2:
                pieces.append(f'<path class="arrow" d="M{x1},{y} h45 v24 h-45"/>')
            else:
                pieces.append(f'<path class="arrow" d="M{x1},{y} H{x2}"/>')
            pieces.append(svg_text((x1+x2)/2, y-12, edge['label'], 40))
    else:
        # Longest DAG ranks. Cycles use a bounded grid rather than an endless layout loop.
        rank = {n['id']: 0 for n in nodes}
        acyclic = False
        for _ in range(len(nodes)):
            changed = False
            for edge in edges:
                if edge['source'] != edge['target'] and rank[edge['target']] <= rank[edge['source']]:
                    rank[edge['target']] = rank[edge['source']] + 1
                    changed = True
            if not changed:
                acyclic = True
                break
        if not acyclic:
            rank = {n['id']: i//3 for i, n in enumerate(nodes)}
        rows = {}
        for node in nodes:
            rows.setdefault(rank[node['id']], []).append(node)
        ordered = []
        for key in sorted(rows):
            row = rows[key]
            ordered.extend(row[i:i+3] for i in range(0, len(row), 3))
        width, height = 900, 60 + 170 * len(ordered)
        for row_index, row in enumerate(ordered):
            for col, node in enumerate(row):
                x = width * (col+1)/(len(row)+1)
                y = 65 + row_index * 170
                positions[node['id']] = (x, y)
        for edge in edges:
            x1, y1 = positions[edge['source']]
            x2, y2 = positions[edge['target']]
            start, end = y1+44, y2-44
            if y2 <= y1:
                side = min(width-10, max(x1, x2)+140)
                path = f'M{x1+110},{y1} C{side},{y1+80} {side},{y2-80} {x2+110},{y2}'
                tx, ty = side-25, (y1+y2)/2
            else:
                mid = (start+end)/2
                path = f'M{x1},{start} C{x1},{mid} {x2},{mid} {x2},{end}'
                tx, ty = (x1+x2)/2, mid-8
            pieces.append(f'<path class="arrow" d="{path}"/>')
            pieces.append(svg_text(tx, ty, edge['label'], 23))
        for node in nodes:
            x, y = positions[node['id']]
            pieces.append(f'<rect x="{x-110}" y="{y-44}" width="220" height="88" rx="12"/>')
            pieces.append(svg_text(x, y-14, node['label']))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{e(d['title'], quote=True)}" viewBox="0 0 {width} {height}">
    <defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="#315b8d"/></marker></defs>
    <style>text{{font:14px system-ui;fill:#163553;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}}rect{{fill:#edf6ff;stroke:#8aa9c7;stroke-width:1.5}}.arrow{{fill:none;stroke:#315b8d;stroke-width:2;marker-end:url(#arrow)}}.lifeline{{stroke:#b6c5d5;stroke-dasharray:5 5;fill:none}}</style>
    {''.join(pieces)}</svg>'''


SKILLS = {'explain': 'Wyjaśnij własnymi słowami', 'predict': 'Przewidź działanie',
          'apply': 'Znajdź zastosowanie', 'limits': 'Wskaż ograniczenia',
          'compare': 'Porównaj', 'recall': 'Przypomnij sobie'}
PRACTICE_INTRO = ('Najpierw spróbuj odpowiedzieć z pamięci, bez zaglądania do opisu. '
                  'Odpowiedz na głos lub na kartce. Przy pytaniach wyboru uzasadnij swój wybór '
                  'przed otwarciem rozwiązań. W razie trudności wróć do krótkiego fragmentu i spróbuj ponownie.')
REVIEW_HINT = ('Po porównaniu odpowiedzi nazwij jedną rzecz, którą rozumiesz, i jedną do powtórzenia. '
               'Możesz wrócić do tych pytań jutro, za kilka dni i po tygodniu, '
               'najpierw odpowiadając z pamięci. To propozycja rytmu, bez automatycznego harmonogramu. '
               'Krótka przerwa i późniejsza próba są w porządku.')


def self_test_html(lesson):
    practice = lesson.get('self_test')
    if not practice:
        return ('<section class="self-test"><h2>Sprawdź się</h2><p>Ta starsza lekcja nie zawiera jeszcze '
                'pytań. Możesz uzupełnić ją poleceniem <code>practice '
                + e(lesson['_meta']['lesson_id']) + '</code> zgodnie ze ściągą.</p></section>')
    out = ['<section class="self-test"><h2>Sprawdź się — najpierw bez podglądania</h2>',
           paras(PRACTICE_INTRO)]
    for index, q in enumerate(practice['questions'], 1):
        out.append(f'<section class="question"><h3>{index}. {e(SKILLS[q["skill"]])}</h3>{paras(q["prompt"])}')
        out.append(f'<p class="muted">Źródło: <code>{e(q["source_path"])}</code> · {e(q["symbol"])}</p>')
        if q['code']:
            origin = 'Fragment źródła' if q['code_origin'] == 'source' else 'Przykład pomocniczy — zmieniony lub wymyślony kod'
            out.append(f'<p class="muted">{origin}</p>'+code(q['code']))
        if q['kind'] == 'single_choice':
            group = e(lesson['_meta']['lesson_id']+'-'+q['id'], quote=True)
            out.append('<fieldset><legend>Wybierz jedną odpowiedź</legend>')
            for option in q['options']:
                out.append(f'<label class="option"><input type="radio" name="{group}" value="{e(option["id"], quote=True)}"> '
                           f'<span><strong>{e(option["id"].upper())}.</strong> {e(option["text"])}</span></label>')
            out.append('</fieldset>')
        out.append('</section>')
    out.append('<p class="muted">Zaznaczenia służą bieżącej próbie. Agent nie zapisuje odpowiedzi ani '
               'wyniku testu; nie traktuje otwarcia rozwiązania jako opanowania materiału.</p></section>')
    out.append('<section class="solutions"><h2>Odpowiedzi i wyjaśnienia</h2><p>Otwórz rozwiązanie dopiero po własnej próbie.</p>')
    for index, q in enumerate(practice['questions'], 1):
        answer = q['answer']
        label = 'Przykładowa odpowiedź' if q['kind'] == 'open' else 'Właściwa odpowiedź'
        out.append(f'<details class="solution"><summary>Rozwiązanie pytania {index}</summary>'
                   f'<h3>Pytanie {index}</h3>{paras(q["prompt"])}')
        if q['code']:
            origin = 'Fragment źródła' if q['code_origin'] == 'source' else 'Przykład pomocniczy — zmieniony lub wymyślony kod'
            out.append(f'<p class="muted">{origin}</p>'+code(q['code']))
        out.append(f'<h4>{label}</h4>{paras(answer["text"])}'
                   f'<h4>Dlaczego?</h4>{paras(answer["explanation"])}')
        if q['kind'] == 'open':
            out.append('<p>Nie musisz używać identycznych słów. Porównaj sens odpowiedzi:</p><ul>'
                       + ''.join('<li>'+e(x)+'</li>' for x in answer['checkpoints'])+'</ul>')
        else:
            out.append('<h4>Dlaczego poszczególne warianty pasują lub nie pasują?</h4><ul>')
            for option in q['options']:
                status = 'poprawna' if option['id'] == answer['correct_option_id'] else 'niepoprawna'
                out.append(f'<li><strong>{e(option["text"])}</strong> — odpowiedź {status}. {e(option["explanation"])}</li>')
            out.append('</ul>')
        out.append('</details>')
    out.append('<div class="review"><h3>Wróć do tego później</h3>'+paras(REVIEW_HINT)+'</div></section>')
    return ''.join(out)


def self_test_markdown(lesson):
    if not lesson.get('self_test'):
        return []
    lines = ['', '## Sprawdź się — najpierw bez podglądania', '', PRACTICE_INTRO, '']
    for index, q in enumerate(lesson['self_test']['questions'], 1):
        lines += [f'### Pytanie {index} — {SKILLS[q["skill"]]}', '', q['prompt'], '',
                  f'Źródło: `{q["source_path"]}` — {q["symbol"]}', '']
        if q['code']:
            origin = 'Fragment źródła' if q['code_origin'] == 'source' else 'Przykład pomocniczy — zmieniony lub wymyślony kod'
            lines += [origin, '', '````'+q['code_language'], q['code'], '````', '']
        for option in q['options']:
            lines += [f'- **{option["id"].upper()}.** {option["text"]}']
        lines += ['']
    lines += ['## Odpowiedzi i wyjaśnienia', '', 'Najpierw odpowiedz samodzielnie. Nie każdy czytnik Markdown zwija rozwiązania.', '']
    for index, q in enumerate(lesson['self_test']['questions'], 1):
        answer = q['answer']
        lines += ['<details>', f'<summary>Rozwiązanie pytania {index}</summary>', '',
                  f'### Pytanie {index}', '', q['prompt'], '']
        if q['code']:
            origin = 'Fragment źródła' if q['code_origin'] == 'source' else 'Przykład pomocniczy — zmieniony lub wymyślony kod'
            lines += [origin, '', '````'+q['code_language'], q['code'], '````', '']
        lines += ['**'+('Przykładowa odpowiedź' if q['kind'] == 'open' else 'Właściwa odpowiedź')+':**', '',
                  answer['text'], '', '**Dlaczego?**', '', answer['explanation'], '']
        if q['kind'] == 'open':
            lines += ['Porównaj sens, nie identyczne sformułowania:', '']
            lines += ['- '+x for x in answer['checkpoints']]
        else:
            for option in q['options']:
                status = 'poprawna' if option['id'] == answer['correct_option_id'] else 'niepoprawna'
                lines += [f'- **{option["text"]}** — odpowiedź {status}. {option["explanation"]}']
        lines += ['', '</details>', '']
    lines += ['### Wróć do tego później', '', REVIEW_HINT, '',
              'Ćwiczenie nie zapisuje wyniku i nie potwierdza opanowania materiału.', '']
    return lines


def evidence_label(lesson, path):
    meta = lesson['_meta']
    item = next((x for x in meta.get('evidence_files',[]) if x['path']==path),None)
    if item:
        return {'plan':'Plan / ustalenia', 'implementation':'Implementacja',
                'context':'Dokumentacja kontekstu'}[item['kind']]
    if 'plan_files' in meta:
        return 'Plan / ustalenia' if path in meta['plan_files'] else 'Implementacja / kontekst'
    return 'Źródło — rodzaj nieustalony w starszym zapisie'


def lesson_html(lesson):
    meta = lesson['_meta']
    out = [f'<article id="{e(meta["lesson_id"])}"><header><div class="eyebrow">LEKCJA · {e(meta["commit"][:12])}</div>',
           f'<h1>{e(lesson["title"])}</h1><p class="muted">{e(meta["created_at"])} · {e(meta["branch"])} · analiza statyczna</p></header>',
           paras(lesson['overview'])]
    p = lesson['plan_connection']
    out.append('<section class="plan"><h2>Jak to pasuje do planu aplikacji?</h2>')
    for label, key in [('Cel z planu', 'current_goal'), ('Rola kodu teraz', 'role_now'),
                       ('Co pozostaje do zrobienia', 'next_gap'), ('Niepewności', 'uncertainty')]:
        if p[key]: out.append(f'<h3>{label}</h3>'+paras(p[key]))
    for item in p['evidence']:
        out.append(f'<p class="muted">{e(evidence_label(lesson,item["path"]))}: <code>{e(item["path"])}</code> — {e(item["symbol"])}. {e(item["explanation"])}</p>')
    out.append('</section><h2>Pliki lekcji i kontekst</h2><div class="table"><table class="sources-table"><colgroup><col style="width:25%"><col style="width:50%"><col style="width:25%"></colgroup><tr><th>Plik</th><th>Po co istnieje</th><th>Zakres</th></tr>')
    for src in lesson['sources']:
        context=src['path'] in meta.get('context_file_paths',[])
        scope='Kontekst — zależność' if context else ('Pełny' if src['coverage']=='full' else 'Częściowy')
        out.append(f'<tr><td><code>{e(src["path"])}</code></td><td>{e(src["summary"])}</td><td>{scope}<br>{e(src["remaining"])}</td></tr>')
    out.append('</table></div>')
    for d in lesson['diagrams']:
        out.append(f'<figure><h2>{e(d["title"])}</h2>{diagram_svg(d)}<figcaption>{e(d["explanation"])}</figcaption></figure>')
    if lesson['methods']:
        out.append('<h2>Metody — zwykłymi słowami</h2>')
    for m in lesson['methods']:
        out.append(f'<section><h3><code>{e(m["name"])}</code></h3><p class="muted">{e(m["source_path"])}</p>')
        for label, key in [('Kiedy i kto uruchamia', 'when'), ('Co dostaje', 'input'), ('Co robi', 'does'), ('Co oddaje / zmienia', 'returns')]:
            out.append(f'<p><strong>{label}:</strong> {e(m[key])}</p>')
        out.append('</section>')
    for s in lesson['sections']:
        out.append(f'<section><h2>{e(s["heading"])}</h2><p class="muted">{e(s["source_path"])} · {e(s["symbol"])}</p>{paras(s["explanation"])}')
        if s['code']:out.append(code(s['code']))
        out.append(paras(s['code_explanation'])+'</section>')
    if lesson['new_concepts']:out.append('<h2>Nowe pojęcia — od podstaw</h2>')
    for c in lesson['new_concepts']:
        out.append(f'<section class="concept"><h3>{e(c["title"])}</h3><p class="muted">{e(c["language"])} · {e(c["category"])}</p>{paras(c["meaning"])}<h4>Po co?</h4>{paras(c["why"])}')
        if c['example']:out.append(code(c['example']))
        out.append(paras(c['example_explanation'])+f'<p class="pitfall"><strong>Uwaga na częste nieporozumienie:</strong> {e(c["pitfall"])}</p></section>')
    if lesson['reused_concepts']:out.append('<h2>Krótkie przypomnienia</h2>')
    for c in lesson['reused_concepts']:
        out.append(f'<p><code>{e(c["key"])}</code> — {e(c["reminder"])}</p>')
    out.append('<h2>Następny krok nauki</h2>'+paras(lesson['next_step']))
    if lesson['limitations']:
        out.append('<details open><summary>Ograniczenia analizy</summary><ul>'+''.join('<li>'+e(x)+'</li>' for x in lesson['limitations'])+'</ul></details>')
    out.append(self_test_html(lesson))
    out.append('<p class="muted">Materiał przygotowany automatycznie. Otwarcie strony nie potwierdza przeczytania ani zrozumienia.</p></article>')
    return ''.join(out)


CSS = '''*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#183047;font:17px/1.65 system-ui,sans-serif}main{max-width:1060px;margin:40px auto;padding:0 24px 80px}nav{background:#142c44;color:#fff;padding:22px 5vw}nav a{color:#cce7ff}article{margin-top:30px;background:#fff;padding:42px;border-radius:18px;box-shadow:0 12px 42px #142c4410}h1{font-size:36px;line-height:1.2}h2{margin-top:36px;font-size:25px}h3{margin-bottom:8px}.eyebrow{letter-spacing:.12em;font-size:12px;font-weight:800;color:#287b87}.muted,figcaption{color:#627589;font-size:14px}.plan{border-left:5px solid #287b87;background:#f0f9f8;padding:6px 24px 20px}.concept{background:#f6f8fc;padding:6px 24px 20px;border-radius:12px;margin:20px 0}code{font:14px/1.65 ui-monospace,monospace;overflow-wrap:anywhere}pre{background:#142333;color:#e6edf7;padding:20px;border-radius:12px;overflow:auto}pre code{white-space:pre;overflow-wrap:normal}.kw{color:#b6a3ff}.str{color:#a7dfac}.num{color:#ffc78b}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dce5ef}th{background:#edf3f9}.sources-table{table-layout:fixed}.sources-table th,.sources-table td{overflow-wrap:anywhere}.table{overflow:auto}figure{margin:28px 0;padding:15px;border:1px solid #dce5ef;border-radius:14px}svg{width:100%;height:auto}details{margin-top:25px;padding:15px;background:#fff8e8;border-radius:10px}a{color:#176b9a}.pitfall{border-left:3px solid #daac42;padding-left:14px}.self-test{margin-top:40px;border-top:4px solid #287b87;padding-top:4px}.question{margin:24px 0;padding:4px 20px 16px;background:#f6f8fc;border-radius:12px}fieldset{border:1px solid #dce5ef;border-radius:8px;padding:12px;min-width:0}legend{font-size:14px;padding:0 6px}.option{display:flex;align-items:flex-start;gap:10px;padding:8px;cursor:pointer;overflow-wrap:anywhere}.option input{flex:0 0 auto;margin:7px 0 0}.option:has(input:checked){background:#e0f1f2;border-radius:6px}.solution{background:#f0f9f8}.solution summary{cursor:pointer;font-weight:650}.review{margin-top:24px;padding:4px 20px;background:#f6f8fc;border-radius:12px}@media(max-width:700px){main{padding:0 12px}article{padding:22px}h1{font-size:28px}}'''


def page(lessons):
    menu = ''.join(f'<li><a href="#{e(l["_meta"]["lesson_id"])}">{e(l["title"])} · {e(l["_meta"]["commit"][:10])}</a></li>' for l in lessons)
    csp = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
    return '<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'+f'<meta http-equiv="Content-Security-Policy" content="{e(csp, quote=True)}"><title>Moja nauka kodu</title><style>{CSS}</style><nav><strong>MOJA NAUKA KODU</strong> · lokalny widok · działa bez internetu</nav><main><h1>Biblioteka lekcji</h1><ul>{menu}</ul>'+''.join(lesson_html(l) for l in lessons)+'</main></html>'


def markdown(lesson):
    m = lesson['_meta']
    lines = [f'# {lesson["title"]}', '', f'Commit: `{m["commit"]}` · gałąź: `{m["branch"]}` · {m["created_at"]}',
             '', 'Analiza statyczna. Przygotowano materiał; nie potwierdzono przeczytania ani zrozumienia.', '', lesson['overview'], '', '## Związek z planem aplikacji', '']
    for key, label in [('current_goal', 'Cel'), ('role_now', 'Rola teraz'), ('next_gap', 'Pozostały zakres'), ('uncertainty', 'Niepewności')]:
        lines += [f'**{label}:** {lesson["plan_connection"][key]}', '']
    for ev in lesson['plan_connection']['evidence']:
        lines += [f'{evidence_label(lesson,ev["path"])}: `{ev["path"]}` — {ev["symbol"]}: {ev["explanation"]}', '']
    for s in lesson['sources']:
        context=s['path'] in m.get('context_file_paths',[])
        scope='kontekst — zależność, nie osobna lekcja pliku' if context else s['coverage']
        lines += [f'## {"Kontekst" if context else "Plik"}: `{s["path"]}`', '', s['summary'], '', f'Zakres: {scope}. {s["remaining"]}', '']
    for method in lesson['methods']:
        lines += [f'### Metoda `{method["name"]}`', '', f'Źródło: `{method["source_path"]}`', '']
        for key, label in [('when','Kiedy'),('input','Wejście'),('does','Działanie'),('returns','Wynik/skutki')]:
            lines += [f'**{label}:** {method[key]}', '']
    for s in lesson['sections']:
        lines += [f'## {s["heading"]}', '', f'Źródło: `{s["source_path"]}` — {s["symbol"]}', '', s['explanation'], '']
        if s['code']:lines += ['````'+s['code_language'], s['code'], '````', '']
        lines += [s['code_explanation'], '']
    for c in lesson['new_concepts']:
        lines += [f'## Nowe pojęcie: {c["title"]}', '', f'Klucz: `{c["key"]}`', '', c['meaning'], '', c['why'], '', '````', c['example'], '````', '', c['example_explanation'], '', '**Częste nieporozumienie:** '+c['pitfall'], '']
    for c in lesson['reused_concepts']:lines += [f'Przypomnienie `{c["key"]}`: {c["reminder"]}', '']
    for i, d in enumerate(lesson['diagrams']):
        lines += [f'## {d["title"]}', '', f'![{d["title"]}](diagram-{i+1}.svg)', '', d['explanation'], '']
    lines += ['## Następny krok', '', lesson['next_step'], '', '## Ograniczenia', '']
    lines += ['- '+x for x in lesson['limitations']]
    lines += self_test_markdown(lesson)
    return '\n'.join(lines)+'\n'
