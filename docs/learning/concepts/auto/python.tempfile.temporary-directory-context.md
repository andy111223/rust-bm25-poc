# Katalog tymczasowy zarządzany przez with

Klucz: `python.tempfile.temporary-directory-context` · Python · biblioteka standardowa

Status: przygotowano — nie potwierdzono przeczytania.

Kod otrzymuje katalog do pracy, a zarządzający nim obiekt sprząta go przy opuszczeniu bloku with w zwykłym przebiegu i podczas obsługi wyjątków.

Sztuczne pliki i repozytorium mogą służyć jako dane kontroli bez tworzenia ich w źródłach aplikacji.

````
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
````

Przykład pomocniczy: tmp jest tekstem ścieżki, a root obiektem ułatwiającym operacje na niej. Wcięcie określa czas korzystania z katalogu.

Częste nieporozumienie: with nie ogranicza uprawnień wywoływanych funkcji do tego katalogu. Bez kodu agentów nie można potwierdzić wszystkich miejsc ich zapisu.

[Lekcja źródłowa](../../lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md)
