# Plan roboczy

Źródło celu: zlecenie autora z 2026-10-29. Cel: eksperyment BM25 w Rust,
potencjalnie później wykorzystany w XREALPresentation. Nie ma jeszcze integracji.

Propozycje etapów wymagające ustalenia przed implementacją:
1. Uzgodnić wejściowy format dokumentów, tokenizację i format wyników.
2. Zaimplementować indeksowanie i wyszukiwanie BM25 na danych syntetycznych.
3. Zmierzyć jakość rankingu i koszty działania na ustalonym zbiorze.
4. Dopiero po ocenie ustalić sposób ewentualnej integracji i granice danych.

Obecny main nie realizuje tych etapów. Nie ustalono API, trwałości indeksu,
metryk odbioru ani sposobu komunikacji z inną aplikacją.
