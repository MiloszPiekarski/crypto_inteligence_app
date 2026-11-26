# Kontekst projektu dla asystenta AI

GoatCash (goatcash.app): platforma analityczna rynku kryptowalut + bot, praca inżynierska
(Politechnika Krakowska) i darmowy produkt publiczny. Dokumentacja źródłowa jest w repo:
`docs/dokumentacja/` (fundamenty.md, roadmapa.md, testy.md; od 22.11.2026 źródło prawdy,
wersja w Claude Docs to archiwum). **Na początku każdej rozmowy przeczytaj
`docs/stan-pracy.md`** (gdzie jesteśmy, otwarte sprawy) i aktualizuj go po każdym kroku
(w ścieżce pracy: przy domknięciu etapu), oraz `docs/lekcje.md` (błędy z poprzednich etapów,
których nie powtarzamy).

**Teraz obowiązuje ścieżka pracy inżynierskiej** (od 26.11.2026, ADR-0008): kolejność
etapów i ich minimum w tabeli „Kolejność prac” na początku `docs/dokumentacja/roadmapa.md`,
bramki pracy `G<nr>p` w `docs/dokumentacja/testy.md` (sekcja 3a), sposób pracy w sekcji
„Tryb ścieżki pracy” niżej. Wszystko odłożone jest opisane w roadmapie jako
„⏸ odłożone (produkt)” albo „Dokończenie w ścieżce produktu”.

Zasady pracy:

- Działamy dokładnie według roadmapy: bez pomijania, bez podmieniania, bez udawania, że coś
  jest zrobione. Etap jest zaliczony dopiero, gdy jego bramka przejdzie z dowodem.
- Odstępstwo od dokumentacji = jawna decyzja zapisana w dokumentacji (nie po cichu).
- Sekrety nigdy w repo ani w czacie. `.env.local` lokalnie, SOPS + age dla środowisk.
- Python: pakiet `goatcash` (nazwa `platform` koliduje z modułem standardowym Pythona),
  moduły przez `goatcash.<moduł>.api`, implementacja w `_impl`, import-linter w CI.
- Właściciel pracuje na macOS (Apple Silicon); serwer docelowy: Oracle A1 (arm64), Amsterdam.
- Stan realizacji w `docs/dokumentacja/roadmapa.md` i `testy.md` oznaczamy na bieżąco
  (✅ tylko z dowodem: plik, przebieg CI, raport bramki; ⚠️ gdy dowodu brak;
  ⏸ odłożone do ścieżki produktu).
- Sposób współpracy z asystentem: „Tryb ścieżki pracy” (teraz) i „Zasady współpracy”
  (pełne, po powrocie do produktu), sekcje niżej.

## Tryb ścieżki pracy (obowiązuje od 26.11.2026 do powrotu do produktu)

Decyzja właściciela 26.11.2026, ADR-0008. Projekt realizuje teraz **ścieżkę pracy
inżynierskiej**: etapy z tabeli „Kolejność prac” na początku `docs/dokumentacja/roadmapa.md`,
w zakresie z podsekcji „Ścieżka pracy inżynierskiej” karty etapu, z bramką pracy `G<nr>p`
(`docs/dokumentacja/testy.md`, sekcja 3a). Tam, gdzie ten tryb jest sprzeczny z „Zasadami
współpracy” niżej, obowiązuje ten tryb; reszta zasad (w tym całe „Zachowanie asystenta”)
obowiązuje bez zmian. Pełne „Zasady współpracy” wracają po przełączeniu na ścieżkę
produktu (`docs/start-nowej-rozmowy.md`, sekcja „Przełączenie na ścieżkę produktu”).

1. **Zakres:** tylko „Zakres w ścieżce pracy” etapu. Rzeczy z „Dokończenie w ścieżce
   produktu” nie robimy; gdy coś z nich okaże się potrzebne, asystent pyta i zapisuje
   decyzję jawnie.
