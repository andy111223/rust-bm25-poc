"""Escaped Markdown/HTML output; local SVG diagrams; no remote scripts or trackers."""
from __future__ import annotations
import html
import json
from urllib.parse import urlsplit

LABEL = {"open": "Otwarte", "planned": "Zaplanowane przez autora", "implemented": "Autor zgłosił wdrożenie",
         "verified": "Autor zgłosił weryfikację", "not_applicable": "Autor uzasadnił brak zastosowania",
         "review_again": "Do ponownej oceny po zmianie", "high": "wysoki", "medium": "średni", "low": "niski",
         "privacy": "Dane osobowe", "security": "Bezpieczeństwo", "ai": "AI i jakość danych",
         "licences": "Licencje i treści", "other": "Pozostałe", "potential_obligation": "Potencjalny obowiązek",
         "contract_check": "Warunki umowy / licencji do sprawdzenia", "recommendation": "Rekomendacja",
         "before": "przed zmianą", "after": "po zmianie", "context": "kontekst autora",
         "legislation": "Akt prawny", "guidance": "Wytyczne / poradnik", "official_summary": "Omówienie urzędowe"}


def esc(value):
    return html.escape(str(value), quote=True)


def label(value):
    return LABEL.get(value, value)


def confidence(value):
    return {"high": "wysoka", "medium": "średnia", "low": "niska"}.get(value, value)


def safe_url(value):
    try:
        p = urlsplit(value)
        return value if p.scheme == "https" and p.hostname and p.username is None else "#"
    except ValueError:
        return "#"


def md(value):
    return str(value).replace("\r", "").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")


def bullets(values):
    return "\n".join("- " + md(v).replace("\n", " ") for v in values) + "\n"


def evidence_md(items):
    result = ""
    for item in items:
        result += f'- `{md(item["path"])}` ({label(item["version"])}), linie {item["first_line"]}–{item["last_line"]}:\n\n'
        result += "> " + md(item["quote"]).replace("\n", "\n> ") + "\n\n"
    return result


def finding_md(f, sources=None):
    result = f'### {f.get("id", f["key"])} — {md(f["title"])}\n\n'
    result += (f'Priorytet: **{label(f["priority"])}** · Pewność: **{confidence(f["confidence"])}** · '
               f'{label(f["kind"])} · Stan: {label(f.get("status", "open"))}\n\n')
    result += "**Obserwacja:** " + md(f["observed"]) + "\n\n"
    result += "**Kiedy ma zastosowanie:** " + md(f["applicability"]) + "\n\n"
    result += "**Prostymi słowami:** " + md(f["plain_explanation"]) + "\n\n"
    result += "**Dowody w migawce**\n\n" + evidence_md(f["evidence"])
    refs = f.get("references_resolved", [])
    if not refs and sources is not None:
        indexed = {s["id"]: s for s in sources}
        refs = [dict(r, source=indexed[r["source_id"]]) for r in f["references"]]
    if refs:
        result += "**Źródła i warunki interpretacji**\n\n"
        for ref in refs:
            s = ref["source"]
            result += (f'- [{md(s["title"])}]({safe_url(s["url"])}) — {label(s["type"])}; '
                       f'{md(ref["section"])}. {md(ref["relevance"])} '
                       f'Karta przejrzana: {s["reviewed_on"]}; pobranie: {s.get("retrieval_status", "nieustalone")}.\n')
        result += "\n"
    for title, key in [("Po stronie kodu", "code_actions"), ("Po stronie autora / organizacji", "author_actions")]:
        result += "**" + title + "**\n\n"
        result += bullets(a["task"] + " Weryfikacja: " + a["verification"] for a in f[key]) if f[key] else "Brak osobnego zadania w tym zakresie.\n"
        result += "\n"
    if f["questions"]:
        result += "**Brakujące informacje**\n\n" + bullets(f["questions"]) + "\n"
    result += "**Dowody potrzebne do rozstrzygnięcia**\n\n" + bullets(f["closure_evidence"]) + "\n"
    if f.get("later_assessment"):
        result += "**Późniejsza obserwacja zmiany (nie zamyka ustalenia):** " + md(f["later_assessment"]["explanation"]) + "\n\n"
        result += evidence_md(f["later_assessment"]["evidence"])
    if f.get("decision"):
        d = f["decision"]
        result += f'**Deklaracja autora ({d["at"]}):** {md(d["note"])}\n\n'
    return result


