# Sekrety (SOPS + age)

Pliki `<środowisko>.enc.yaml` są zaszyfrowane SOPS kluczem age danego środowiska
i mogą leżeć w publicznym repozytorium. Reguły są w `.sops.yaml`.

| Plik                        | Klucz          | Gdzie jest klucz prywatny                                                        |
| --------------------------- | -------------- | -------------------------------------------------------------------------------- |
| `local.enc.yaml`            | age local      | Bitwarden („age local”) + `~/.config/sops/age/keys.txt` na komputerze dewelopera |
| `staging.enc.yaml` (E3)     | age staging    | Bitwarden („age staging”) + serwer staging                                       |
| `production.enc.yaml` (E16) | age production | Bitwarden („age production”) + serwer produkcyjny                                |

Klucz `local` leży w `~/.config/sops/age/keys.txt`. Na macOS SOPS domyślnie szuka go
gdzie indziej (`~/Library/Application Support/sops/age/`), więc w `~/.zprofile` ustaw:

```bash
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

Komendy:

```bash
sops infra/secrets/local.enc.yaml          # edycja (otwiera edytor, zapis szyfruje)
sops -d infra/secrets/local.enc.yaml       # podgląd odszyfrowany (nie zapisuj do pliku w repo)
```

Wyciek klucza = natychmiastowa rotacja u dostawcy i wpis w dzienniku incydentów
(sekcja 8 Fundamentów, warstwa 5).
