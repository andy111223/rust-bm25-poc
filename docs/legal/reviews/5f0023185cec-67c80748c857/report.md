# Wstępna analiza prawna wykluczeń Git i testu selekcji plików

Commit: `5f0023185cec49664718df16f27f367a412e3619` · Gałąź: `master`

Przygotowano: 2026-10-28T23:35:35.885349+00:00. Weryfikacja działania: **nieuruchomiona**.

Wstępna ocena. Zakres raportu i stan źródeł nie stanowią potwierdzenia zgodności prawnej.

## Część 1: Wstępna analiza prawna wykluczeń Git i testu selekcji plików

W dwóch plikach objętych zakresem nie wskazano konkretnych nowych zagadnień wymagających ustalenia prawnego. Dodano wykluczenie /.idea/ oraz testy na danych syntetycznych sprawdzające wybór plików i wykluczanie plików potencjalnie poufnych. Obecność testów nie potwierdza ich wykonania ani skuteczności zabezpieczeń.

Zakres: Analiza statyczna wyłącznie przekazanego wejścia dla commitu 5f0023185cec49664718df16f27f367a412e3619, gałąź master. Zakres główny obejmuje wyłącznie wersje after plików .gitignore i tools/tests/check_rust_selection.py. Wersję before .gitignore i pozostałe materiały wykorzystano pomocniczo. Uwzględniono instrukcje roli prawnej oraz plan eksperymentu BM25; planowana integracja nie jest potwierdzonym działaniem aplikacji.

- .gitignore — po zmianie: Przejrzano cały przekazany plik. W porównaniu z wersją before dodano /.idea/. Wpisy ignorowania plików nie potwierdzają usunięcia wcześniej zapisanych danych ani ochrony dostępu.
- tools/tests/check_rust_selection.py — po zmianie: Przejrzano cały przekazany skrypt. Definiuje tworzenie tymczasowych repozytoriów z danymi syntetycznymi oraz sprawdzenia selekcji źródeł Rust, manifestów Cargo i wykluczeń plików potencjalnie poufnych dla obu agentów. Końcowy komunikat o sukcesie jest elementem kodu, a nie przekazanym wynikiem testu.

Nie zgłoszono nowych ustaleń w tej części. Nie oznacza to pełnej zgodności projektu.

### Następne kroki



### Ograniczenia

- Nie używano narzędzi, sieci ani plików spoza wejścia; nie uruchamiano kodu i niczego nie zapisano. Wymagane w AGENTS.md sprawdzenie bieżącego stanu Git nie zostało wykonane, ponieważ zlecenie ogranicza analizę do przekazanej migawki.
- Nie przekazano docs/README.md wymaganego przez lokalne instrukcje. Dostępne były profil, decyzje, plan, stan projektu i mapa kodu; nie uzupełniano brakującej dokumentacji domysłami.
- Nie przekazano implementacji importowanych modułów agent ani wyników testów. Nie potwierdzono skuteczności wykluczeń, rzeczywistego działania instalatorów, braku komunikacji sieciowej ani kompletności tworzonych pakietów danych.
- Nie przekazano wersji before skryptu testowego, więc jego szczegółowe zmiany względem bazy pozostają nieustalone. Kontekst PROJECT_STATUS.md opisuje wcześniejszy source_head i nie potwierdza stanu działania narzędzi po analizowanym commicie.
- Karty źródeł prawnych mają reviewed_on 2026-10-20 i retrieved_at 2026-10-28. Udostępnione fragmenty poradników i omówienia nie stanowią aktualnej weryfikacji tekstów aktów, zmian ani terminów stosowania. Nie wyprowadzano z nich obowiązków dla samych syntetycznych testów.
- Nie oceniono licencji pełnego grafu zależności, warunków dostawcy analiz modelowych ani przyszłych korpusów i integracji. Brak ustaleń w tym wąskim zakresie nie oznacza audytu ani potwierdzenia zgodności całej aplikacji.

## Zakres przygotowanych migawek

Sekrety, produkcyjne dane, binaria, pliki niewersjonowane, vendor/SDK i kod samych agentów; szczegóły filtrów w agent.py.

### Migawka części 1

| Plik | Wersja / zakres | SHA-256 źródła | Ukryte wiersze |
|---|---|---|---|
| `AGENTS.md` | kontekst autora | `88545f1dd6fc98ca4e10e9b9394c57eabb66928bd27707302fc98b4dd73fff46` | 0 |
| `ENGINEERING_RULES.md` | kontekst autora | `c850c051c67a71e38b8b2dcec4a540078e5e249111ba219c15013ac2df02364d` | 0 |
| `LEGAL_AGENT.md` | kontekst autora | `a29da18434e1ca6dfbeb16b2b8980615ac84d2f63067aeee94d01141f89dc853` | 0 |
| `docs/legal/APP_PROFILE.md` | kontekst autora | `22b353d327b986fef00c095718b7657a800fc8406ca79ce6cb23433e658a57f3` | 0 |
| `docs/legal/DECISIONS.md` | kontekst autora | `4f1ba4a3ff52b4e1365a3773cbdf1bc8486b0107232b2aa83a30d898455d93df` | 0 |
| `docs/APP_PLAN.md` | kontekst autora | `764922f7d64bc6dd4dfd67b1983f624785dcd4f09883779f4d109369c3a2fac5` | 0 |
| `docs/PROJECT_STATUS.md` | kontekst autora | `4c31dc4d112272b6d2f9d92bb1b7b6e2e5f1b5556d025a5ab648c6c3a5e6f19e` | 0 |
| `docs/CODE_MAP.md` | kontekst autora | `c482de31e6dc985dc22d0430ce10113f13131b6ae9b86874accedbe486b2ba18` | 0 |
| `.gitignore` | po zmianie | `6287181e46fbd28820dd5cc6f2fa43b0230f2ddf78e546178b104fb59458e722` | 0 |
| `tools/tests/check_rust_selection.py` | po zmianie | `6019acfa772b7122a18a0113bdad27f0271250ebe2bb97397059cb294b69a108` | 0 |
| `.gitignore` | przed zmianą | `c1d785ee354148210f345c2e707acff659f47f49beccb2e5b65e7c504f978bbb` | 0 |
| `Cargo.lock` | po zmianie | `0bfbda8130c7bcd59c94240f612c866e30420c88d314d3ad21d7986724af532d` | 0 |
| `Cargo.toml` | po zmianie | `c210eae24495f68f159034a87c3668d32f72bfd5ae40f73f149f5fc0b3632666` | 0 |
| `src/main.rs` | po zmianie | `c8e0583694bb1e0188dbe28fe0d65ac1130723c55f968b6262b906c147f72549` | 0 |

Pominięcia podczas budowy migawki:

Brak dodatkowych pominięć limitowych. Filtry zakresu pozostają aktywne.