def report_markdown(report):
    result = (f'# {md(report["title"])}\n\n'
              f'Commit: `{report["commit"]}` · Gałąź: `{md(report["branch"])}`\n\n'
              f'Przygotowano: {report["created_at"]}. Weryfikacja działania: **nieuruchomiona**.\n\n'
              'Wstępna ocena. Zakres raportu i stan źródeł nie stanowią potwierdzenia zgodności prawnej.\n\n')
    for i, part in enumerate(report["parts"], 1):
        result += f'## Część {i}: {md(part["title"])}\n\n{md(part["summary"])}\n\n'
        result += "Zakres: " + md(part["scope_note"]) + "\n\n"
        result += bullets(c["path"] + " — " + label(c["version"]) + ": " + c["description"] for c in part["coverage"]) + "\n"
        if part["assumptions"]:
            result += "### Założenia wymagające potwierdzenia\n\n" + bullets(part["assumptions"]) + "\n"
        if not part["findings"]:
            result += "Nie zgłoszono nowych ustaleń w tej części. Nie oznacza to pełnej zgodności projektu.\n\n"
        for finding in part["findings"]:
            result += finding_md(finding, report["legal_sources"])
        if part["previous_findings"]:
            result += "### Wcześniejsze ustalenia\n\n" + bullets(
                x["key"] + " — " + x["assessment"] + ": " + x["explanation"] for x in part["previous_findings"]) + "\n"
        result += "### Następne kroki\n\n" + bullets(part["next_steps"]) + "\n"
        result += "### Ograniczenia\n\n" + bullets(part["limitations"]) + "\n"
    if report.get("manifests"):
        result += "## Zakres przygotowanych migawek\n\n" + md(report["excluded_categories"]) + "\n\n"
        for manifest in report["manifests"]:
            result += f'### Migawka części {manifest["part"]}\n\n'
            repairs = manifest.get("line_repairs", {}).get("changes", [])
            if repairs:
                result += (f'Automatycznie skorygowano numerację {len(repairs)} odwołań po jednoznacznym, '
                           'dosłownym dopasowaniu cytatu w migawce. Oryginalna odpowiedź modelu pozostała zachowana. '
                           'Szczegóły i hashe są w line_repairs w report.json.\n\n')
            result += "| Plik | Wersja / zakres | SHA-256 źródła | Ukryte wiersze |\n|---|---|---|---|\n"
            for f in manifest["files"]:
                region = f' · linie {f["first_line"]}–{f["last_line"]} z {f["total_lines"]}' if "first_line" in f else ""
                result += f'| `{md(f["path"])}` | {label(f["version"])}{region} | `{f["sha256"]}` | {f.get("redacted_lines", 0)} |\n'
            result += "\nPominięcia podczas budowy migawki:\n\n" + (bullets(manifest["omissions"]) if manifest["omissions"] else "Brak dodatkowych pominięć limitowych. Filtry zakresu pozostają aktywne.\n") + "\n"
    return result


def findings_markdown(findings, signature):
    result = ("# Rejestr ustaleń\n\nPlik generowany z raportów dostępnych w bieżącej historii Git. "
              "Własne wyjaśnienia zapisuj w DECISIONS.md albo poleceniem decide. "
              "Decyzje autora są deklaracjami, a nie automatycznym wynikiem audytu.\n\n")
    if not findings:
        return result + "Brak ustaleń. Jeżeli nie wykonano baseline, brak wpisów nie oznacza wykonanej analizy.\n"
    result += "| ID | Temat | Priorytet | Pewność | Stan | Ostatnia obserwacja |\n|---|---|---|---|---|---|\n"
    for f in findings:
        result += f'| {f["id"]} | {md(f["title"])} | {label(f["priority"])} | {confidence(f["confidence"])} | {label(f["status"])} | `{f["last_commit"][:12]}` |\n'
    result += "\n"
    for f in findings:
        if f.get("profile_signature") != signature:
            result += "**Uwaga: profil aplikacji lub rejestr źródeł zmienił się od tej obserwacji.**\n\n"
        result += finding_md(f)
    return result


