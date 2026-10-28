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
