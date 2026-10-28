"""JSON Schema and strict dependency-free validation for a generated lesson."""
import re


def obj(**fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields),
            'additionalProperties': False}


S = {'type': 'string'}
def arr(item):
    return {'type': 'array', 'items': item}


LEGACY_SCHEMA = obj(
    title=S, overview=S,
    plan_connection=obj(current_goal=S, role_now=S, next_gap=S, uncertainty=S,
                        evidence=arr(obj(path=S, symbol=S, explanation=S))),
    sources=arr(obj(path=S, summary=S, coverage={'type': 'string', 'enum': ['full', 'partial']}, remaining=S)),
    methods=arr(obj(source_path=S, name=S, when=S, input=S, does=S, returns=S)),
    sections=arr(obj(heading=S, explanation=S, source_path=S, symbol=S,
                     code_language=S, code=S, code_explanation=S)),
    new_concepts=arr(obj(key=S, title=S, language=S, category=S, meaning=S,
                         why=S, example=S, example_explanation=S, pitfall=S)),
    reused_concepts=arr(obj(key=S, reminder=S)),
    diagrams=arr(obj(title=S, kind={'type': 'string', 'enum': ['flow', 'sequence']},
                     nodes=arr(obj(id=S, label=S)),
                     edges=arr(obj(source=S, target=S, label=S)), explanation=S)),
    next_step=S, limitations=arr(S),
)

SELF_TEST_SCHEMA = obj(questions=arr(obj(
    id=S,
    kind={'type': 'string', 'enum': ['open', 'single_choice']},
    skill={'type': 'string', 'enum': ['explain', 'predict', 'apply', 'limits', 'compare', 'recall']},
    prompt=S, source_path=S, symbol=S, code_language=S, code=S,
    code_origin={'type': 'string', 'enum': ['none', 'source', 'hypothetical']},
    options=arr(obj(id=S, text=S, explanation=S)),
    answer=obj(text=S, explanation=S, correct_option_id=S, checkpoints=arr(S)),
)))
PRACTICE_SCHEMA = obj(self_test=SELF_TEST_SCHEMA)
SCHEMA = obj(**LEGACY_SCHEMA['properties'], self_test=SELF_TEST_SCHEMA)


def check_schema(value, schema=SCHEMA, where='lesson'):
    typ = schema['type']
    if typ == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError(f'{where}: niepoprawne pola obiektu')
        for key, sub in schema['properties'].items():
            check_schema(value[key], sub, f'{where}.{key}')
    elif typ == 'array':
        if not isinstance(value, list) or len(value) > 200:
            raise ValueError(f'{where}: niepoprawna lista')
        for index, child in enumerate(value):
            check_schema(child, schema['items'], f'{where}[{index}]')
    elif not isinstance(value, str) or len(value) > 40000:
        raise ValueError(f'{where}: niepoprawny tekst')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{where}: niedopuszczalna wartość')


def validate_self_test(self_test, manifest, snapshot, reported_paths):
    check_schema(self_test, SELF_TEST_SCHEMA, 'self_test')
    questions = self_test['questions']
    if not 4 <= len(questions) <= 6:
        raise ValueError('Sprawdzenie wiedzy musi zawierać 4–6 pytań')
    kinds = [q['kind'] for q in questions]
    if kinds.count('open') < 2 or kinds.count('single_choice') < 1:
        raise ValueError('Potrzebne są co najmniej dwa pytania otwarte i jedno pytanie wyboru')
    open_skills = {q['skill'] for q in questions if q['kind'] == 'open'}
    if 'explain' not in open_skills or not open_skills.intersection({'apply', 'limits'}):
        raise ValueError('Pytania otwarte muszą obejmować wyjaśnienie i zastosowanie lub ograniczenia')
    paths = {x['path']: x for x in manifest['snapshot_files']}
    for index, q in enumerate(questions, 1):
        if q['id'] != f'q{index}' or not q['prompt'].strip() or not q['symbol'].strip():
            raise ValueError('Niepoprawny numer lub pusta treść pytania')
        if q['source_path'] not in reported_paths or q['source_path'] not in paths:
            raise ValueError('Pytanie wskazuje plik spoza zakresu lekcji')
        if q['code_origin'] == 'none':
            if q['code'] or q['code_language']:
                raise ValueError('Pytanie bez kodu musi mieć puste code i code_language')
        elif not q['code'].strip() or not q['code_language'].strip():
            raise ValueError('Pytanie z kodem nie podaje fragmentu lub języka')
        elif q['code_origin'] == 'source':
            file = snapshot / paths[q['source_path']]['snapshot_path']
            if q['code'] not in file.read_text(encoding='utf-8'):
                raise ValueError('Cytat w pytaniu nie jest dokładnym fragmentem źródła')
        answer = q['answer']
        if not answer['text'].strip() or not answer['explanation'].strip():
            raise ValueError('Brak pełnej odpowiedzi lub uzasadnienia')
        if q['kind'] == 'open':
            if q['options'] or answer['correct_option_id']:
                raise ValueError('Pytanie otwarte nie może mieć wariantów wyboru')
            if not 2 <= len(answer['checkpoints']) <= 4 or any(not x.strip() for x in answer['checkpoints']):
                raise ValueError('Pytanie otwarte wymaga 2–4 punktów do samodzielnego porównania')
        else:
            options = q['options']
            ids = [x['id'] for x in options]
            texts = [x['text'].strip() for x in options]
            if not 2 <= len(options) <= 4 or len(ids) != len(set(ids)) or len(texts) != len(set(texts)):
                raise ValueError('Niepoprawne lub powtórzone warianty odpowiedzi')
            if any(not re.fullmatch(r'[a-d]', x) for x in ids):
                raise ValueError('Identyfikatory wariantów muszą należeć do a–d')
            if any(not x['text'].strip() or not x['explanation'].strip() for x in options):
                raise ValueError('Każdy wariant wymaga treści i uzasadnienia w rozwiązaniu')
            selected = next((x for x in options if x['id'] == answer['correct_option_id']), None)
            if selected is None or answer['text'].strip() != selected['text'].strip():
                raise ValueError('Odpowiedź musi powtarzać pełną treść właściwego wariantu')
            if answer['checkpoints']:
                raise ValueError('Pytanie wyboru nie używa punktów oceny odpowiedzi otwartej')


