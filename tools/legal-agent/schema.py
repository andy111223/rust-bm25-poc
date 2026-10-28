"""Strict transport schema and checks against the actual, frozen evidence."""
from __future__ import annotations
import re
import copy


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def arr(item):
    return {"type": "array", "items": item}


S = {"type": "string"}
I = {"type": "integer"}


def enum(*values):
    return {"type": "string", "enum": list(values)}


EVIDENCE = obj(path=S, version=enum("before", "after", "context"),
               first_line=I, last_line=I, quote=S)
REFERENCE = obj(source_id=S, section=S, relevance=S)
ACTION = obj(task=S, verification=S)
FINDING = obj(
    key=S, title=S, domain=enum("privacy", "security", "ai", "licences", "other"),
    priority=enum("high", "medium", "low"), confidence=enum("high", "medium", "low"),
    kind=enum("potential_obligation", "contract_check", "recommendation"),
    observed=S, applicability=S, plain_explanation=S,
    evidence=arr(EVIDENCE), references=arr(REFERENCE),
    code_actions=arr(ACTION), author_actions=arr(ACTION),
    questions=arr(S), closure_evidence=arr(S))
FLOW = obj(key=S, purpose=S, data=S, origin=S, destination=S, retention=S,
           confidence=enum("high", "medium", "low"), evidence=arr(EVIDENCE), unknowns=arr(S))
SCHEMA = obj(
    title=S, summary=S, scope_note=S,
    coverage=arr(obj(path=S, version=enum("before", "after"), description=S)),
    assumptions=arr(S), flows=arr(FLOW), findings=arr(FINDING),
    previous_findings=arr(obj(key=S, assessment=enum("still_relevant", "change_observed", "not_assessed"),
                              explanation=S, evidence=arr(EVIDENCE))),
    profile_suggestions=arr(S), next_steps=arr(S), limitations=arr(S))


def check_shape(value, spec=SCHEMA, location="result"):
    typ = spec["type"]
    if typ == "object":
        if not isinstance(value, dict) or set(value) != set(spec["properties"]):
            raise ValueError(f"Niepoprawne pola: {location}")
        for k, v in value.items():
            check_shape(v, spec["properties"][k], location + "." + k)
    elif typ == "array":
        if not isinstance(value, list) or len(value) > 250:
            raise ValueError(f"Niepoprawna lista: {location}")
        for i, v in enumerate(value):
            check_shape(v, spec["items"], f"{location}[{i}]")
    elif typ == "integer":
        if type(value) is not int:
            raise ValueError(f"Niepoprawna liczba: {location}")
    elif not isinstance(value, str) or len(value) > 24000:
        raise ValueError(f"Niepoprawny tekst: {location}")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"Nieznana wartość: {location}")


def normalize_evidence_locations(report, bundle):
    """Correct only a uniquely located literal quote in the frozen source.

    Never edit the raw model response or infer a different quote/source version.
    The caller must still validate the complete returned response.
    """
    check_shape(report)
    corrected = copy.deepcopy(report)
    files = {(x["version"], x["path"]): x for x in bundle["files"]}
    changes = []
    for section in ("findings", "flows", "previous_findings"):
        for index, item in enumerate(corrected[section]):
            for number, evidence in enumerate(item["evidence"]):
                source = files.get((evidence["version"], evidence["path"]))
                if source is None:
                    continue
                text = source["text"]
                lines = text.splitlines()
                offset = source.get("first_line", 1) - 1
                a, b, quote = evidence["first_line"], evidence["last_line"], evidence["quote"]
                if not quote.strip() or len(quote) > 1500:
                    continue
                if (offset + 1 <= a <= b <= offset + len(lines) and b-a <= 50
                        and quote in "\n".join(lines[a-1-offset:b-offset])):
                    continue
                pos = text.find(quote)
                if pos < 0 or text.find(quote, pos+1) >= 0:
                    continue
                first = offset + text.count("\n", 0, pos) + 1
                last = offset + text.count("\n", 0, pos + len(quote) - 1) + 1
                if not (offset + 1 <= first <= last <= offset + len(lines) and last-first <= 50):
                    continue
                if quote not in "\n".join(lines[first-1-offset:last-offset]):
                    continue
                changes.append(dict(section=section, item=index, evidence=number,
                                    path=evidence["path"], version=evidence["version"],
                                    original_lines=[a, b], corrected_lines=[first, last]))
                evidence.update(first_line=first, last_line=last)
    return corrected, changes


