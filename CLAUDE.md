# Kontekst projektu dla asystenta AI

GoatCash (goatcash.app): platforma analityczna rynku kryptowalut + bot, praca inżynierska
(Politechnika Krakowska) i darmowy produkt publiczny. Dokumentacja źródłowa jest w repo:
`docs/dokumentacja/` (fundamenty.md, roadmapa.md, testy.md; od 22.11.2026 źródło prawdy,
wersja w Claude Docs to archiwum). **Na początku każdej rozmowy przeczytaj
`docs/stan-pracy.md`** (gdzie jesteśmy, otwarte sprawy) i aktualizuj go po każdym kroku.

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
2. **Zmiany jako łatki:** asystent przygotowuje je w swoim klonie i wysyła plik `.patch`
   (`git diff --binary`). Właściciel: `git apply --check … && git apply …`, commit podpisany
   SSH, push, PR z etykietą etapu (`--label E<nr>`). Gałęzie `feat/`, `fix/`, `docs/`, `ci/`
   - `E<nr>-<opis>`; commity: Conventional Commits po polsku; scalanie tylko squash.
3. **Zanim asystent wyśle łatkę (bez wyjątków):**
   - `make gate G=1` i bramka bieżącego etapu, `CI=true make gate G=<nr>`, `make audit`,
     `pre-commit run --all-files`;
   - dla każdego zabezpieczenia pytanie „jak obejść tę kontrolę?”;
   - test dokładnie tak, jak użyje tego właściciel: ścieżki względne, katalog projektu z `.venv`,
     macOS `/bin/bash` 3.2, narzędzia BSD, GNU make 3.81;
   - test na prawdziwym GitHubie: gałąź `claude/<nazwa>-test`, szkic PR do tego, na co
     właściciel nałoży łatkę; całe CI zielone (z bramką na macOS), potem szkic zamknięty.
     Gałąź usuwa właściciel (`git push origin --delete claude/…`), bo asystent dostaje 403;
   - łatka nakłada się na dokładny commit właściciela i daje przetestowany stan
     (`git apply --index` + `git diff --cached --quiet <testowany_commit>`).

   W wiadomości z łatką: gdzie testowana (numer szkicu PR, wynik CI).
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
   łatce; bramka etapu = raport `docs/gates/G<nr>.md` + `G<nr>.passed.json` z `gate_pass.py`.
8. **Nowa rozmowa na każdy etap** (bez kompaktowania); wszystko, co ustalimy, ląduje w repo.

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
- Przed użyciem akcji GitHub lub wersji narzędzia: sprawdzić, że istnieje (`git ls-remote`),
  i przypiąć do SHA. Przed odejściem od dokumentacji: sprawdzić, co mówi dokumentacja.
  Wyjątków w skanerach nie dodajemy bez dowodu, że są potrzebne.
