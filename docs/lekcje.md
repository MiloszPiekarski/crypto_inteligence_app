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
- Raport G3 twierdził, że odtworzenie od zera użyło kopii z timera, a przebieg dowodowy
  odtworzył kopię z `backup-now` (rozliczenie E3) → zdanie w raporcie bramki piszemy tylko
  na podstawie logu przebiegu, który jest dowodem, i podajemy jego ID.
- ✅ w roadmapie dla „obserwowalności” obejmował logi i ślady, których nikt nie sprawdził:
  logi nie docierały (zła ścieżka katalogu Dockera), a api w ogóle nie wysyłało śladów → ✅
  tylko dla tego, co zostało pokazane; wiersz z kilkoma rzeczami ma dowód dla każdej.
- Warunek roli Ansible `ansible_swaptotal_mb == 0` przechodził lokalnie przypadkiem (inny
  swap w systemie), więc plik wymiany nie był włączany → warunki opieramy na stanie tego
  konkretnego zasobu, a test sprawdza wynik (plik aktywny), nie brak błędu.
- Kolektor OTel montował domyślny `/var/lib/docker/containers`, a Docker trzymał logi na
  wolumenie (`data-root`) → ścieżki zależne od konfiguracji z innej warstwy (Ansible →
  Compose) pilnuje test, który czyta obie.
- Gałąź `claude/…` oparta na commicie sprzed scalenia innego PR dała u właściciela brak
  `IDENTYCZNE` → przed przekazaniem przebazowujemy na aktualny `main` i czekamy na CI.
- Plan Terraform zapisany do pliku (`-out`) zawiera jawne wartości zmiennych, także
  tokeny → `*.plan` w `.gitignore` i usuwanie pliku zaraz po `apply`.
- Wartości metryk z node-exportera są w notacji naukowej (`1.79e+09`), więc `sed` na liczbę
  całkowitą zwrócił pusty wynik → metryki w testach parsujemy jak liczby zmiennoprzecinkowe.
- Gitleaks (`generic-api-key`) zgłosił publiczny odcisk klucza GPG przez słowo „key”
  w nazwie zmiennej → wyjątek tylko dla tej reguły i dokładnej wartości, z dowodem, że
  sąsiedni ciąg dalej jest wykrywany.
- `ansible-test` raz padł na przejściowym błędzie DNS w kontenerze (pobieranie sops) →
  przy czerwonym teście najpierw czytamy przyczynę; błąd sieci powtarzamy raz i opisujemy,
  a nie oznaczamy jako sukces.
- `pre-commit run --all-files` sprawdza tylko pliki śledzone przez git: nowe pliki (np. ADR)
  przeszły, a `make gate G=1` (Biome `ci .`) padł na ich formatowaniu → nowe pliki
  dodajemy (`git add`) przed pre-commit, a o wyniku decyduje bramka, nie sam pre-commit.

## E4

- Zasada „commity asystenta mogą być niepodpisane, bo squash podpisuje GitHub” sprawdzona
  na commitach squash z PR-ów z commitami właściciela; ruleset sprawdza każdy commit w PR
  i zablokował PR #129 → regułę sprawdzamy na przypadku, którego dotyczy (tu: PR
  z niepodpisanym commitem), a nie na wyniku innej ścieżki; wymagania rulesetu czytamy
  z API (`rulesets/<id>`).
- Workflow uruchamiany ręcznie (`workflow_dispatch`) działa dopiero z `main`, więc sondy
  na serwerze nie da się puścić z gałęzi PR → pracę zależną od takiego workflow dzielimy
  na mały PR z workflow i PR z resztą (PR 2a i 2b E4), i mówimy o tym przy planie etapu.
- Bybit blokuje kraj sesji asystenta (403 CloudFront), a ccxt raportuje to jako
  `RateLimitExceeded` → dostęp do zewnętrznego API sprawdzamy z miejsca, w którym kod
  będzie działał (sonda z serwera), a kasety nagrywamy tam, gdzie API odpowiada.
- `statistics.pstdev` (ułamki dokładne) spowalniało test właściwości DQ ~5x → w pętlach
  po świecach liczymy na float (`math.fsum`), wynik zależny tylko od zawartości okna.
- Mutacja reguły OHLC (close poza [low, high]) przeżyła pierwsze testy, bo wstrzykiwane
  błędy psuły zawsze to samo pole → dla każdej reguły test mutacyjny i błędy wstrzykiwane
  w kilku wariantach.
