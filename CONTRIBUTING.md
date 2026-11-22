# Jak pracujemy

- **Roadmapa rządzi kolejnością.** Każdy PR realizuje jeden punkt zakresu prac etapu
  (np. E1.6). Etap kończy się bramką jakości; bez zielonej bramki nie zaczynamy etapu
  zależnego.
- **Gałęzie:** `feat/E<nr>-<opis>`, `fix/E<nr>-<opis>`, `docs/E<nr>-<opis>`.
  Gałąź `main` jest chroniona: tylko przez PR, wymagane zielone CI, podpisane commity,
  liniowa historia, zakaz force-push.
- **Commity:** [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `ci:`), podpisane kluczem SSH.
- **Przed pushem:** `make lint audit typecheck imports test`. Narzędzia do `make audit`
  w tych samych przypiętych wersjach co CI instaluje jednorazowo `make tools` (do `.tools/`). Hooki pre-commit (`make install`)
  sprawdzają format, YAML, duże pliki i sekrety przy każdym commicie.
- **Granice modułów:** moduły pakietu `goatcash` komunikują się wyłącznie przez
  `goatcash.<moduł>.api`; implementacja leży w `goatcash.<moduł>._impl`. Pilnuje tego
  import-linter w CI.
- **Decyzje architektoniczne** zapisujemy jako ADR w `docs/adr/` (szablon `0000-szablon.md`).
- **Sekrety:** nigdy w kodzie ani w `.env` w repo. Nowy sekret aplikacji trafia do
  `infra/secrets/<env>.enc.yaml` przez `sops`.

## Przegląd zmian

Każda zmiana przechodzi kolejno:

1. **Bramka lokalnie i w trybie CI:** `make gate G=<nr>` oraz `CI=true make gate G=<nr>`.
2. **Statyczna kontrola:** `make audit` (shellcheck, hadolint, actionlint, zizmor).
3. **Prawdziwe CI** na GitHubie, w tym bramka na macOS z systemowym bash 3.2 i narzędziami
   BSD (środowisko właściciela). Zmiany przygotowane przez asystenta AI są najpierw
   testowane na gałęzi `claude/…` w szkicu PR, który jest potem zamykany bez scalenia.
4. **Przegląd krytyczny:** dla każdej kontroli pytanie „jak ją obejść?”; przy zmianach
   bezpieczeństwa także niezależny przegląd (inny agent albo Copilot), który nie pisał kodu.

### Uwagi automatycznych recenzentów (Graphify, Copilot)

| Rodzaj uwagi                                     | Co robimy                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------- |
| bezpieczeństwo, poprawność, bramka jakości       | naprawa przed scaleniem, z testem, który bez poprawki pada                |
| fałszywa                                         | odpowiedź z dowodem (komenda i wynik), wątek rozwiązany                   |
| drobna (kosmetyka, mało prawdopodobny przypadek) | zgłoszenie z etykietą `tech-debt`, wątek rozwiązany linkiem do zgłoszenia |

Wynik triażu każdego PR etapu trafia do raportu bramki (`docs/gates/G<nr>.md`).