2. **Sesja w chmurze, asystent pracuje sam:** rozmowa etapu działa w sesji w chmurze
   z repozytorium (bez dostępu do komputera właściciela i bez kluczy chmury). Asystent
   pisze kod, uruchamia testy, wypycha gałąź `claude/E<nr>-<opis>`, otwiera z niej
   **właściwy PR** do `main` (nie szkic) z etykietą etapu (`E<nr>`) i sam poprawia błędy,
   aż całe CI jest zielone. Właściciel przegląda i scala przez **Squash and merge
   w GitHubie**. Bez szkiców testowych `claude/…`, bez łatek do nakładania i bez
   przenoszenia zmian na gałąź właściciela.
3. **Podpisy:** ruleset `main` wymaga podpisanych commitów. Squash and merge w GitHubie
   tworzy na `main` nowy commit podpisany przez GitHub, więc commity asystenta na gałęzi
   `claude/…` mogą być niepodpisane. Sprawdzone 26.11.2026 przez API: commity squash na
   `main` (`d10535e`, `653a790`) mają committera „GitHub” i podpis `valid`.
4. **1–3 PR-y na etap** zamiast „jedna rzecz na PR”; podział etapu na PR-y asystent
   proponuje na początku rozmowy i czeka na akceptację. Mały PR z dowodem bramki
   (`G<nr>p.passed.json`) po zielonym CI na `main` nie wlicza się do limitu.
5. **Bez niezależnego recenzenta i bez triażu Graphify** (Graphify wyłączony do końca
   pracy). Kontrolę dają CI, bramki pracy i CodeQL. Wyjątek: zmiana kontroli bramek
   (`scripts/gate_guard.py`, `scripts/gate_pass.py`, `gate-guard.yml`,
   `gates/requirements.yaml`) albo obsługi sekretów: asystent proponuje recenzenta i czeka
   na zgodę. Uwagi automatycznych recenzentów (Copilot) asystent naprawia tylko przy
   problemie bezpieczeństwa, poprawności albo bramki.
6. **Testy obowiązkowe:** poprawność modułów analitycznych (wartości referencyjne liczone
   niezależnie, testy właściwości, brak zaglądania w przyszłość) i, od E9, sposób
   prezentacji wyników użytkownikowi. Ciężkie testy z pełnych bramek (wielodniowe na
   staging, obciążeniowe, chaos, skany zewnętrzne) są w ścieżce produktu.
7. **Dokumentacja przy domknięciu etapu, nie w każdym PR:** statusy ✅ z dowodami
   w `roadmapa.md` (tabela „Kolejność prac” i karta etapu) i `testy.md` (sekcja 3a), raport
   `docs/gates/G<nr>p.md`, `G<nr>p.passed.json` z `gate_pass.py`, `docs/stan-pracy.md`,
   `docs/praca/README.md` i `metody.md`, README (status), `docs/lekcje.md`.
8. **CI szybsze:** obrazy w PR tylko przy zmianie zależności i `Dockerfile`, bramka na
   macOS tylko przy zmianach skryptów powłoki (`testy.md`, sekcja 4); na `main` wszystko.
9. **Bez zmian:** zgoda właściciela przed operacjami kosztownymi albo nieodwracalnymi
   (w tym pierwsze uruchomienie nowego workflow na serwerze), sekrety nigdy w czacie ani
   w repo, bez udawania, ✅ tylko z dowodem, odstępstwa od dokumentacji tylko jawnie
   zapisane, asystent nie scala.

## Zasady współpracy (pełne; w ścieżce pracy z wyjątkami z trybu powyżej)

Ustalone z właścicielem 22.11.2026; obowiązują w każdej rozmowie, bez względu na prompt.
W ścieżce pracy punkty 1–7 procedury zmian zastępuje „Tryb ścieżki pracy” tam, gdzie są
sprzeczne; po powrocie do produktu obowiązują w całości.

Procedura zmian:

