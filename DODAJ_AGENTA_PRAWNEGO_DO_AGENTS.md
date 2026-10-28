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