- `scripts/gate_pass.py` odczytuje nazwę repozytorium przez `gh repo view` (GraphQL),
  zablokowany w sesji w chmurze → na czas komendy podstawione `gh` zwracające nazwę
  repozytorium (bez zmiany skryptu, która wymagałaby recenzenta); opis w `docs/gates/G4p.md`.
  Przy następnej zmianie `gate_pass` (z recenzentem): nazwa z `GITHUB_REPOSITORY` albo REST.
- Pierwszy raport danych uruchomiony „na czas” przed końcem pobierania historii wyszedł
  czerwony → czas pobierania bierzemy z pierwszego przebiegu (tu ok. 60 min dla 20 par × 2
  giełdy), a raport puszczamy po nim; czerwony przebieg zostaje w historii jako próba.

## E5

- Ta sama nazwa pliku testów w dwóch katalogach (`test_pgstore.py` w `marketdata`
  i `features`) przy testach bez pakietów: błąd zbierania testów w pełnym `pytest`, choć
  każdy katalog osobno przechodził → nazwy plików testów unikalne w całym repozytorium;
  przed wypchnięciem zawsze pełne `pytest`, nie tylko nowe pliki.
- Przekaźnik outbox z E4 publikował wszystkie zdarzenia z `event_outbox` pod nazwą swojego
  procesu, więc pierwszy nowy typ zdarzenia (`features.ready`) poszedłby jako `ingest@…`
  → przy nowym producencie zdarzeń sprawdzamy, kto publikuje outbox; każdy proces publikuje
  tylko własne typy (`relay_outbox(..., types=...)`).
- Warunek z roadmapy `ingested_at ≤ as_of` dawał dla historii pobranej później pusty widok
  → wymagania czasowe sprawdzamy na prawdziwym przebiegu danych (kiedy dane powstały, kiedy
  je zapisano), a doprecyzowanie zapisujemy jawnie z decyzją właściciela (`known_at`).
- Próg pokrycia (80%) prawie przekroczony, bo nowy kod bazy i konsumenta był testowany
  tylko w teście z Dockerem (poza `make test`) → logikę sprawdzamy też bez Dockera
  (atrapa strumienia o tej samej semantyce), a test z Dockerem sprawdza integrację.
- Lokalny test bazy bez Timescale (Postgres 16 w sesji) wymaga schematu odtworzonego
  z migracji bez poleceń Timescale; to nie zastępuje CI → raportujemy, co sprawdzono
  lokalnie, a co dopiero w CI.
- Tryb leniwy Polars (eliminacja wspólnych podwyrażeń) okazał się 3x wolniejszy na małych
  ramkach niż tryb natychmiastowy → optymalizację mierzymy, zanim ją zostawimy.
- Komendy „po scaleniu” (usunięcie gałęzi) podane w tej samej wiadomości co kroki podpisu:
  właściciel wykonał je po kolei, gałąź zniknęła przed scaleniem i GitHub zamknął PR #135
  bez scalenia (naprawa: odtworzenie gałęzi z podpisanego commitu i ponowne otwarcie PR) →
  komendy po scaleniu podajemy dopiero po potwierdzeniu scalenia, w osobnej wiadomości;
  gałęzie #133 i #134 GitHub usunął sam po scaleniu.
- Audyt E5: próg testu sformułowany „po swojemu” (1e-9 · max(1, |b|)) był słabszy od zapisu
  kryterium („różnica < 1e-9”) i przepuszczał odchylenie RSI o 1,5e-8 → próg w teście
  dosłownie jak w kryterium; interpretację, która je osłabia, zatwierdza właściciel.
- Audyt E5: losowanie chwil jako dowolnych milisekund dawało 6/1000 chwil na pełnej
  godzinie, czyli prawie nie sprawdzało przypadku na żywo; mutację brzegu łapał jeden test
  deterministyczny → przy testach właściwości losujemy jawnie także przypadki brzegowe
  (tu: pełne godziny) i asercją pilnujemy ich liczby; mutacje brzegu w każdym teście.
- Audyt E5: „porównanie z TA-Lib” dla MACD było porównaniem ze złożonymi EMA, a
  `talib.MACD` ma inną inicjalizację → przy wzorcu złożonym z funkcji podstawowych mówimy
  to wprost i sprawdzamy też funkcję gotową, jeśli istnieje.
- Audyt E5: znany problem poprzedniego etapu (`ingested_at` nadpisywane przy upsercie
  w E4) nie trafił do opisu ograniczeń E5, choć dotyczył replay → przy zamknięciu etapu
  przeglądamy otwarte problemy poprzednich etapów, które dotykają jego zakresu.
