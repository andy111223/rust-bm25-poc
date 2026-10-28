# Standardy kodu, dokumentacji i weryfikacji

Wersja adaptacji: 2026-10-15. Opracowano z wykorzystaniem przekazanego przez
autora pliku `engineering-rules-general.md` oraz reguł dokumentowania projektu.
Dotyczy rust-bm25-poc: Rust edition 2024 i pomocnicze narzędzia Python. Obecność technologii w przykładzie nie potwierdza,
że jest używana w tym repozytorium.

## Zakres i egzekwowanie

`AGENTS.md` określa rolę i dozwolone działania agenta. Poniższe standardy nie
upoważniają do rozszerzania zadania. Sekcje mają oznaczony zakres:
**D** — dokumentacja, **I** — implementacja, **T** — testowanie, **W** — wydanie.
Domyślny agent dokumentacji stosuje D; reguły I/T/W opisuje i przywołuje wtedy,
gdy dotyczą dokumentowanego obszaru, ale nie rozpoczyna tych działań samodzielnie.

Reguły sprawdzalne automatycznie automatyzuj, gdy koszt jest uzasadniony.
Pozostałe kontroluj w przeglądzie. Brak automatycznego testu nie unieważnia
reguły. Nie dodawaj infrastruktury testowej przy samej aktualizacji dokumentów.

## 1. Architektura i ponowne użycie [I; ewidencja D]

- Dbaj o spójne odpowiedzialności komponentów i jedno miejsce utrzymywania
  wspólnej reguły biznesowej. Nie kopiuj progów lub warunków między warstwami,
  gdy są tą samą regułą. Podobieństwo dwóch fragmentów nie wymusza natychmiast
  nowej abstrakcji; wspólny moduł powinien mieć uzasadnioną odpowiedzialność.
- Przed dodaniem wspólnego zachowania sprawdź rejestr w `docs/CODE_MAP.md`.
  Użyj istniejącego rozwiązania, jeśli pasuje. Uzasadnij istotne odstępstwo.
  Nowy wspólny komponent dopisz do rejestru razem ze zmianą.
- Granice integracji są jawne: odpowiedzialności stron, formaty danych, pola
  wymagane/opcjonalne, jednostki i błędy. Stosuj modele danych i walidację
  odpowiednie dla języka. Kilka kanałów komunikacji jest dopuszczalne, jeśli
  każdy ma zrozumiałą rolę i kontrakt.
- Agent dokumentacji wskazuje zależności, rozbieżności i potencjalne duplikaty.
  Ich naprawa jest osobnym zadaniem implementacyjnym.

## 2. Typy i czytelność [I]

- Używaj możliwości danego języka do jawnego opisania danych i obsługi braku
  wartości. Nie obchodź kontroli typów bez konkretnego powodu i walidacji.
- W Rust jawnie modeluj dane oraz błędy przez typy i `Result`; nie dodawaj
  `unsafe` ani panic bez uzasadnienia.
- W Pythonie stosuj adnotacje i walidację na granicach tam, gdzie pomagają;
  same adnotacje nie walidują danych przychodzących podczas działania.
- Jeśli występuje TypeScript, preferuj `unknown` i zawężanie zamiast `any`;
  asercje i operator non-null wymagają uzasadnienia. Nie przenoś tej składni
  dosłownie do C#, Pythona lub Kotlina.
- Uruchamiaj istniejące sprawdzanie typów, analizatory i lintery odpowiednie
  do zmienianego kodu. Zmiana samych dokumentów wymaga kontroli dokumentów,
  a nie automatycznie pełnego zestawu testów aplikacji.
- Komentarz wyjaśnia cel lub powód nietrywialnego rozwiązania. Nie opisuj
  mechanicznie każdej funkcji. Trwałe decyzje z datą i kontekstem zapisuj
  w DECISIONS; unikaj duplikowania całej historii w komentarzach.

## 3. Dowody i testy [T; raportowanie D]

- Rozróżniaj obserwację działania, wynik testu i wniosek z analizy kodu.
  Analiza źródeł może potwierdzić obecność mechanizmu, nie jego skuteczność
  w docelowym środowisku. Dokumentuj źródło twierdzenia i ograniczenia.
- Przed naprawą błędu uzyskaj jego reprodukcję, zawodzący test lub inny
  wiarygodny dowód. Jeśli to niemożliwe, nazwij ograniczenie wprost.
- Dla testu regresji w miarę możliwości wykaż porażkę przed naprawą i sukces
  po niej. Dla ważnego mechanizmu kontroli sprawdź, czy celowo wprowadzony błąd
  jest wykrywany. Nie wymagaj testowania z mutantem każdej zmiany dokumentacji
  ani każdego twierdzenia. Takie próby nie powinny naruszać pracy autora.
- Testuj poprawny przypadek i istotny przypadek błędu/odrzucenia. Dobierz
  przypadki brzegowe i środowiska do ryzyka oraz rzeczywistej zmiany.
