# Rejestr ustaleń

Plik generowany z raportów dostępnych w bieżącej historii Git. Własne wyjaśnienia zapisuj w DECISIONS.md albo poleceniem decide. Decyzje autora są deklaracjami, a nie automatycznym wynikiem audytu.

| ID | Temat | Priorytet | Pewność | Stan | Ostatnia obserwacja |
|---|---|---|---|---|---|
| LEGAL-2D8AB7D288 | Przygotuj zestawienie licencji zależności przed udostępnieniem projektu | niski | wysoka | Otwarte | `5f0023185cec` |

### LEGAL-2D8AB7D288 — Przygotuj zestawienie licencji zależności przed udostępnieniem projektu

Priorytet: **niski** · Pewność: **wysoka** · Rekomendacja · Stan: Otwarte

**Obserwacja:** Cargo.toml deklaruje cztery bezpośrednie zależności, a Cargo.lock zapisuje także zależności przechodnie. Przekazane pliki konfiguracji nie zawierają tekstów ich licencji. Nie ustalono warunków korzystania ani obowiązków dotyczących planowanego wydania.

**Kiedy ma zastosowanie:** Zakres sprawdzenia zależy od rzeczywiście wykorzystywanych składników, ich dokładnych wersji oraz tego, czy autor udostępni źródła, program wynikowy lub zintegruje projekt z inną aplikacją. Konkretne wymagania należy ustalić z właściwych tekstów licencji.

**Prostymi słowami:** Lista bibliotek pomaga znaleźć warunki ich używania, ale sama nie jest potwierdzeniem uprawnień. Zestawienie licencji pozwoli ustalić na przykład, jakie informacje trzeba dołączyć do wydania. Brak tekstów licencji w tej migawce nie dowodzi braku uprawnień.

**Dowody w migawce**

- `Cargo.toml` (po zmianie), linie 6–10:

> [dependencies]
> anyhow = "1.0.104"
> serde = { version = "1.0.229", features = ["derive"] }
> serde_json = "1.0.154"
> tantivy = "=0.27.0"

- `Cargo.lock` (po zmianie), linie 15–17:

> name = "anyhow"
> version = "1.0.104"
> source = "registry+https://github.com/rust-lang/crates.io-index"

**Po stronie kodu**

- Przy przygotowaniu wydania zestawić składniki rzeczywiście wykorzystywane dla wybranej platformy i konfiguracji z wersjami zapisanymi w Cargo.lock, uwzględniając zależności przechodnie. Weryfikacja: Zestawienie wskazuje nazwę, wersję, źródło i sposób obecności każdego składnika w planowanym wydaniu.

**Po stronie autora / organizacji**

- Określić sposób udostępniania projektu i sprawdzić teksty LICENSE oraz ewentualne NOTICE w źródłach dokładnych wersji składników. Weryfikacja: Zapisano sposób dystrybucji, pochodzenie tekstów licencji oraz wynik sprawdzenia warunków i wymaganych informacji dla wydania.

**Brakujące informacje**

- Czy planujesz udostępniać źródła, gotowy program, czy wykorzystywać projekt wyłącznie wewnętrznie?

**Dowody potrzebne do rozstrzygnięcia**

- Zestawienie składników planowanego wydania z dokładnymi wersjami i tekstami licencji.
- Udokumentowana ocena warunków dla wybranego sposobu dystrybucji oraz przygotowane wymagane informacje licencyjne; materiał wymaga ponownej oceny, nie zamyka ustalenia automatycznie.
