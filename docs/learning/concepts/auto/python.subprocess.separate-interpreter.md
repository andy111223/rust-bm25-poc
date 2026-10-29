# Osobny proces interpretera

Klucz: `python.subprocess.separate-interpreter` · Python · biblioteka standardowa

Status: przygotowano — nie potwierdzono przeczytania.

Program może uruchomić drugi program z własną pamięcią. Tutaj subprocess.run uruchamia nowy interpreter Pythona dla każdego narzędzia.

Oba narzędzia importują moduł o nazwie agent. Osobne procesy oddzielają ich pamięć importów i zmienne modułów.

````
subprocess.run([sys.executable, 'check.py', 'learning-agent'], check=True)
````

Przykład pomocniczy: uruchamia check.py w bieżącym interpreterze jako nowy proces, przekazuje argument i czeka na koniec. Niezerowy kod zakończenia powoduje wyjątek.

Częste nieporozumienie: Osobny proces nie oznacza równoległości ani pełnej izolacji systemu plików. W skrypcie procesy uruchamiane są kolejno.

[Lekcja źródłowa](../../lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md)