- Raport zestawu testów podaje liczbę sukcesów, błędów i pominięć. Gdy narzędzie
  nie raportuje części danych, oznacz je jako niepodane, zamiast dopisywać zero.
  Pojedynczą ręczną próbę opisz jako pojedynczą próbę, nie pełną bramkę wydania.
- Zapisuj datę, wersję kodu i istotne warunki: np. wersję Rust/Cargo,
  system, wersję serwera. Bazę danych i miejsce na dysku zapisuj, gdy mają
  znaczenie dla scenariusza; nie wymagaj ich w każdym raporcie.
- Wyniki autora oznacz jako zgłoszone przez autora. Po istotnej zmianie kodu
  zachowaj poprzedni wynik z jego kontekstem i zaznacz potrzebę ponownej próby.

## 4. Kontrola długu technicznego [I/T, opcjonalnie]

Automatyczny limit zastanych problemów może zapobiegać ich przyrostowi
(„zapadka”). Wprowadzaj go dla konkretnego mierzalnego problemu, jeśli projekt
tego potrzebuje; nie uruchamiaj całego systemu zapadek jako warunku dokumentacji.

Przy wdrożeniu ustal metrykę, zakres i rzeczywistą bazę. Nie zwiększaj budżetu
na zapas; po zmniejszeniu problemu obniż limit. Dla nowego kodu dąż do braku
nowych naruszeń. Uzasadnione wyjątki i zmiany limitu są jawną decyzją autora.
Sprawdź skuteczność kontroli na reprezentatywnym naruszeniu. Różne metryki
(np. ostrzeżenia i rozmiar builda) wymagają różnych zasad, bez mechanicznego
stosowania jednego licznika do wszystkiego.

## 5. Dokumentacja i zadania [D]

- Repozytorium przechowuje uzgodnione reguły, kontekst i decyzje. Ustalenia
  przekazane w czacie lub zwykłej notatce agent przenosi do właściwego dokumentu
  z oznaczeniem źródła. Nie musi otrzymać tekstu napisanego językiem technicznym.
- Kod opisuje implementację; wymagania opisują zamierzony efekt; test i log
  dokumentują obserwację w określonych warunkach. Nie zastępuj jednego drugim.
- Decyzja ma datę, autora decyzji, powód i źródło, jeśli są znane. Oddzielaj
  decyzje potwierdzone, zastane rozwiązania z nieznanym uzasadnieniem i propozycje.
  Nie przypisuj autorstwa decyzji osobie/agentowi, który jedynie zapisał wpis.
- Dokumentację aktualizuj w ramach tego samego etapu pracy co kod: przed
  uznaniem etapu za ukończony. Może to być wspólny commit lub powiązane osobne
  commity; ważna jest spójność stanu końcowego, nie liczba commitów.
- Dla twierdzeń o implementacji podawaj ścieżkę i symbol. Dla wyników działania
  podawaj wynik testu, obserwację albo raport autora z ograniczeniami.
- Zewnętrzne twierdzenia istotne dla projektu (np. ograniczenia SDK lub zasady
  platformy) opieraj na właściwym źródle: adresie, tytule i wersji/dacie, jeśli
  dostępne. Nie dodawaj niepotrzebnych faktów prawnych lub produktowych.
- Większe zlecone/wybrane zadanie ma samodzielny opis Markdown w `docs/tasks/`.
  Jeśli brakuje opisu od programisty, tworzy go agent zgodnie z AGENTS.
  Zapisuje cel, problem, zakres, potwierdzone miejsca w kodzie, ograniczenia,
  kryteria odbioru i pytania. Nie odnosi się do „poprzedniej wiadomości”.
- Opisanie zadania nie upoważnia do implementacji. Propozycje agenta nie są
  automatycznie decyzjami autora. Nie zamieniaj domysłów w wymagania.
- Pisz dla odbiorcy: wniosek na początku, krótkie akapity, daty bezwzględne,
  wartości z jednostkami, wyjaśnienie ważnych pojęć i mało powtórzeń.

## 6. Współpraca i wydania [D/I/T/W zależnie od zadania]

- Przeczytaj instrukcje przed pracą. Zachowuj cudze zmiany i nie deklaruj
  wykonania czynności bez wyniku. Ograniczenia dostępu i weryfikacji podawaj jawnie.
- Przy równoległej pracy uzgodnij odpowiedzialności za pliki, testy i integrację.
  Nie uruchamiaj obciążających procesów kolidujących z pracą innych sesji.
- Zmiany standardów wymagają wyraźnego zlecenia właściciela projektu; zwykłe
  zadanie dokumentacyjne nie obejmuje ich samowolnego przepisywania.
- Zapis zadania, propozycja innego agenta i gotowa dokumentacja nie zastępują
  upoważnienia autora do wdrożenia, publikacji lub zapisu w produkcji.
- Reguły wydania nie oznaczają, że agent dokumentacji ma publikować projekt
  albo przesuwać gałąź główną. W domyślnej roli nie wykonuje commitów ani pushów.
