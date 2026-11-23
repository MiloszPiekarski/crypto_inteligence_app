# Lekcje: błędy asystenta, których nie powtarzamy

Asystent czyta ten plik na początku każdej rozmowy (`docs/start-nowej-rozmowy.md`)
i dopisuje do niego nowe pozycje przy zamknięciu etapu. Każda pozycja: co się stało →
jak tego unikamy.

## E0–E1

- Wersja akcji GitHub, która nie istniała → wersje sprawdzamy (`git ls-remote`, dokumentacja)
  i przypinamy do SHA.
- Nazwa obrazu GHCR z wielkimi literami → GHCR wymaga małych liter.
- Odejście od dokumentacji „po cichu” (bramka jako `.sh` zamiast `gates/G<nr>.yaml`) →
  najpierw sprawdzamy, co mówi dokumentacja; odstępstwo tylko jawne i zapisane.
- Wyjątek w gitleaks dla `*.enc.yaml`, który otwierał lukę → wyjątków w skanerach nie
  dodajemy bez dowodu, że są potrzebne.
- Kontrola łatwa do obejścia (`sops_check` sprawdzał tylko prefiks `ENC[`) → przy każdej
  kontroli pytanie „jak ją obejść?”.
- Skrypt testowany ze ścieżką bezwzględną, właściciel użył względnej (`make tools`) →
  testujemy dokładnie tak, jak uruchomi to właściciel.
- `doctor.sh` zepsuty przez `.venv` w katalogu projektu → testujemy w katalogu projektu.
- Raport bramki gubił linię FAIL → wynik musi być czytelny dla właściciela.
- Za dużo rund poprawek pod dyktando bota → triaż (`CLAUDE.md`, punkt 5).

## E2

- Oczekiwane wyniki w instrukcjach podane z głowy (liczba testów migracji, liczba linii) →
  każdą oczekiwaną liczbę bierzemy z faktycznego przebiegu, nie szacujemy.
- Polecenie ustawienia `DOCKER_HOST` u właściciela, niepotrzebne i psujące test → nie
  dajemy właścicielowi zmian środowiska, których nie przetestowaliśmy w jego układzie.
- Zamiana tekstu w tabeli po cichu nie zadziałała, bo Biome przeformatował Markdown
  (także `__x__` → `**x**`) → każda zamiana w skrypcie ma `assert`; po `pre-commit`
  sprawdzamy wynikowy diff.
- Szkic PR na gałęzi opartej o niescalony commit: konflikt, CI się nie uruchomiło → szkic
  zawsze na aktualnym `main` (albo na dokładnie tym commicie, na który właściciel nałoży łatkę).
- `version_locations` w `alembic.ini` zepsuło wykrywanie rewizji; nazwa indeksu
  `session_user` (słowo zastrzeżone); rola tylko do odczytu widziała dane osobowe →
  migracje testujemy na prawdziwym obrazie bazy (CI na ubuntu), uprawnienia ról sprawdzamy
  testem dla każdej roli.
- `gate-guard` przez `pull_request`: PR mógł podmienić samą kontrolę → przy kontroli
  w workflow pytamy też „czy PR może zmienić samą kontrolę?”; `pull_request_target` tylko
  z uprawnieniami do odczytu i bez kodu z PR (test w `scripts/tests/`).
- „0 uwag Graphify” podane jako czysty przegląd, a limit przeglądów był wyczerpany → brak
  uwag to nie przegląd; podajemy przyczynę (np. limit) i sprawdzamy ją konektorem.
- „Dokumentacja jest na bieżąco”, a README pokazywało stary etap → przy zamknięciu etapu
  sprawdzamy wszystkie pliki ze stanem: `README.md`, `README.pl.md`, `roadmapa.md` (także
  tabela „Stan realizacji E<nr>”), `testy.md`, `docs/stan-pracy.md` (README pilnuje test).
- Progi doprecyzowane ponad roadmapę bez akceptacji właściciela → `source: doprecyzowanie`
  wymaga `accepted` i `note` (pilnuje `make requirements-check`); próg wynikający wprost
  z normy przywołanej w roadmapie (np. WCAG AA → axe 0 serious) to `source: roadmapa`.
- Etykieta PR przez `gh pr create --label` nie działa w sesji (GraphQL) → PR i etykiety
  przez REST (`gh api …/pulls`, `…/issues/<nr>/labels`).
- Dwie gałęzie w jednym `git push origin --delete a b`: błąd przy jednej przerwał całą
  komendę → jedna komenda `git push origin --delete` na gałąź.
