# Wybór modułu przez ścieżkę importowania

Klucz: `python.import.search-path-selection` · Python · importowanie modułów

Status: przygotowano — nie potwierdzono przeczytania.

sys.path określa miejsca szukania modułów. Dodanie katalogu na początku listy pozwala wskazać, skąd ma zostać znaleziony moduł o danej nazwie.

Skrypt używa tej samej nazwy agent dla dwóch narzędzi znajdujących się w różnych katalogach.

````
sys.path.insert(0, '/example/tools/learning-agent')
import agent as a
````

Przykład pomocniczy: katalog otrzymuje pierwszeństwo wyszukiwania, a a staje się skrótem dla zaimportowanego modułu.

Częste nieporozumienie: Zmiana sys.path nie zastępuje automatycznie modułu już zapamiętanego przez interpreter. W tej lekcji osobne procesy oddzielają importy.

[Lekcja źródłowa](../../lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md)
