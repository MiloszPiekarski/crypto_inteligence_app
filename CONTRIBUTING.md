# Jak pracujemy

- **Roadmapa rządzi kolejnością.** Każdy PR realizuje jeden punkt zakresu prac etapu
  (np. E1.6). Etap kończy się bramką jakości; bez zielonej bramki nie zaczynamy etapu
  zależnego.
- **Gałęzie:** `feat/E<nr>-<opis>`, `fix/E<nr>-<opis>`, `docs/E<nr>-<opis>`.
  Gałąź `main` jest chroniona: tylko przez PR, wymagane zielone CI, podpisane commity,
  liniowa historia, zakaz force-push.
- **Commity:** [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `ci:`), podpisane kluczem SSH.
- **Przed pushem:** `make lint typecheck imports test`. Hooki pre-commit (`make install`)
  sprawdzają format, YAML, duże pliki i sekrety przy każdym commicie.
- **Granice modułów:** moduły pakietu `goatcash` komunikują się wyłącznie przez
  `goatcash.<moduł>.api`; implementacja leży w `goatcash.<moduł>._impl`. Pilnuje tego
  import-linter w CI.
- **Decyzje architektoniczne** zapisujemy jako ADR w `docs/adr/` (szablon `0000-szablon.md`).
- **Sekrety:** nigdy w kodzie ani w `.env` w repo. Nowy sekret aplikacji trafia do
  `infra/secrets/<env>.enc.yaml` przez `sops`.