def flows_markdown(flows):
    result = ("# Mapa danych — obserwacje z kodu\n\nMapa jest przyrostowa. Wpisy zachowują commit ostatniej obserwacji; "
              "brak wpisu w późniejszym raporcie nie potwierdza usunięcia przepływu. "
              "Pełny obraz wdrożenia wymaga potwierdzenia autora.\n\n")
    for f in flows:
        result += f'## {md(f["purpose"])}\n\n'
        result += (f'{md(f["origin"])} → {md(f["destination"])}\n\nDane: {md(f["data"])}\n\n'
                   f'Przechowywanie: {md(f["retention"])}\n\nCommit: `{f.get("commit", "demo")}`. '
                   f'Pewność: {confidence(f["confidence"])}.\n\n')
        result += evidence_md(f["evidence"])
        if f["unknowns"]:
            result += "Do ustalenia:\n\n" + bullets(f["unknowns"]) + "\n"
    return result


def svg_flow(flow):
    # Every arrow represents one documented transfer, not an inferred deployment.
    def lines(value, width=32, limit=3):
        words, rows, row = str(value).split(), [], ""
        for word in words:
            if len(row) + len(word) > width and row:
                rows.append(row)
                row = word
            else:
                row = (row + " " + word).strip()
        if row:
            rows.append(row)
        if len(rows) > limit:
            rows = rows[:limit]
            rows[-1] = rows[-1][:width-1] + "…"
        return rows
    def text(value, x, y, cls=""):
        return '<text x="' + str(x) + '" y="' + str(y) + '" class="' + cls + '">' + ''.join(
            '<tspan x="' + str(x) + '" dy="' + ("0" if i == 0 else "20") + '">' + esc(v) + '</tspan>'
            for i, v in enumerate(lines(value))) + '</text>'
    return (f'<svg role="img" aria-label="{esc(flow["purpose"])}" viewBox="0 0 800 250" xmlns="http://www.w3.org/2000/svg">'
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#397064"/></marker></defs>'
            '<style>text{font:15px system-ui;fill:#163a32}.small{font-size:13px;fill:#536a63}</style>'
            '<rect x="12" y="12" width="776" height="226" rx="18" fill="#f1f7f4"/>'
            '<rect x="30" y="35" width="270" height="90" rx="12" fill="#dcefe5"/>'
            '<rect x="500" y="35" width="270" height="90" rx="12" fill="#e2e9fb"/>'
            '<path d="M315 80 L485 80" stroke="#397064" stroke-width="3" marker-end="url(#arrow)"/>'
            + text(flow["origin"], 45, 62) + text(flow["destination"], 515, 62)
            + text("Dane: " + flow["data"], 45, 160, "small")
            + text("Retencja: " + flow["retention"], 430, 160, "small") + '</svg>')


