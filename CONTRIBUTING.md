# Jak pracujemy

## Tryb ścieżki pracy (obowiązuje od 26.11.2026, ADR-0008)

Do obrony pracy inżynierskiej realizujemy ścieżkę pracy: kolejność i minimum etapów
w tabeli „Kolejność prac” na początku `docs/dokumentacja/roadmapa.md`, bramki pracy
`G<nr>p` w `docs/dokumentacja/testy.md` (sekcja 3a). Ten tryb zmienia zasady niżej tylko
w poniższych punktach; pozostałe obowiązują. Szczegóły dla asystenta AI: `CLAUDE.md`,
sekcja „Tryb ścieżki pracy”.

- **1–3 PR-y na etap** (zamiast „jeden punkt zakresu na PR”), plus mały PR z dowodem
  bramki po zielonym CI na `main`.
- **Asystent w sesji w chmurze** wypycha gałąź `claude/E<nr>-<opis>` (commity mogą być
  niepodpisane), otwiera właściwy PR z etykietą etapu i poprawia go do zielonego CI.
  Właściciel przegląda i scala przez **Squash and merge** w GitHubie: commit na `main`
  podpisuje GitHub, więc wymóg podpisanych commitów w rulesecie jest spełniony.
- **Przegląd:** CI, bramki pracy i CodeQL; bez szkiców testowych, bez niezależnego
  recenzenta (wyjątek: zmiany kontroli bramek i sekretów, za zgodą właściciela), bez
  triażu Graphify (wyłączony do końca pracy).
- **CI szybsze:** obrazy w PR tylko przy zmianie zależności i `Dockerfile`, bramka na macOS
  tylko przy zmianach skryptów powłoki; na `main` zawsze wszystko (`testy.md`, sekcja 4).
- **Dokumentacja i statusy** aktualizowane przy domknięciu etapu, nie w każdym PR.

Zasady poniżej obowiązują w całości po powrocie do ścieżki produktu.

## Zasady pełne (ścieżka produktu)

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