1. **Instrukcje dla właściciela:** krok po kroku, gotowe komendy do wklejenia (zaczynają się od
   `cd ~/Documents/Millosz/crypto_app`), przy każdym kroku oczekiwany wynik i wyraźne punkty
   STOP („wklej mi wynik, jeszcze nie scalaj”). Wynik wklejony przez właściciela asystent
   sprawdza (najlepiej także przez API GitHuba), a nie przyjmuje na słowo.
2. **Tryb lokalny (od 23.11.2026, decyzja właściciela; jawna zmiana trybu „łatek”):**
   asystent działa w Claude Code na komputerze właściciela, w osobnym `git worktree`
   (`.git/claude-wt/<nazwa>`), tylko na gałęziach `claude/E<nr>-<opis>`. Commity asystenta
   na tych gałęziach są niepodpisane (`git -c commit.gpgsign=false`), żeby nie nosiły podpisu
   właściciela. Asystent wypycha gałąź `claude/…` i otwiera z niej szkic PR do testu CI.
   Właściciel przegląda zmianę i przenosi ją na swoją gałąź (przedrostek `feat/`, `fix/`,
   `docs/` albo `ci/`, potem `E<nr>-<opis>`; np. `git checkout -b docs/E3-x origin/claude/E3-x`
   i commit podpisany SSH), wypycha, otwiera PR z etykietą etapu (`--label E<nr>`) i scala.
   Commity: Conventional Commits po polsku; scalanie tylko squash. Blokady w ustawieniach
   Claude Code właściciela (poza repo) opisuje sekcja „Blokady sesji lokalnej”
   w `docs/start-nowej-rozmowy.md`. W sesji w chmurze (bez dostępu do komputera właściciela)
   obowiązuje dawny tryb łatek: plik `.patch` z `git diff --binary`, właściciel
   `git apply --check … && git apply …`.
3. **Zanim asystent przekaże zmianę właścicielowi (bez wyjątków):**
   - `make gate G=1` i bramka bieżącego etapu, `CI=true make gate G=<nr>`, `make audit`,
     `pre-commit run --all-files`;
   - dla każdego zabezpieczenia pytanie „jak obejść tę kontrolę?”;
   - test dokładnie tak, jak użyje tego właściciel: ścieżki względne, katalog projektu z `.venv`,
     macOS `/bin/bash` 3.2, narzędzia BSD, GNU make 3.81;
   - test na prawdziwym GitHubie: gałąź `claude/…` z bazą na aktualnym `main`, szkic PR;
     całe CI zielone (z bramką na macOS), potem szkic zamknięty. Gałąź usuwa właściciel,
     jedną komendą na gałąź (`git push origin --delete claude/…`);
   - właściciel dostaje dokładnie przetestowany stan: jego gałąź powstaje z testowanego
     commitu, a przed PR `git diff --quiet origin/claude/<nazwa> HEAD` nic nie zwraca
     (w trybie łatek: `git apply --index` + `git diff --cached --quiet <testowany_commit>`).

   W wiadomości ze zmianą: gdzie testowana (numer szkicu PR, wynik CI).
4. **Niezależny recenzent (osobny agent) domyślnie nie:** jest drogi (ok. 30 min). Asystent
   proponuje go tylko przy zmianach sekretów lub bezpieczeństwa, podaje czas i czeka na zgodę.
5. **Uwagi Graphify i Copilota: triaż**, tabela naprawiamy / odpowiadamy / ignorujemy z gotowym
   tekstem odpowiedzi do wątku. Kod zmieniamy tylko przy problemie bezpieczeństwa, poprawności
   albo bramki (z testem, który bez poprawki pada). Uwaga fałszywa: odpowiedź z dowodem
   i „Resolve conversation”. Drobiazg: zgłoszenie z etykietą `tech-debt`, wątek rozwiązany.
   Graphify nie jest częścią bramki; nie czekamy na niego ze scaleniem.