def validate(lesson, manifest, snapshot, known, allow_legacy=False, allow_known_new=False):
    legacy = allow_legacy and 'self_test' not in lesson
    check_schema(lesson, LEGACY_SCHEMA if legacy else SCHEMA)
    if not lesson['title'].strip() or not lesson['overview'].strip():
        raise ValueError('Brak tytułu lub wprowadzenia')
    paths = {x['path']: x for x in manifest['snapshot_files']}
    expected = {x['path'] for x in manifest['lesson_files']}
    reported = [x['path'] for x in lesson['sources']]
    actual = set(reported)
    missing = sorted(expected - actual)
    unknown = sorted(actual - set(paths))
    if len(reported) != len(actual):
        raise ValueError('Lista sources zawiera powtórzone ścieżki plików')
    if missing or unknown:
        details = []
        if missing: details.append('brak wymaganych: '+', '.join(missing))
        if unknown: details.append('pliki spoza migawki: '+', '.join(unknown))
        raise ValueError('Niepoprawny zakres sources — '+'; '.join(details))
    # Extra source entries are valid context if they exist in this exact snapshot.
    # They must not count as fully explained target files in the learning index.
    for source in lesson['sources']:
        if source['path'] in expected and source['coverage'] == 'partial' and not source['remaining'].strip():
            raise ValueError('Częściowy opis nie podaje pozostałego zakresu')
    for section in lesson['sections']:
        if section['source_path'] not in paths:
            raise ValueError('Sekcja wskazuje plik spoza migawki')
        file = snapshot / paths[section['source_path']]['snapshot_path']
        if section['code'] and section['code'] not in file.read_text(encoding='utf-8'):
            raise ValueError('Cytat kodu nie jest dokładnym fragmentem wskazanego źródła')
    for method in lesson['methods']:
        if method['source_path'] not in paths:
            raise ValueError('Metoda wskazuje plik spoza migawki')
    for evidence in lesson['plan_connection']['evidence']:
        if evidence['path'] not in paths:
            raise ValueError('Odwołanie do planu lub implementacji wskazuje plik spoza migawki: '+evidence['path'])
    keys = [x['key'] for x in lesson['new_concepts']]
    if len(keys) > 5 or len(keys) != len(set(keys)):
        raise ValueError('Za dużo nowych pojęć lub zduplikowany klucz')
    for key in keys:
        if not re.fullmatch(r'[a-z][a-z0-9.-]{2,100}', key):
            raise ValueError('Niepoprawny klucz pojęcia')
        if key in known and not allow_known_new:
            raise ValueError(f'Ponowne pełne wyjaśnienie znanego pojęcia: {key}')
    for reminder in lesson['reused_concepts']:
        if reminder['key'] not in known:
            raise ValueError('Przypomnienie odwołuje się do nieznanego pojęcia')
    if len(lesson['diagrams']) > 3:
        raise ValueError('Za dużo diagramów')
    for diagram in lesson['diagrams']:
        ids = [x['id'] for x in diagram['nodes']]
        if not 1 <= len(ids) <= 12 or len(ids) != len(set(ids)):
            raise ValueError('Niepoprawne węzły diagramu')
        if diagram['kind'] == 'sequence' and len(ids) > 5:
            raise ValueError('Diagram sekwencji ma więcej niż pięciu uczestników')
        if len(diagram['edges']) > 24:
            raise ValueError('Za dużo krawędzi diagramu')
        for edge in diagram['edges']:
            if edge['source'] not in ids or edge['target'] not in ids:
                raise ValueError('Krawędź wskazuje nieistniejący węzeł')
    if not legacy:
        validate_self_test(lesson['self_test'], manifest, snapshot, actual)
