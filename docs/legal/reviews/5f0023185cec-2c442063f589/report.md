# Wstępna analiza konfiguracji i zależności Rust

Commit: `5f0023185cec49664718df16f27f367a412e3619` · Gałąź: `master`

Przygotowano: 2026-10-28T23:43:48.299046+00:00. Weryfikacja działania: **nieuruchomiona**.

Wstępna ocena. Zakres raportu i stan źródeł nie stanowią potwierdzenia zgodności prawnej.

## Część 1: Wstępna analiza konfiguracji i zależności Rust

Cargo.toml i Cargo.lock są identyczne z przekazaną bazą. W .gitignore dodano /.idea/. Zakres nie potwierdza przepływów danych aplikacji. Do przygotowania pozostaje zestawienie licencji składników odpowiednie do planowanego sposobu udostępniania projektu.

Zakres: Analiza statyczna trzech plików wersji after z commitu 5f0023185cec49664718df16f27f367a412e3619. Wersje before wykorzystano porównawczo, a pozostałe przekazane pliki jako kontekst. Uwzględniono instrukcje AGENTS.md, ENGINEERING_RULES.md i LEGAL_AGENT.md. Nie wykonywano narzędzi, kodu ani zapisów.

- .gitignore — po zmianie: Reguły pomijania /target, /data/ i /.idea/; względem bazy dodano /.idea/. Reguły nie potwierdzają zawartości katalogów ani usunięcia wcześniej śledzonych plików.
- Cargo.lock — po zmianie: Przejrzano zapis rozwiązanych wersji i zależności przechodnich, czyli bibliotek wymaganych przez inne biblioteki. Plik jest identyczny z bazą; nie potwierdza faktycznego użycia składników ani ich licencji.
- Cargo.toml — po zmianie: Deklaracja pakietu i zależności anyhow, serde z funkcją derive, serde_json oraz tantivy =0.27.0. Plik jest identyczny z bazą.

### Założenia wymagające potwierdzenia

- Eksperyment BM25 i możliwe przyszłe wykorzystanie w XREALPresentation potraktowano jako zadeklarowany plan. Nie przyjęto, że integracja lub dystrybucja już nastąpiły.

### dependency-licence-inventory — Przygotuj zestawienie licencji zależności przed udostępnieniem projektu

Priorytet: **niski** · Pewność: **wysoka** · Rekomendacja · Stan: Otwarte

**Obserwacja:** Cargo.toml deklaruje cztery bezpośrednie zależności, a Cargo.lock zapisuje także zależności przechodnie. Przekazane pliki konfiguracji nie zawierają tekstów ich licencji. Nie ustalono warunków korzystania ani obowiązków dotyczących planowanego wydania.

**Kiedy ma zastosowanie:** Zakres sprawdzenia zależy od rzeczywiście wykorzystywanych składników, ich dokładnych wersji oraz tego, czy autor udostępni źródła, program wynikowy lub zintegruje projekt z inną aplikacją. Konkretne wymagania należy ustalić z właściwych tekstów licencji.

**Prostymi słowami:** Lista bibliotek pomaga znaleźć warunki ich używania, ale sama nie jest potwierdzeniem uprawnień. Zestawienie licencji pozwoli ustalić na przykład, jakie informacje trzeba dołączyć do wydania. Brak tekstów licencji w tej migawce nie dowodzi braku uprawnień.

**Dowody w migawce**

- `Cargo.toml` (po zmianie), linie 6–10:

> [dependencies]
> anyhow = "1.0.104"
> serde = { version = "1.0.229", features = ["derive"] }
> serde_json = "1.0.154"
> tantivy = "=0.27.0"

- `Cargo.lock` (po zmianie), linie 15–17:

> name = "anyhow"
> version = "1.0.104"
> source = "registry+https://github.com/rust-lang/crates.io-index"

**Po stronie kodu**

- Przy przygotowaniu wydania zestawić składniki rzeczywiście wykorzystywane dla wybranej platformy i konfiguracji z wersjami zapisanymi w Cargo.lock, uwzględniając zależności przechodnie. Weryfikacja: Zestawienie wskazuje nazwę, wersję, źródło i sposób obecności każdego składnika w planowanym wydaniu.

