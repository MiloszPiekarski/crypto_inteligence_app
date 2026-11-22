# Bezpieczeństwo

## Zgłaszanie podatności

Nie zgłaszaj podatności w publicznym issue. Użyj prywatnego zgłoszenia GitHub:
zakładka **Security → Report a vulnerability** w tym repozytorium
(<https://github.com/MiloszPiekarski/crypto_inteligence_app/security/advisories/new>).

Potwierdzamy zgłoszenie w ciągu 7 dni i informujemy o planie naprawy. Prosimy o
nieujawnianie szczegółów przed wydaniem poprawki.

## Pięć warstw ochrony przed wyciekiem sekretów

1. **pre-commit z gitleaks** lokalnie: blokuje commit z czymś, co wygląda na sekret.
2. **GitHub Secret Scanning + Push Protection**: blokuje push.
3. **gitleaks w CI** na każdym PR, z pełną historią.
4. **Brak danych w repo**: żadnych zrzutów bazy, `.parquet`, `.csv` z danymi
   użytkowników ani logów (`.gitignore`, limit rozmiaru plików).
5. **Procedura incydentu**: wyciek = natychmiastowa rotacja klucza u dostawcy (nie tylko
   usunięcie z historii) i wpis w dzienniku incydentów.

## Gdzie są sekrety

| Klasa                         | Miejsce                                        |
| ----------------------------- | ---------------------------------------------- |
| Sekrety infrastruktury        | GitHub Environments z wymaganym zatwierdzeniem |
| Sekrety aplikacji             | `infra/secrets/<env>.enc.yaml` (SOPS + age)    |
| Klucze API giełd użytkowników | baza executora, szyfrowanie kopertowe (od E14) |
| Lokalny development           | `.env.local` poza repo (wzór: `.env.example`)  |
