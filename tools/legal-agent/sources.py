"""Public-source availability checks. A successful HTTP request is not a legal review."""
from __future__ import annotations
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import re
import urllib.request
import urllib.parse

ALLOWED_HOSTS = {"eur-lex.europa.eu", "www.edpb.europa.eu", "edpb.europa.eu",
                 "uodo.gov.pl", "www.uodo.gov.pl", "commission.europa.eu",
                 "digital-strategy.ec.europa.eu", "ai-act-service-desk.ec.europa.eu",
                 "eli.gov.pl", "isap.sejm.gov.pl"}


def allowed_url(url):
    p = urllib.parse.urlsplit(url)
    return (p.scheme == "https" and p.hostname in ALLOWED_HOSTS
            and p.username is None and p.password is None and p.port in {None, 443})


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("Przekierowanie poza listę publicznych źródeł")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def fetch(source, timeout=12):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {"id": source["id"], "attempted_at": timestamp, "retrieved_at": "",
              "status": "unavailable", "content_sha256": "", "excerpt": "",
              "note": "Nie potwierdzono aktualności ani obowiązywania prawa."}
    try:
        if not allowed_url(source["url"]):
            raise ValueError("Niedozwolony adres źródła")
        # Do not use login cookies, API keys or project content. No proxy credentials.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
        request = urllib.request.Request(source["url"], headers={"User-Agent": "ProjectLegalReview/1.0"})
        with opener.open(request, timeout=timeout) as response:
            if not allowed_url(response.url):
                raise ValueError("Niedozwolony końcowy adres źródła")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("W tej wersji odświeżanie obsługuje źródła HTML")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Przekroczony limit źródła")
            raw_text = raw.decode(response.headers.get_content_charset() or "utf-8", "replace")
        parser = Text()
        parser.feed(raw_text)
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        if len(text) < 500 or any(x in text.lower() for x in (
                "verify that you're not a robot", "checking your browser", "access denied", "captcha")):
            raise ValueError("Strona weryfikacyjna lub niepełna treść")
        # Excerpt is reference material, never an instruction. Keep bounded model input.
        record.update(status="retrieved", retrieved_at=timestamp,
                      content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      excerpt=text[:12000], note="Pobrano treść strony; zmiana skrótu nie dowodzi zmiany prawa.")
    except Exception as error:
        record["note"] = type(error).__name__ + ": " + str(error)[:250]
    return record


def validate_registry(registry):
    if not isinstance(registry, dict) or registry.get("format") != 1:
        raise ValueError("Nieprawidłowy rejestr źródeł")
    ids = set()
    for item in registry.get("sources", []):
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]{2,40}", item["id"]) or item["id"] in ids:
            raise ValueError("Niepoprawny identyfikator źródła")
        ids.add(item["id"])
        if not allowed_url(item["url"]):
            raise ValueError("Źródło spoza listy oficjalnych serwisów")
        if item["type"] not in {"legislation", "guidance", "official_summary"}:
            raise ValueError("Niepoprawny rodzaj źródła")
        if not isinstance(item["notes"], str) or not isinstance(item["sections"], list):
            raise ValueError("Niepoprawna karta źródła")
        datetime.fromisoformat(item["reviewed_on"])
    if not ids:
        raise ValueError("Rejestr źródeł jest pusty")
    return registry