**Po stronie autora / organizacji**

- Określić sposób udostępniania projektu i sprawdzić teksty LICENSE oraz ewentualne NOTICE w źródłach dokładnych wersji składników. Weryfikacja: Zapisano sposób dystrybucji, pochodzenie tekstów licencji oraz wynik sprawdzenia warunków i wymaganych informacji dla wydania.

**Brakujące informacje**

- Czy planujesz udostępniać źródła, gotowy program, czy wykorzystywać projekt wyłącznie wewnętrznie?

**Dowody potrzebne do rozstrzygnięcia**

- Zestawienie składników planowanego wydania z dokładnymi wersjami i tekstami licencji.
- Udokumentowana ocena warunków dla wybranego sposobu dystrybucji oraz przygotowane wymagane informacje licencyjne; materiał wymaga ponownej oceny, nie zamyka ustalenia automatycznie.

### Następne kroki

- Po ustaleniu sposobu udostępniania przygotować zestawienie licencji dokładnych wersji składników planowanego wydania.

### Ograniczenia

- To analiza wskazanego zakresu, bez oceny zgodności całej aplikacji. Nie uruchamiano programu, kompilacji ani testów; obecność zależności nie potwierdza ich wykonania lub włączenia do wydania.
- Przekazane legal_sources nie obejmują tekstów licencji tych bibliotek. Nie ustalono konkretnych warunków licencyjnych ani obowiązków na ich podstawie.
- Karty źródeł prawnych mają reviewed_on 2026-10-20 i deklarowane pobranie 2026-10-28. Udostępniono fragmenty poradników, wytycznych i oficjalnego omówienia, a nie zweryfikowane aktualne teksty aktów. Nie przeprowadzono bieżącej weryfikacji prawa, zmian ani terminów stosowania.
- Nie przekazano docs/README.md wymaganego przez instrukcje lokalne. Wymagane tam sprawdzenia bieżącego stanu Git i linków pominięto zgodnie z nadrzędnym zakresem zlecenia: wyłącznie analiza wejścia, bez narzędzi.
- Lista omissions jest pusta, ale wejście nie obejmuje całego repozytorium ani źródeł bibliotek. Nie sprawdzono zawartości lokalnych katalogów, historii publikacji, środowiska wdrożenia ani rzeczywistego sposobu dystrybucji.
- Nie zidentyfikowano potwierdzonego przepływu danych aplikacji w analizowanych plikach konfiguracji. Pusta lista flows nie potwierdza braku przepływów poza tym zakresem.

## Część 2: Wstępna analiza prawna punktu wejścia i testu wyboru plików

main nadal wypisuje wyłącznie stały komunikat. Skrypt testowy tworzy dane syntetyczne i zawiera sprawdzenia wykluczania wybranych plików z materiału dla agentów. Nie wskazano konkretnych ustaleń prawnych wymagających rejestracji w tym zakresie. Nie potwierdzono wykonania ani skuteczności testów.

Zakres: Analiza statyczna dwóch wskazanych plików w commicie 5f0023185cec49664718df16f27f367a412e3619. Uwzględniono przekazane instrukcje, profil, plan i dokumenty kontekstowe. Nie używano narzędzi ani nie zapisywano plików. Wynik nie stanowi oceny zgodności całej aplikacji.

- src/main.rs — po zmianie: Cały punkt wejścia: wypisanie stałego komunikatu. Treść jest identyczna z przekazaną wersją before.
- tools/tests/check_rust_selection.py — po zmianie: Cały skrypt: tworzenie tymczasowego repozytorium z danymi syntetycznymi oraz sprawdzenia wyboru plików, kontekstu i wykluczeń dla dwóch agentów.

Nie zgłoszono nowych ustaleń w tej części. Nie oznacza to pełnej zgodności projektu.

### Następne kroki

- Przed poleganiem na ochronie materiału wejściowego przejrzeć implementacje wyboru plików, snapshot, context i build_bundle w obu importowanych modułach agentów.
- W osobno zleconej weryfikacji uzyskać wynik testu syntetycznego dla tego commitu. Końcowy komunikat print w kodzie nie jest dowodem sukcesu.