def render(findings, flows, reports, signature, demo=False):
    counts = {k: sum(1 for f in findings if f["priority"] == k) for k in ("high", "medium", "low")}
    intro = ("FIKCYJNA DEMONSTRACJA — przykład zapisu nagrań, bez analizy Twojego projektu." if demo else
             "Wstępna ocena kodu i kontekstu. Zapis raportu nie potwierdza zgodności prawnej aplikacji.")
    body = f'<header><div class="eyebrow">AGENT ANALIZY PRAWNEJ</div><h1>Co wymaga uwagi w projekcie?</h1><p>{esc(intro)}</p></header>'
    body += '<nav><a href="#findings">Ustalenia</a><a href="#flows">Przepływy danych</a><a href="#reports">Raporty i źródła</a></nav>'
    body += '<main><section class="metrics">' + ''.join(
        f'<div><strong>{counts[k]}</strong><span>priorytet {label(k)}</span></div>' for k in counts) + '</section>'
    if not reports and not demo:
        body += '<aside>Nie ma jeszcze przeglądu na bieżącej historii Git. Uruchom <code>baseline --background</code>. Pusta lista nie oznacza sprawdzonego projektu.</aside>'
    body += '<section id="findings"><h2>Ustalenia i działania</h2>'
    for f in sorted(findings, key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x["priority"]], x["title"])):
        body += (f'<article><div class="tag {esc(f["priority"])}">Priorytet {label(f["priority"])} · pewność {confidence(f["confidence"])}</div>'
                 f'<h3>{esc(f["title"])}</h3><p class="meta">{esc(f.get("id", f["key"]))} · {label(f["domain"])} · {label(f.get("status", "open"))}</p>')
        if not demo and f.get("profile_signature") != signature:
            body += '<aside>Profil lub źródła zmieniły się od tej obserwacji. Wniosek wymaga ponownego odniesienia do aktualnego kontekstu.</aside>'
        body += '<h4>Co znaleziono?</h4><p>' + esc(f["observed"]) + '</p>'
        body += '<h4>Co to oznacza prostymi słowami?</h4><p>' + esc(f["plain_explanation"]) + '</p>'
        body += '<p><strong>Warunki zastosowania:</strong> ' + esc(f["applicability"]) + '</p>'
        body += '<div class="actions">'
        for title, key in [("Po stronie kodu", "code_actions"), ("Po stronie autora / organizacji", "author_actions")]:
            body += '<div><h4>' + title + '</h4>'
            for a in f[key]:
                body += '<p>' + esc(a["task"]) + '</p><p class="verification">Jak sprawdzić: ' + esc(a["verification"]) + '</p>'
            if not f[key]:
                body += '<p>Brak osobnego zadania w tym zakresie.</p>'
            body += '</div>'
        body += '</div>'
        if f["questions"]:
            body += '<h4>Pytania do autora</h4><ul>' + ''.join('<li>' + esc(q) + '</li>' for q in f["questions"]) + '</ul>'
        body += '<details><summary>Dowody w kodzie i źródła</summary>'
        for e in f["evidence"]:
            body += (f'<p><code>{esc(e["path"])}</code> · {label(e["version"])} · linie {e["first_line"]}–{e["last_line"]}</p>'
                     '<pre>' + esc(e["quote"]) + '</pre>')
        for ref in f.get("references_resolved", []):
            s = ref["source"]
            body += (f'<p><a href="{esc(safe_url(s["url"]))}" target="_blank" rel="noreferrer">{esc(s["title"])}</a> · '
                     f'{label(s["type"])} · {esc(ref["section"])}</p><p>{esc(ref["relevance"])}</p>')
        body += '<p><strong>Dowody potrzebne do rozstrzygnięcia</strong></p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in f["closure_evidence"]) + '</ul></details>'
        if f.get("decision"):
            body += '<p class="meta">Deklaracja autora: ' + esc(f["decision"]["note"]) + '</p>'
        if f.get("later_assessment"):
            body += '<p><strong>Późniejsza obserwacja zmiany:</strong> ' + esc(f["later_assessment"]["explanation"]) + '</p>'
        body += '</article>'
    body += '</section><section id="flows"><h2>Przepływy danych</h2><p>Mapa przyrostowa. Każdy przepływ ma dowód; środowisko wdrożenia wymaga potwierdzenia.</p>'
    for flow in flows:
        body += '<article><h3>' + esc(flow["purpose"]) + '</h3>' + svg_flow(flow)
        body += '<p class="meta">Ostatnia obserwacja: ' + esc(flow.get("commit", "demo")[:12]) + ' · pewność ' + confidence(flow["confidence"]) + '</p>'
        if flow["unknowns"]:
            body += '<p><strong>Do ustalenia</strong></p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in flow["unknowns"]) + '</ul>'
        body += '</article>'
    body += '</section><section id="reports"><h2>Raporty i stan źródeł</h2>'
    for report in reversed(reports):
        body += '<article><h3>' + esc(report["title"]) + '</h3><p class="meta">' + esc(report["commit"][:12]) + ' · ' + esc(report["created_at"]) + '</p>'
        for part in report["parts"]:
            body += '<p>' + esc(part["summary"]) + '</p><p><strong>Zakres:</strong> ' + esc(part["scope_note"]) + '</p>'
            body += '<details><summary>Zakres, ograniczenia i następne kroki</summary><ul>'
            body += ''.join('<li><code>' + esc(c["path"]) + '</code> — ' + esc(c["description"]) + '</li>' for c in part["coverage"])
            body += '</ul><h4>Ograniczenia</h4><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in part["limitations"]) + '</ul>'
            body += '<h4>Następne kroki</h4><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in part["next_steps"]) + '</ul></details>'
        if report.get("manifests"):
            body += '<details><summary>Pominięcia i pochodzenie plików</summary><p>' + esc(report["excluded_categories"]) + '</p>'
            for manifest in report["manifests"]:
                body += '<h4>Część ' + str(manifest["part"]) + '</h4><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in manifest["omissions"]) + '</ul>'
                repairs = manifest.get("line_repairs", {}).get("changes", [])
                if repairs:
                    body += '<p>Skorygowano numerację ' + str(len(repairs)) + ' odwołań po jednoznacznym, dosłownym dopasowaniu cytatu w migawce. Zachowano oryginalną odpowiedź. Szczegóły: line_repairs w report.json.</p>'
                body += '<p class="meta">Pełny manifest plików i hashy znajduje się w report.json oraz report.md.</p>'
            body += '</details>'
        body += '<details><summary>Daty kart i pobrania publicznych źródeł</summary><p>Pobranie strony nie oznacza sprawdzenia obowiązywania przepisów.</p><ul>'
        for s in report["legal_sources"]:
            body += (f'<li><a href="{esc(safe_url(s["url"]))}" target="_blank" rel="noreferrer">{esc(s["title"])}</a> · '
                     f'{label(s["type"])} · karta: {esc(s["reviewed_on"])} · '
                     f'pobranie: {esc(s.get("retrieved_at") or "nie potwierdzono")} ({esc(s.get("retrieval_status", "brak"))})</li>')
        body += '</ul></details></article>'
    body += '</section></main><footer>Analiza statyczna · bez uruchamiania aplikacji · decyzje autora zapisane oddzielnie</footer>'
    css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f5f2;color:#1d302b;font:17px/1.6 system-ui,sans-serif}header{background:#153e35;color:#f7fff9;padding:50px max(6vw,24px) 40px}h1{font-size:clamp(30px,4vw,48px);line-height:1.2;max-width:1000px;margin:15px 0}header p{max-width:950px;color:#d5e8dd}.eyebrow{letter-spacing:.16em;font-size:12px;font-weight:700}nav{padding:15px max(6vw,24px);background:white;border-bottom:1px solid #dce3dc;display:flex;gap:25px;flex-wrap:wrap}a{color:#17664d;text-underline-offset:3px}nav a{font-size:15px}main{max-width:1240px;padding:28px 24px 60px;margin:auto}h2{font-size:28px;margin:42px 0 18px}h3{font-size:24px;line-height:1.3;margin:16px 0 8px}h4{font-size:17px;margin:22px 0 5px}p{margin:8px 0 15px}.meta,.verification{font-size:14px;color:#54675e}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.metrics div{border:1px solid #dce4dc;background:white;border-radius:14px;padding:20px}.metrics strong{display:block;font-size:30px}.metrics span{font-size:14px;color:#5d6f64}article{background:white;border:1px solid #dce4dc;border-radius:16px;padding:28px;margin:20px 0;overflow-wrap:anywhere}.tag{display:inline-block;border-radius:30px;padding:5px 12px;font-size:12px;font-weight:650}.high{background:#fce8df;color:#86371a}.medium{background:#fff2cb;color:#775800}.low{background:#e3eee5;color:#335d42}.actions{display:grid;grid-template-columns:1fr 1fr;gap:25px;padding:0 22px 12px;background:#f4f7f3;border-radius:12px}.verification{border-left:3px solid #a9c0b2;padding-left:12px}details{padding:15px 0;border-top:1px solid #e1e7e0;margin-top:18px}summary{cursor:pointer;color:#23654c;font-weight:600}pre{white-space:pre-wrap;background:#f0f4f0;padding:15px;border-radius:8px;font-size:13px}code{font-size:.85em}aside{padding:18px;background:#fff4d5;border-left:4px solid #b99435;margin:20px 0}svg{width:100%;height:auto;display:block}footer{text-align:center;color:#607266;font-size:13px;padding:25px}@media(max-width:700px){.actions{grid-template-columns:1fr}.metrics{gap:7px}.metrics div{padding:13px}.metrics span{font-size:12px}article{padding:20px}h3{font-size:21px}}'''
    return ('<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'">'
            '<title>Agent analizy prawnej — projekt</title><style>' + css + '</style></head><body>' + body + '</body></html>')
