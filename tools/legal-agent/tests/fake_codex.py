"""Deterministic local test double; never used by the installed agent."""
import json
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("codex-test-double")
elif sys.argv[1:4] == ["mcp", "list", "--json"]:
    print(json.dumps([{"name": "private.server"}, {"name": "server with spaces"}]))
else:
    assert sys.argv[1] == "exec"
    args = sys.argv
    for setting in ['features.shell_tool=false', 'features.apps=false', 'features.plugins=false',
                    'features.multi_agent=false', 'features.hooks=false', 'web_search="disabled"',
                    'mcp_servers."private.server".enabled=false',
                    'mcp_servers."server with spaces".enabled=false']:
        assert setting in args, setting
    assert args[args.index("--sandbox")+1] == "read-only"
    prompt = sys.stdin.read()
    bundle = json.loads(prompt.split("DANE_WEJSCIOWE_JSON:\n", 1)[1])
    target = bundle["targets"][0]
    source = next(f for f in bundle["files"] if (f["path"],f["version"]) == (target["path"],target["version"]))
    lines = source["text"].splitlines()
    local_number = next((i+1 for i,x in enumerate(lines) if x.strip()), 1)
    number = local_number + source.get("first_line", 1) - 1
    evidence = dict(path=source["path"],version=source["version"],first_line=number,last_line=number,
                    quote=lines[local_number-1][:500] if lines else "")
    finding = dict(key="speech-audio-retention",title="Sprawdzenie przechowywania audio",domain="privacy",
                   priority="medium",confidence="medium",kind="potential_obligation",
                   observed="W zakresie tej części znaleziono funkcję wymagającą ustalenia celu i retencji.",
                   applicability="Jeżeli są to dane osobowe w zakresie RODO, ustal cel i niezbędny okres.",
                   plain_explanation="Ustal, czy nagranie jest potrzebne po transkrypcji.", evidence=[evidence],
                   references=[dict(source_id="EDPB_BASICS",section="The key principles of the GDPR",relevance="Poradnik opisuje ograniczenie przechowywania.")],
                   code_actions=[dict(task="Sprawdzić usuwanie audio.",verification="Syntetyczne nagranie i kontrola plików.")],
                   author_actions=[dict(task="Ustalić potrzebę zapisu.",verification="Potwierdzony profil aplikacji.")],
                   questions=["Czy nagranie ma pozostać po transkrypcji?"],closure_evidence=["Opis celu i wynik weryfikacji."])
    response = dict(title="Przegląd syntetycznego kodu",summary="Raport testowy.",scope_note="Tylko przekazane pliki.",
                    coverage=[dict(path=t["path"],version=t["version"],description="Odczyt statyczny.") for t in bundle["targets"]],assumptions=[],
                    flows=[dict(key="speech-backend",purpose="Przesłanie audio",data="Audio",origin="Klient",destination="Backend",
                                retention="Nieustalona",confidence="medium",evidence=[evidence],unknowns=["Okres przechowywania."])],
                    findings=[finding],previous_findings=[],profile_suggestions=["Uzupełnić cel zapisu audio."],
                    next_steps=["Odpowiedzieć na pytanie."],limitations=["Dane syntetyczne; nie uruchamiano aplikacji."])
    Path(args[args.index("--output-last-message")+1]).write_text(json.dumps(response))
