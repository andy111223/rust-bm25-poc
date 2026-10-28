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
