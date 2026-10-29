# Sprawdzenie warunku i oczekiwanego wyjątku

Klucz: `python.testing.assert-and-expected-exception` · Python · kontrola poprawności

Status: przygotowano — nie potwierdzono przeczytania.

assert przerywa wykonanie, gdy warunek nie jest spełniony. try/except/else pozwala osobno sprawdzić sytuację, w której wywołanie powinno zgłosić określony wyjątek.

Skrypt sprawdza zarówno obecność i nieobecność plików, jak i odrzucenie jawnego żądania zabronionego pliku.

````
try:
    operation()
except RuntimeError:
    pass
else:
    raise AssertionError('expected rejection')
````

Przykład pomocniczy: RuntimeError jest oczekiwanym wynikiem. Brak wyjątku powoduje jawne niepowodzenie. Inny wyjątek przechodzi dalej.

Częste nieporozumienie: Przechwycenie samego typu wyjątku nie dowodzi jego przyczyny. Instrukcje assert mogą też zostać wyłączone przez optymalizację interpretera.

[Lekcja źródłowa](../../lessons/5f0023185cec4966-8f8529ed59-p001/lesson.md)