def validate(report, bundle):
    check_shape(report)
    files = {(x["version"], x["path"]): x for x in bundle["files"]}
    expected = {(x["version"], x["path"]) for x in bundle["targets"]}
    actual = [(x["version"], x["path"]) for x in report["coverage"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Zakres odpowiedzi nie odpowiada plikom tej części (coverage)")
    sources = {x["id"]: x for x in bundle["legal_sources"]}
    known = {x["key"] for x in bundle["previous_findings"]}

    def evidence(items):
        for item in items:
            source = files.get((item["version"], item["path"]))
            if source is None:
                raise ValueError("Dowód wskazuje plik poza migawką")
            lines = source["text"].splitlines()
            a, b = item["first_line"], item["last_line"]
            offset = source.get("first_line", 1) - 1
            if not offset + 1 <= a <= b <= offset + len(lines) or b - a > 50:
                raise ValueError("Nieprawidłowe linie dowodu")
            quote = item["quote"]
            segment = "\n".join(lines[a-1-offset:b-offset])
            if not quote.strip() or len(quote) > 1500 or quote not in segment:
                raise ValueError("Cytat dowodu nie występuje we wskazanych liniach")

    keys = set()
    for finding in report["findings"]:
        key = finding["key"]
        if not re.fullmatch(r"[a-z][a-z0-9.-]{2,95}", key) or key in keys:
            raise ValueError("Niepoprawny lub powtórzony klucz ustalenia")
        keys.add(key)
        if not finding["evidence"] or not finding["closure_evidence"]:
            raise ValueError("Ustalenie wymaga dowodu i sposobu weryfikacji")
        if not (finding["code_actions"] or finding["author_actions"]):
            raise ValueError("Ustalenie wymaga konkretnego następnego działania")
        if finding["kind"] == "potential_obligation" and not finding["references"]:
            raise ValueError("Potencjalny obowiązek wymaga dostępnego źródła")
        evidence(finding["evidence"])
        for ref in finding["references"]:
            source = sources.get(ref["source_id"])
            if source is None or ref["section"] not in source["sections"]:
                raise ValueError("Nieznane źródło lub niezweryfikowane oznaczenie przepisu/sekcji")
            if not source["notes"] and not source.get("retrieved_excerpt"):
                raise ValueError("Sam odnośnik nie jest treścią źródła")
    flow_keys = set()
    for flow in report["flows"]:
        if not re.fullmatch(r"[a-z][a-z0-9.-]{2,95}", flow["key"]) or flow["key"] in flow_keys:
            raise ValueError("Niepoprawny lub powtórzony klucz przepływu")
        flow_keys.add(flow["key"])
        if not flow["evidence"]:
            raise ValueError("Przepływ wymaga dowodu; hipotezy wpisz do unknowns")
        evidence(flow["evidence"])
    for previous in report["previous_findings"]:
        if previous["key"] not in known:
            raise ValueError("Ocena wskazuje nieznane wcześniejsze ustalenie")
        if previous["assessment"] == "change_observed" and not previous["evidence"]:
            raise ValueError("Stwierdzenie zmiany wymaga dowodu")
        evidence(previous["evidence"])
    if not report["limitations"] or not report["scope_note"].strip():
        raise ValueError("Raport wymaga zakresu i ograniczeń")
    return report
