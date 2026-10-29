# Narzędzia lokalne

Przeniesiono kod narzędzi i neutralne instrukcje z XREALPresentation (odczyt).
Nie przeniesiono lokalnych konfiguracji, kolejek, timerów, logów, raportów,
historii nauki, decyzji ani profilu aplikacji. Przykłady w katalogach tools są
przykładami schematu/testów, a nie historią tego projektu.
SOURCES.json to skopiowany neutralny rejestr PL/UE; jego daty pochodzą ze źródła,
nie są datą weryfikacji w tym projekcie. Aktualności prawa tutaj nie badano.

## Stan informacji po przeglądzie 2026-10-29

Poniższy opis migracji i wyniki offline są zapisem historycznym adaptacji,
nie nową weryfikacją HEAD. Podczas aktualizacji dokumentacji nie uruchamiano
instalatorów, doctor, testów ani modeli i nie sprawdzano lokalnego runtime.
Istnieją już lokalne materiały obu agentów; ich zakres i commit opisuje
[PROJECT_STATUS.md](PROJECT_STATUS.md). Wcześniejsze stwierdzenia o braku
instalacji i analiz dotyczą etapu przygotowania, a nie ustalonego stanu bieżącego.

## Wymagania i instalacja

Potrzebne: Git, Python 3 (biblioteka standardowa), Codex CLI z aktywnym dostępem
do modelu. BrowserOS jest używany do podglądu; można wyłączyć auto-open lub
skonfigurować przeglądarkę. systemd --user jest potrzebny tylko dla opcjonalnych
timerów, których poniższe polecenia nie instalują. Cargo nie jest potrzebne
narzędziom analizy statycznej. Nie instalowano zależności.

Polecenia do późniejszego wykonania przez autora:

```bash
cd /home/andrzej/Desktop/dev/unity/rust-bm25-poc
bash tools/learning-agent/learn.sh install --no-hook
bash tools/legal-agent/legal.sh install
bash tools/learning-agent/learn.sh configure --auto-open off
bash tools/legal-agent/legal.sh configure --auto-open off
bash tools/learning-agent/learn.sh doctor
bash tools/legal-agent/legal.sh doctor
```

`--no-hook` pozwala najpierw korzystać ręcznie. Opcjonalna instalacja nauczyciela
po commitach: `bash tools/learning-agent/learn.sh install` (bez --timer).
Instalator zachowuje istniejący hook i dodaje swój blok; własny core.hooksPath
lub dodatkowy worktree wymagają --no-hook. Agent prawny nie zmienia hooków.
Instalatory zapisują runtime/config w lokalnym katalogu Git, uzupełniają wymagane
pliki startowe i oznaczone bloki AGENTS.md. Pliki startowe są już przygotowane.

Pierwsza lekcja, z istniejącego pliku Rust (to polecenie wywoła model):

```bash
bash tools/learning-agent/learn.sh now --file src/main.rs
```

Lekcja analizuje migawkę HEAD, a nie niezapisane zmiany robocze.
Dostępność CLI, modelu, logowania i przeglądarki sprawdza doctor; nie były
potwierdzane w tej migracji. Nie uruchamiaj baseline prawnego bez uzupełnienia profilu.

## Adaptacja i weryfikacja offline — 2026-10-29

Oba selektory obsługują .rs, Cargo.toml i Cargo.lock. Manifest deklaruje pakiet
oraz zależności; lockfile służy analizie rozwiązanych wersji, w tym zależności
przechodnich. Nie jest własnym algorytmem ani dowodem użycia lub licencji.
Nie należy go pomijać przy ocenie zależności ani zmieniać podczas nauki.

Sprawdzono wybór zmian, jawne pliki, kontekst migawki nauczyciela oraz cele,
kontekst roboczy i dodatkowe pliki pakietu agenta prawnego. target/ jest pomijany
w dowolnym komponencie ścieżki, także gdy wpisano go w plan_files nauczyciela.
Wykluczenia sekretów zachowano; walidatory schematów, cytatów i dowodów pozostają.

Wykonane polecenia:

```bash
python3 -m unittest discover -s tools/learning-agent/tests -q
python3 -m unittest discover -s tools/legal-agent/tests -q
python3 tools/tests/check_rust_selection.py
```

Wynik: nauczyciel 45/45, prawny 42/42; brak błędów i pominięć.
Dwie dodatkowe syntetyczne próby selekcji, instalatorów i kontekstu przeszły.
Instalatory sprawdzono wyłącznie w jednorazowych repozytoriach /tmp, bez timerów.
Testy używają atrap odpowiedzi; nie wywołują rzeczywistego modelu.
Nie jest to weryfikacja jakości lekcji, prawna ocena projektu ani test Rust.
