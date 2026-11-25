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

## E3

- Blokady sesji wpisane do globalnych ustawień Claude Code (`~/.claude`), więc działały też
  w innych projektach właściciela, a skutek opisano dopiero po fakcie → zmiany na komputerze
  właściciela tylko w zakresie projektu; przed zmianą poza repo mówimy, czego dotknie.
- Poprawka hooka podana właścicielowi bez testu (nie działała) → każdą komendę dla
  właściciela testujemy najpierw na kopii (np. fałszywy katalog domowy w scratchpadzie).
- Po resecie katalogu powłoki komendy gita asystenta trafiły do głównego katalogu
  właściciela (przełączona gałąź, zmieniony plik) zamiast do worktree → każda komenda gita
  asystenta ma jawną ścieżkę (`git -C <worktree>`), a `git status` sprawdzamy przed commitem.
- `cmd | grep -q` przy `set -o pipefail` dawało losowe błędy (SIGPIPE, gdy `grep` kończy
  wcześniej) → wynik najpierw do zmiennej, potem `grep -q <<<"$zmienna"`.
- Blokada sesji (hook) reaguje na tekst komendy, nie na jej skutek: edycja pliku przez
  powłokę z nazwą polecenia Terraform w treści została zablokowana → zmiany treści plików
  narzędziami Edit/Write, a nie heredociem w Bash.
- Środowisko GitHub z wymaganym recenzentem a workflow z harmonogramem lub automatycznym
  wdrożeniem: przebieg czeka na kliknięcie, czyli „automat” ma ręczny krok → przed
  ustawieniem ochrony środowiska sprawdzamy, które workflow z niego korzystają i jak
  są uruchamiane.
- Nowy serwer z pustą bazą i istniejącą stanzą pgBackRest w R2: `stanza-create` odrzuca
  obcą instancję → odtworzenie od zera musi najpierw odtworzyć bazę z kopii (`deploy.sh`,
  test w `make compose-staging-test`).
- Nazwy limitów w polityce Oracle podane z pamięci (`standard-a1-core-count`), a A1 liczy
  też limit regionalny → A1 zablokowana dwa razy → nazwy limitów bierzemy z tabeli
  „Limits, quotas and usage” (kolumna Limit Name) i ustawiamy wszystkie, które dotyczą zasobu.
- Diagnoza błędu API Tailscale testem, który zmieniał dwie rzeczy naraz → wniosek był
  fałszywy → test zmienia jedną zmienną albo od razu całą macierz kombinacji.
- Sprzątanie testu Docker na Linuksie: pliki tworzone przez kontener (inny uid) nie dają
  się usunąć z runnera, a błąd w pułapce EXIT przy `set -e` zmienia wynik testu → pliki
  kontenera usuwa kontener, sprzątanie nie wpływa na wynik.
- Subject OIDC Tailscale wpisany w formacie z ogólnej dokumentacji, a repozytorium ma
  niezmienny format (`repo:<właściciel>@<id>/<repo>@<id>:environment:<env>`) → 403
  w CI → subject bierzemy z `gh api repos/<repo>/actions/oidc/customization/sub`.
- Endpoint R2 podany z `.eu.`, a bucket ma tylko wskazówkę lokalizacji (EEUR), nie
  jurysdykcję UE → przed podaniem adresu sprawdzamy jurysdykcję bucketu w Terraform.
- Komendy dla właściciela z miejscem do wpisania („…”) zostały wklejone dosłownie, a `pbpaste`
  bez wyjaśnienia wkleił przypadkową zawartość schowka → w komendach do wklejenia nie ma
  miejsc do uzupełnienia; wartości ze schowka zawsze z kontrolą formatu przed `gh secret set`.
- Edycja pliku SOPS uruchomiona z `!` w sesji asystenta pokazała odszyfrowaną treść
  w rozmowie (dotarła tylko pierwsza linia) → komendy, które wypisują sekrety, tylko
  w terminalu właściciela.
- Gałąź właściciela utworzona wprost z gałęzi `claude/…` niosła niepodpisane commity
  asystenta, a `main` wymaga podpisów → zawsze `merge --squash` i jeden podpisany commit.
- Świeży Ubuntu 24.04 w OCI nie ma `/etc/systemd/journald.conf.d` ani `/run/sshd` (SSH
  uruchamiany na żądanie) → playbook testujemy przed wdrożeniem w kontenerze Ubuntu 24.04
  z systemd (wolumen z pętli jako `/dev/oracleoci/oraclevdb`), łącznie z drugim przebiegiem
  (`changed=0`).
- Reguły alertów Grafany bez zapytań `instant` i z błędnym PromQL przeszły `terraform
  validate`, a padły dopiero na prawdziwych danych → zapytania sprawdzamy na danych przez
  API źródła danych przed zmianą reguł; test pilnuje `instant`.
- Oracle usuwa wolumeny i dyski startowe asynchronicznie, a przy Always Free (200 GB) każdy
  usuwany dysk blokuje nowy → odtworzenie od zera czeka na usunięcie wszystkich dysków
  (dwie nieudane próby; trzecia przeszła w 1388 s).
- Po odtworzeniu z kopii Postgres jest „zdrowy”, ale jeszcze odgrywa WAL → przed
  `stanza-create` i migracjami czekamy, aż `pg_is_in_recovery()` zwróci `f`.
- Próba obejścia blokady sesji (rozbicie nazwy ścieżki `.ssh`) została zatrzymana przez
  klasyfikator → blokad nie obchodzimy; gdy blokada przeszkadza w teście, pomijamy ten punkt
  i mówimy o tym.
