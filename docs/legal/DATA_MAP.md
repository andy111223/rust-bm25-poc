# Mapa danych — obserwacje z kodu

Mapa jest przyrostowa. Wpisy zachowują commit ostatniej obserwacji; brak wpisu w późniejszym raporcie nie potwierdza usunięcia przepływu. Pełny obraz wdrożenia wymaga potwierdzenia autora.

## Przygotowanie sztucznych plików do sprawdzenia reguł wyboru materiałów dla agentów.

Stałe tekstowe w tools/tests/check_rust_selection.py. → Pliki pod ścieżką katalogu utworzonego przez tempfile.TemporaryDirectory().

Dane: Treści zdefiniowane w słowniku contents: minimalne źródło Rust, pliki Cargo, teksty oznaczające pliki generowane i pliki wykluczane oraz syntetyczny plan. W tych wartościach nie stwierdzono rzeczywistych poświadczeń ani danych konkretnych osób.

Przechowywanie: Kod przewiduje katalog tymczasowy zarządzany przez blok with, ze sprzątaniem po wyjściu z bloku. Nie potwierdzono wykonania ani usunięcia pozostałości po awarii.

Commit: `5f0023185cec49664718df16f27f367a412e3619`. Pewność: wysoka.

- `tools/tests/check_rust_selection.py` (po zmianie), linie 16–17:

> with tempfile.TemporaryDirectory() as tmp:
>     root = pathlib.Path(tmp)

- `tools/tests/check_rust_selection.py` (po zmianie), linie 26–29:

>     for name, text in contents.items():
>         p = root / name
>         p.parent.mkdir(parents=True, exist_ok=True)
>         p.write_text(text)

Do ustalenia:

- Nie przekazano wyniku uruchomienia potwierdzającego zapis i sprzątnięcie katalogu.
- Nie oceniono ewentualnych dodatkowych zapisów wykonywanych przez importowane funkcje agentów; ich implementacji nie ma w wejściu.

## Wypisanie komunikatu demonstracyjnego.

Literał tekstowy w funkcji main. → Standardowe wyjście procesu.

Dane: Stały tekst „Hello, world!”; bez danych użytkownika w tym wywołaniu.

Przechowywanie: Kod nie określa przechowywania wyjścia. Ewentualne zachowanie go przez terminal lub przekierowanie nie zostało ustalone.

Commit: `5f0023185cec49664718df16f27f367a412e3619`. Pewność: wysoka.

- `src/main.rs` (po zmianie), linie 1–3:

> fn main() {
>     println!("Hello, world!");
> }

Do ustalenia:

- Nie potwierdzono uruchomienia ani sposobu obsługi standardowego wyjścia w środowisku autora.

## Przygotowanie syntetycznych plików do sprawdzenia wyboru materiału dla agentów.

Słownik contents zdefiniowany w skrypcie. → Pliki wewnątrz katalogu tymczasowego testu.

Dane: Przykładowy kod Rust, pliki Cargo, plan oraz sztuczne pliki reprezentujące dane generowane i poufne. Ich zawartość nie dowodzi użycia rzeczywistych poświadczeń.

Przechowywanie: TemporaryDirectory przewiduje sprzątanie katalogu po zakończeniu bloku. Nie potwierdzono wykonania ani faktycznego usunięcia plików.

Commit: `5f0023185cec49664718df16f27f367a412e3619`. Pewność: wysoka.

- `tools/tests/check_rust_selection.py` (po zmianie), linie 16–17:

> with tempfile.TemporaryDirectory() as tmp:
>     root = pathlib.Path(tmp)

- `tools/tests/check_rust_selection.py` (po zmianie), linie 26–29:

>     for name, text in contents.items():
>         p = root / name
>         p.parent.mkdir(parents=True, exist_ok=True)
>         p.write_text(text)

Do ustalenia:

- Nie sprawdzono zachowania importowanych modułów agentów ani plików tworzonych przez ich funkcje poza widocznymi instrukcjami skryptu.
- Brak wyniku uruchomienia testu.

