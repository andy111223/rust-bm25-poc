# Stan projektu

## Implementacja — analiza kodu

- `src/main.rs` / `main` nadal zawiera wyłącznie `println!("Hello, world!")`.
- `tests/fixtures/demo_slides.jsonl` zawiera trzy rekordy; `main` ich nie czyta.
- `Cargo.toml` / `dependencies` deklaruje anyhow, serde, serde_json i tantivy;
  brak ich użycia w `main`. Cargo.lock nie dowodzi użycia ani zgodności licencji.
- Od poprzedniej bazy nie zmieniono kodu Rust, manifestu, lockfile ani danych
  przykładowych. Dodano narzędzia i instrukcje agentów oraz dokumentację;
  `.gitignore` dodatkowo pomija `/.idea/`.
- Narzędzia pomocnicze opisuje [mapa kodu](CODE_MAP.md). Ich obecność w repozytorium
  nie potwierdza aktywnego runtime, hooków, timerów ani dostępności modelu.
- Indeksowanie, ranking BM25, pomiary i integracja pozostają planem:
  [APP_PLAN.md](APP_PLAN.md).

## Wyniki i artefakty

W tym przeglądzie nie uruchamiano aplikacji, buildów, testów ani agentów.
Nie potwierdzono działania BM25. Historyczny zapis w [AGENT_SETUP.md](AGENT_SETUP.md)
raportuje próby offline podczas adaptacji narzędzi; nie jest wynikiem ponownego
uruchomienia dla bieżącego HEAD. Nie dostarczono surowych logów tych prób.

W drzewie roboczym istnieją materiały dla commitu
`5f0023185cec49664718df16f27f367a412e3619`:

- [Lekcja o selekcji plików](learning/lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md),
  przygotowana 2026-10-28T23:36:07.632704+00:00: analiza statyczna skryptu,
  bez jego wykonania i bez potwierdzenia zrozumienia przez autora.
- [Wstępny raport prawny](legal/reviews/5f0023185cec-67c80748c857/report.md),
  przygotowany 2026-10-28T23:35:35.885349+00:00: zakres główny `.gitignore`
  i `tools/tests/check_rust_selection.py`; działanie nieuruchomione.
  Raport podaje daty kart źródeł: reviewed_on 2026-10-20, retrieved_at 2026-10-28.
  Nie jest audytem całego projektu ani potwierdzeniem aktualności prawa lub zgodności.

Obecność tych plików potwierdzono odczytem; nie ustalano sposobu ich utworzenia
ani stanu lokalnej instalacji. Materiały obu ról zachowano bez zmian.

## Metryka przeglądu

- Data: 2026-10-29, Europe/Warsaw (CET, UTC+01:00).
- Gałąź: `master`.
- source_head: `5f0023185cec49664718df16f27f367a412e3619`.
- Baza: `5ed8c12197b6a491a3fab8debf3aa12d8f79246b`, dostępna w Git.
- Poprzednie pending_source_paths: `[]`.
- Sprawdzono HEAD, indeks (pusty), zmiany robocze i pełną listę nowych plików;
  brak usunięć i zmian nazw. Zastane zmiany: cztery indeksy/mapy w docs/learning
  i docs/legal oraz nowe karty, lekcja i raport w tych katalogach.
- Zakres: różnica baza–HEAD, własne źródło Rust, Cargo.toml, fixture, .gitignore,
  instrukcje i dokumentacja techniczna; selektory oraz wybrane funkcje migawki,
  wywołania modelu i zapisu wyników w obu agentach, skrypt kontroli selekcji.
  Cargo.lock uwzględniono przez brak różnic, bez audytu grafu zależności.
- Braki: nie wykonano pełnego audytu narzędzi i ich testów, nie badano instalacji,
  nie czytano target/, konfiguracji IDE, sekretów ani lokalnego stanu Git.
  Nie weryfikowano zewnętrznych źródeł prawnych. Nie ma nowych dowodów wykonania.
- pending_source_paths: `[]` — brak zaległych zmian źródeł aplikacji;
  zakres nie oznacza pełnego audytu dodanych narzędzi.