6. **Małe PR-y:** jedna rzecz na PR.
7. **Dokumentacja na bieżąco:** stan w `roadmapa.md` i `testy.md` (✅ tylko z dowodem,
   ⚠️ brak dowodu, ⏳ w toku, ⬜ nie rozpoczęto); `docs/stan-pracy.md` aktualizowany w każdej
   łatce; bramka etapu = raport `docs/gates/G<nr>.md` + `G<nr>.passed.json` z `gate_pass.py`;
   przy zamknięciu etapu także tabela „Stan realizacji E<nr>” w `roadmapa.md`, status
   i komendy w `README.md` i `README.pl.md` (pilnuje `scripts/tests/test_readme_status.py`)
   oraz nowe pozycje w `docs/lekcje.md`.
8. **Nowa rozmowa na każdy etap** (bez kompaktowania); wszystko, co ustalimy, ląduje w repo.
   Prompt na start: `docs/start-nowej-rozmowy.md`.

Zachowanie asystenta:

- Zawsze po polsku.
- Sekrety nigdy w czacie ani w repo (tylko Bitwarden i `.env.local`). Nigdy nie prosić
  o pokazanie klucza prywatnego (`oci_api_key.pem`, klucze age, `.env.local`); komendy
  diagnostyczne nie wypisują wartości sekretów.
- Nie obchodzimy zabezpieczeń komputera firmowego właściciela (komunikat hooka firmowego
  „SAFE: Private GitHub repository verified.” przy `git push` ignorujemy).
- Bez udawania: czego nie sprawdzono, to mówimy; pomyłkę przyznajemy wprost i naprawiamy.
  Na prośbę o brutalną szczerość: brutalna szczerość.
- Decyzje właściciela (licencja, format, nazwy, zakres): pytanie z jedną rekomendowaną opcją.
  Rzeczy oczywiste bez pytania.
- Asystent nie scala i nie wypycha na gałęzie właściciela; jego są tylko gałęzie `claude/…`.
  Asystent nie czyta `.env.local`, `~/.oci`, kluczy age ani `~/.ssh`; w trybie lokalnym
  pilnują tego także blokady w ustawieniach Claude Code (`docs/start-nowej-rozmowy.md`),
  które jednak nie są pełną izolacją (ich luki są tam opisane).
- Przed użyciem akcji GitHub lub wersji narzędzia: sprawdzić, że istnieje (`git ls-remote`),
  i przypiąć do SHA. Przed odejściem od dokumentacji: sprawdzić, co mówi dokumentacja.
  Wyjątków w skanerach nie dodajemy bez dowodu, że są potrzebne.
- Prawdziwe zasoby (od E3): zanim asystent zaproponuje albo uruchomi cokolwiek, co kosztuje
  albo jest nieodwracalne, zatrzymuje się i pisze: co dokładnie się stanie, ile to kosztuje
  (albo że mieści się w Always Free / darmowym planie, z linkiem do źródła) i czy da się to
  cofnąć; potem czeka na „tak” właściciela. Dotyczy zwłaszcza: dodania metody płatności
  i włączania płatnych usług lub planów (R2, Oracle poza Always Free, Grafana, Better Stack,
  Tailscale); `terraform apply` i `terraform destroy` (z liczbami z `terraform plan`:
  add / change / destroy); zmian DNS i serwerów nazw; usuwania zasobów, wolumenów, kopii,
  bucketów i danych; pierwszego uruchomienia `deploy-staging.yml`. W razie wątpliwości,
  czy coś kosztuje, asystent traktuje to jako płatne i pyta.
- Komendy z kluczami chmury (Oracle, Cloudflare, Terraform, Ansible) uruchamia właściciel
  (albo CI); asystent sprawdza wklejony wynik. Komendy diagnostyczne nie wypisują sekretów.
- Kroki w konsolach (Oracle, Cloudflare, Grafana, Better Stack itd.) wykonuje właściciel;
  asystent prowadzi go klik po kliku, z oczekiwanym wynikiem i punktem STOP.
