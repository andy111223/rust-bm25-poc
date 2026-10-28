# Profil projektu

## Obserwacje z kodu — 2026-10-29

src/main.rs / main wypisuje stały komunikat. Nie zaobserwowano w nim odczytu
danych, sieci, AI, kont użytkowników ani wyszukiwania. Cargo.toml deklaruje
biblioteki; sama deklaracja nie potwierdza przepływów danych.
tests/fixtures/demo_slides.jsonl zawiera trzy przykładowe rekordy z tekstem.
Nie oceniono praw do późniejszych korpusów ani licencji wszystkich zależności.

## Cel zadeklarowany przez autora

Eksperyment BM25 w Rust; możliwe przyszłe wykorzystanie w XREALPresentation.

## Do potwierdzenia przez autora

- Kto jest właścicielem, operatorem i odbiorcą rozwiązania? Jaki zakres dystrybucji?
- Jakie będą źródła dokumentów, prawa do treści i ewentualne dane osobowe?
- Gdzie będą działać indeks i wyszukiwanie, jakie będą retencja i dostęp?
- Czy i jakie dane/kod wolno przekazywać dostawcy Codex CLI podczas analiz?
- Czy planowana jest usługa, wdrożenie lub integracja? Jurysdykcja i role nieustalone.

Nie przeniesiono profilu ani ustaleń innej aplikacji. Brak odpowiedzi nie jest zgodą.