### Ograniczenia

- Nie uruchamiano kodu, testów, instalatorów ani usług. Wywołania install widoczne w skrypcie dotyczą przygotowanego katalogu tymczasowego i nie dowodzą instalacji w projekcie autora.
- Nie udostępniono implementacji importowanego modułu agent dla żadnego narzędzia. Nie ustalono rzeczywistych odbiorców materiału, transmisji, redakcji danych, logowania ani przechowywania przez dostawcę.
- Lista omissions jest pusta, lecz zakres główny obejmuje tylko dwa pliki. Kontekst Cargo nie zastępuje sprawdzenia licencji komponentów, warunków dostawców ani sposobu dystrybucji.
- Nie sprawdzono stanu Git ani docs/README.md wymaganego przez instrukcje repozytorium: użytkownik ograniczył analizę do przekazanego wejścia, które nie zawiera tego dokumentu. Nie wykonano dodatkowych odczytów.
- Dokument PROJECT_STATUS.md odnosi się do commitu bazowego. Jego opisy instalacji i działania nie potwierdzają stanu po analizowanym commicie.
- Indeksowanie BM25 i integracja z XREALPresentation są opisane jako plan. Analizowany main ich nie implementuje; nie oceniono przyszłych korpusów, praw do treści ani przyszłych przepływów danych.
- Dostępne źródła prawne są wytycznymi, poradnikami i omówieniem KE, a nie zweryfikowanymi tekstami aktów lub umów. Karty mają reviewed_on 2026-10-20 i pobrania z 2026-10-28. Nie przeprowadzono bieżącej weryfikacji prawa, zmian ani terminów stosowania; dla tego zakresu nie przypisano na ich podstawie obowiązków.

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
| `Cargo.lock` | po zmianie | `0bfbda8130c7bcd59c94240f612c866e30420c88d314d3ad21d7986724af532d` | 0 |
| `Cargo.toml` | po zmianie | `c210eae24495f68f159034a87c3668d32f72bfd5ae40f73f149f5fc0b3632666` | 0 |
| `.gitignore` | przed zmianą | `c1d785ee354148210f345c2e707acff659f47f49beccb2e5b65e7c504f978bbb` | 0 |
| `Cargo.lock` | przed zmianą | `0bfbda8130c7bcd59c94240f612c866e30420c88d314d3ad21d7986724af532d` | 0 |
| `Cargo.toml` | przed zmianą | `c210eae24495f68f159034a87c3668d32f72bfd5ae40f73f149f5fc0b3632666` | 0 |
| `src/main.rs` | po zmianie | `c8e0583694bb1e0188dbe28fe0d65ac1130723c55f968b6262b906c147f72549` | 0 |
| `tools/tests/check_rust_selection.py` | po zmianie | `6019acfa772b7122a18a0113bdad27f0271250ebe2bb97397059cb294b69a108` | 0 |

Pominięcia podczas budowy migawki:

Brak dodatkowych pominięć limitowych. Filtry zakresu pozostają aktywne.

### Migawka części 2

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
| `src/main.rs` | po zmianie | `c8e0583694bb1e0188dbe28fe0d65ac1130723c55f968b6262b906c147f72549` | 0 |
| `tools/tests/check_rust_selection.py` | po zmianie | `6019acfa772b7122a18a0113bdad27f0271250ebe2bb97397059cb294b69a108` | 0 |
| `src/main.rs` | przed zmianą | `c8e0583694bb1e0188dbe28fe0d65ac1130723c55f968b6262b906c147f72549` | 0 |
| `.gitignore` | po zmianie | `6287181e46fbd28820dd5cc6f2fa43b0230f2ddf78e546178b104fb59458e722` | 0 |
| `Cargo.lock` | po zmianie | `0bfbda8130c7bcd59c94240f612c866e30420c88d314d3ad21d7986724af532d` | 0 |
| `Cargo.toml` | po zmianie | `c210eae24495f68f159034a87c3668d32f72bfd5ae40f73f149f5fc0b3632666` | 0 |

Pominięcia podczas budowy migawki:

Brak dodatkowych pominięć limitowych. Filtry zakresu pozostają aktywne.
