# Kontekst projektu dla asystenta AI

GoatCash (goatcash.app): platforma analityczna rynku kryptowalut + bot, praca inżynierska
(Politechnika Krakowska) i darmowy produkt publiczny. Dokumentacja źródłowa jest w repo:
`docs/dokumentacja/` (fundamenty.md, roadmapa.md, testy.md; od 22.11.2026 źródło prawdy,
wersja w Claude Docs to archiwum). **Na początku każdej rozmowy przeczytaj
`docs/stan-pracy.md`** (gdzie jesteśmy, otwarte sprawy) i aktualizuj go po każdym kroku,
oraz `docs/lekcje.md` (błędy z poprzednich etapów, których nie powtarzamy).

Zasady pracy:

- Działamy dokładnie według roadmapy: bez pomijania, bez podmieniania, bez udawania, że coś
  jest zrobione. Etap jest zaliczony dopiero, gdy jego bramka przejdzie z dowodem.
- Odstępstwo od dokumentacji = jawna decyzja zapisana w dokumentacji (nie po cichu).
- Sekrety nigdy w repo ani w czacie. `.env.local` lokalnie, SOPS + age dla środowisk.
- Python: pakiet `goatcash` (nazwa `platform` koliduje z modułem standardowym Pythona),
  moduły przez `goatcash.<moduł>.api`, implementacja w `_impl`, import-linter w CI.
- Właściciel pracuje na macOS (Apple Silicon); serwer docelowy: Oracle A1 (arm64), Amsterdam.
- Stan realizacji w `docs/dokumentacja/roadmapa.md` i `testy.md` oznaczamy na bieżąco
  (✅ tylko z dowodem: plik, przebieg CI, raport bramki; ⚠️ gdy dowodu brak).
- Sposób współpracy z asystentem (łatki, testy, triaż uwag botów): sekcja niżej.

## Zasady współpracy

Ustalone z właścicielem 22.11.2026; obowiązują w każdej rozmowie, bez względu na prompt.

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
