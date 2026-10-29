# Zbiór ścieżek i sprawdzanie obecności

Klucz: `python.set.comprehension-membership-intersection` · Python · kolekcje

Status: przygotowano — nie potwierdzono przeczytania.

Zbiór przechowuje niepowtarzające się elementy. Zapis z for wewnątrz klamer tworzy go z kolejnych wartości, in sprawdza obecność, a & znajduje elementy wspólne.

Kontrola potrzebuje wiedzieć, czy dana ścieżka trafiła do materiałów, bez zależności od kolejności wpisów.

````
paths = {x['path'] for x in [{'path': 'src/main.rs'}, {'path': 'Cargo.toml'}]}
blocked = {'target/generated.rs', '.env'}
common = blocked & paths
````

Przykład pomocniczy: paths zawiera dwie ścieżki. common jest pustym zbiorem, bo żadna zabroniona ścieżka nie występuje w paths. Pusty zbiór ma wartość logiczną fałszu, stąd assert not common sprawdza brak przecięcia.

Częste nieporozumienie: Zbiór usuwa powtórzenia. Taka kontrola nie wykryje, że manifest zawiera dwa wpisy tej samej ścieżki.

[Lekcja źródłowa](../../lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md)
