# Mapa kodu

| Ścieżka / symbol | Odpowiedzialność |
|---|---|
| src/main.rs / main | Punkt wejścia; println! wypisuje Hello, world! |
| Cargo.toml / package, dependencies | Pakiet 0.1.0, edition 2024; anyhow, serde (derive), serde_json, tantivy =0.27.0 |
| Cargo.lock | Rozwiązane wersje zależności; nie kod wyszukiwania |
| tests/fixtures/demo_slides.jsonl | Trzy przykładowe dokumenty: document_id, ordinal, tokens; brak czytnika w main |
| tools/learning-agent | Nauczyciel: migawka commitu, walidacja i materiały |
| tools/legal-agent | Analiza prawna: dowody, źródła i raporty |

Chcę zmienić uruchomienie → src/main.rs; zależności → Cargo.toml (osobne zlecenie);
przykładowe dane → tests/fixtures/demo_slides.jsonl.
Brak własnych wspólnych modułów lub kontraktu integracji w kodzie aplikacji.

## Narzędzia pomocnicze — analiza statyczna

| Ścieżka / symbol | Odpowiedzialność i granica |
|---|---|
| tools/learning-agent/learn.sh | Przekazuje argumenty do agent.py przez python3 |
| tools/learning-agent/agent.py / is_source, snapshot | Wybór źródeł i migawka wskazanego commitu; filtry ścieżek i limity rozmiaru |
| tools/learning-agent/agent.py / run_codex, publish, regenerate | Wywołanie modelu w read-only; runtime zapisuje lekcje MD/JSON/SVG, indeksy i lokalny HTML |
| tools/learning-agent/schema.py / validate | Walidacja lekcji i odniesień do migawki |
| tools/legal-agent/legal.sh | Przekazuje argumenty do agent.py przez python3 |
| tools/legal-agent/agent.py / candidate, context, build_bundle | Wybór źródeł, kontekst z drzewa roboczego i pakiet wersji before/after; kontekst jest oznaczany osobno |
| tools/legal-agent/agent.py / run_codex, publish, regenerate | Analiza modelowa read-only; runtime zapisuje raporty MD/JSON, rejestry i lokalny HTML |
| tools/legal-agent/schema.py / validate | Walidacja raportu i dowodów względem pakietu |
| tools/legal-agent/sources.py / fetch, validate_registry | Pobieranie kart źródeł i walidacja rejestru; obecność funkcji nie potwierdza aktualności źródeł |
| tools/tests/check_rust_selection.py / ROOT, tool, git | Syntetyczne repozytoria tymczasowe, osobne interpretery dla agentów, asercje selekcji Rust/Cargo i wykluczeń |

Skrypt kontroli selekcji wywołuje instalatory wyłącznie w tworzonych repozytoriach
syntetycznych (nauczyciel bez hooka, oba bez timerów). Jest kodem testowym,
nie dowodem wykonania. W tym przeglądzie go nie uruchamiano.

Wspólne nazwy `safe_rel` i `secret_path` w obu agent.py oznaczają osobne
implementacje filtrów; nie jest to jeden współdzielony komponent. Ich warunki
nie są identyczne. Nie zmieniano ich w ramach dokumentacji.
