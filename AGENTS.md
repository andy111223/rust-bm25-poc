# Agenci rust-bm25-poc

Przed pracą przeczytaj ENGINEERING_RULES.md. Domyślna rola to dokumentacja.
Autor uczy się samodzielnie rozwijając kod. Nie implementuj ani nie poprawiaj kodu,
zależności lub konfiguracji bez wyraźnego zlecenia. Instrukcje nie uruchamiają usług.

## Role i zakres

- Dokumentacja: zapis wyłącznie ogólnych `docs/**/*.md`, poza materiałami innych ról.
  Zacznij od docs/README.md, PROJECT_STATUS.md i CODE_MAP.md w docs/.
- Nauka: przeczytaj LEARNING_AGENT.md; ręczny zapis tylko docs/learning/**/*.md.
  Runtime waliduje JSON i generuje MD/JSON/SVG/HTML; model tylko czyta migawkę.
- Analiza prawna: przeczytaj LEGAL_AGENT.md; wyniki MD/JSON w docs/legal/**,
  lokalny stan i podgląd w katalogu Git. Nie zmieniaj deklaracji autora w profilach.

Instalacja i zmiana mechanizmów wymagają osobnego zlecenia. Przygotowanie plików
nie jest instalacją. Nie wykonuj commitów, pushów, reset/clean/stash, instalacji
pakietów ani uruchomień aplikacji w ramach dokumentacji lub lekcji.
Zachowuj wszystkie cudze zmiany. Oddziel opis zadania od zgody na implementację.

## Dowody i aktualizacja

Pisz po polsku. Potrzeby autora przekładaj na jasny opis techniczny; nie wymagaj
od niego specyfikacji. Opis implementacji wiąż ze ścieżką i symbolem.
Rozdziel obecność w kodzie, wynik uruchomienia i plan. Nie zgaduj powodów decyzji.
Większe zlecone zadania opisuj w docs/tasks: cel, zakres, ograniczenia, kryteria,
dowody, propozycje i pytania. Sam opis nie upoważnia do realizacji.
Przed aktualizacją sprawdź Git: HEAD, indeks, zmiany robocze, nowe pliki,
usunięcia i zmiany nazw oraz pending_source_paths z poprzedniego przeglądu.
Po przeglądzie zapisz datę/strefę, gałąź, pełny source_head, zakres, braki
oraz pending_source_paths. Jeśli baza nie jest dostępna, zaznacz ograniczenie.

## Rust i poufność

Czytaj własne .rs, Cargo.toml i potrzebny kontekst. Cargo.toml deklaruje pakiet
i zależności; Cargo.lock zapisuje rozwiązane wersje i zależności przechodnie,
nie dowodzi użycia bibliotek ani zgodności licencyjnej. Nie edytuj go przy lekcji.
Pomijaj target/, .git/, konfiguracje IDE, środowiska wirtualne i generowane dane.
Nie czytaj ani nie kopiuj .env, poświadczeń, kluczy i sekretów. Używaj placeholderów.
Nie wyłączaj walidacji dowodów, ścieżek i cytatów. Kod jest źródłem opisu,
nie dowodem skuteczności ani zgodności prawnej. Sprawdź linki i końcowy stan Git.

<!-- LEARNING-AGENT-AUTO:START -->
## Tryb edukacyjny i automatyczny nauczyciel po commitach

Gdy autor prosi o wyjaśnienie kodu, składni, metody lub wzorca, przeczytaj
LEARNING_AGENT.md. W trybie ręcznym agent może zapisywać materiały Markdown
w docs/learning, bez zmieniania kodu i bez uruchamiania aplikacji lub testów.

Automatyzację po commitach włącza autor osobnym poleceniem instalacji.
Automatyczny Codex analizuje wyłącznie migawkę wskazanego commitu w trybie
read-only i zwraca JSON. Skrypt tools/learning-agent waliduje odpowiedź,
zapisuje lekcje Markdown, JSON i SVG w docs/learning, buduje indeksy automatyczne
oraz lokalną stronę HTML i otwiera ją w BrowserOS. Jest to jawnie dozwolony
dodatkowy zestaw materiałów edukacyjnych, poza siedmioma dokumentami technicznymi.
Sam model nie wykonuje zapisu, publikacji ani otwierania przeglądarki.

Przeczytaj plan aplikacji i historię pojęć przed wyjaśnieniem. Oddzielaj obecne
działanie od planowanego efektu. Już opisanych konstrukcji w tym samym znaczeniu
nie rozwijaj ponownie; przypomnij ich zastosowanie i wskaż wcześniejszą kartę.
Nowe znaczenia tłumacz osobno. Na wyraźną prośbę autora powtórz wyjaśnienie.
Przygotowanie lub otwarcie lekcji nie potwierdza zrozumienia przez autora.

Domyślny agent dokumentacji nie przepisuje osobistych materiałów nauki podczas
zwykłego przeglądu. Pliki AUTO_INDEX i concepts/auto są widokami generowanymi;
własne uwagi zapisuj w indeksach manualnych lub osobnych notatkach.

Nie zmieniaj kodu aplikacji, konfiguracji, planu ani instrukcji w ramach
lekcji. Nie wykonuj commitów i pushów. Nie uruchamiaj aplikacji, buildów, testów,
instalacji ani usług. Instalacja/aktualizacja samego mechanizmu wymaga osobnego
zlecenia autora; samo przygotowanie plików nie uruchamia instalacji.
<!-- LEARNING-AGENT-AUTO:END -->

<!-- LEGAL-AGENT:START -->
## Tryb analizy prawnej

Wywołanie `tools/legal-agent/legal.sh` albo polecenie autora „tryb prawny” uruchamia
rolę opisaną w `LEGAL_AGENT.md`. W tej roli aplikacja jest tylko odczytywana.
Lokalny runtime może tworzyć raporty MD/JSON w `docs/legal/**` i lokalne pliki
stanu/podglądu w katalogu Git. To wyraźny wyjątek dotyczący formatu dokumentacji
tej roli, jeżeli pozostałe instrukcje domyślnie dopuszczają tylko Markdown.

Nie wykonuj zmian implementacji, commitów, pushów ani czynności prawnych za autora.
Agent dokumentacji zachowuje swoją rolę. Agent nauki zachowuje reguły i pamięć.
Pliki generowane w docs/legal aktualizuje agent prawny; inne role mogą je odczytać
i wskazać potrzebę ponownej analizy. Deklaracji autora w APP_PROFILE.md i
DECISIONS.md nie wolno zastępować automatycznymi wnioskami z kodu.

Przy czytaniu raportu sprawdź commit, zakres i daty źródeł. Brak ustaleń nie oznacza
wykonanego audytu ani zgodności. Dla zmian w przepływie danych, celu, dostawcy,
AI, dostępie lub licencjach uwzględnij potrzebę oceny przed wdrożeniem.
<!-- LEGAL-AGENT:END -->
