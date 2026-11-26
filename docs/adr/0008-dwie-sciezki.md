# ADR-0008: Dwie ścieżki realizacji: najpierw praca inżynierska, potem pełny produkt

- **Status:** przyjęta (decyzja właściciela 26.11.2026, propozycja asystenta zaakceptowana
  ze zmianami opisanymi niżej)
- **Data:** 2026-11-26
- **Etap:** po E3 (dotyczy E4–E18)
- **Źródło:** zakres pracy inżynierskiej (`docs/dokumentacja/fundamenty.md`, sekcja 0),
  roadmapa E4–E18, `docs/dokumentacja/testy.md` (sekcje 3 i 3a), `gates/requirements.yaml`

## Kontekst

GoatCash jest jednocześnie pracą inżynierską (Politechnika Krakowska) i darmowym produktem
publicznym. Pełna roadmapa E4–E18 to kilka miesięcy pracy jednej osoby (np. E4: 150 par
z czterech giełd i 72 h pracy na staging, E7: siedmiu agentów i 14 dni dowodów, E12:
pięć sesji z użytkownikami). Zakres pracy inżynierskiej jest węższy: aplikacja webowa,
kilku agentów (trend, ryzyko, analiza historyczna, podpowiedzi), wybrane metody AI/ML
na danych historycznych, prezentacja informacyjna (bez decyzji inwestycyjnych), opcjonalny
backtest, model danych, architektura, wymagania F/NF, opis metod, projekt GUI oraz
przetestowany prototyp. Proces z E3 (kilkanaście PR-ów na etap, każda zmiana dwa razy
przez CI, przeklejanie komend) był za wolny jak na termin obrony.

Wymagania właściciela: nowa rozmowa przy każdym etapie musi z samego repo wiedzieć, co
robić, jakie są testy i bramka; po obronie produkt ma dać się dokończyć bez utraty
czegokolwiek, a wszystko odłożone ma być w jednym miejscu opisane jako „do zrobienia
w ścieżce produktu”.

## Decyzja

1. **Ścieżka pracy** (bieżąca): E0–E3 (zaliczone, pełny zakres), potem E4, E5, E6, E7, E8,
   E9, E11, E12a, E12b w wersji okrojonej do minimum spełniającego zakres pracy. Kolejność
   i minimum każdego etapu: tabela „Kolejność prac” na początku `roadmapa.md`
   i podsekcja „Ścieżka pracy inżynierskiej” w karcie każdego etapu.
2. **Ścieżka produktu** (po obronie): wszystko ponad minimum w etapach ścieżki pracy
   (podsekcje „Dokończenie w ścieżce produktu”) oraz etapy odłożone w całości: E10, E10a,
   E11a, E13, E14 (a–c), E15, E16, E17, E18, a także Resend z E0. Karty tych etapów
   zostają bez zmian, ze statusem „⏸ odłożone (produkt)”.
3. **Bramki pracy** `G<nr>p` (G4p, G5p, G6p, G7p, G8p, G9p, G11p, G12p): kryteria okrojone
   w `testy.md`, sekcja 3a, z kolumną „przechodzi do produktu”. Pełne bramki G4–G18
   zostają nienaruszone i obowiązują w ścieżce produktu. Etap ścieżki pracy jest
   zaliczony, gdy jego bramka pracy ma `docs/gates/G<nr>p.passed.json` sprawdzany przez
   `gate-guard`; zamyka to zakres pracy, a nie pełny etap (status w roadmapie:
   „✅ zakres pracy (G<nr>p) · ⏸ reszta w produkcie”).
4. **Egzekwowanie:** `gates/requirements.yaml` ma przełącznik `sciezka` (`praca`
   albo `produkt`) i dwie mapy zależności; `gate-guard` czyta je z `main`. W ścieżce pracy
   PR z etykietą etapu odłożonego jest odrzucany. Powrót do produktu = jeden PR właściciela
   zmieniający przełącznik (zmiana w `gate_guard` w osobnym PR z niezależnym recenzentem,
   zgoda właściciela 26.11.2026).
5. **Wymagania:** każde F-xx i NF-xx w `docs/wymagania.yaml` ma `track` (`praca` albo
   `produkt`); wymaganie ścieżki pracy z etapu E4+ ma też `work_gate` (bramka pracy)
   i `work_target` (próg w ścieżce pracy). Pole `target` (pełny próg) zostaje bez zmian
   na ścieżkę produktu.
6. **Tryb ścieżki pracy** (sposób współpracy z asystentem, `CLAUDE.md` i `CONTRIBUTING.md`):
   1–3 PR-y na etap, asystent w sesji w chmurze sam pisze kod, testuje i otwiera właściwy
   PR z gałęzi `claude/…` z etykietą etapu i poprawia go do zielonego CI; właściciel
   przegląda i scala przez Squash and merge w GitHubie. Bez szkiców testowych, łatek,
   niezależnego recenzenta (poza zmianą `gate_guard` w punkcie 4) i triażu Graphify.
   Dokumentacja i statusy aktualizowane przy domknięciu etapu. Zasady pełnej ścieżki
   zostają w dokumentacji, oznaczone jako obowiązujące po powrocie do produktu.
7. **CI szybsze:** obrazy (build + Trivy amd64 i arm64) w PR tylko przy zmianie
   `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock` albo `ci.yml`, a zawsze na
   `main`; bramki na macOS tylko przy zmianach skryptów powłoki, `Makefile`, `scripts/`,
   `gates/`, `infra/` albo `ci.yml`, a zawsze na `main`.

Zmiany właściciela do propozycji (26.11.2026): agent Trend tylko na EMA i ADX (filtr
Kalmana do produktu); ML jeden horyzont 24 h (7 d i 4 h do produktu); w G4p zamiast
„kompletność ≥ 99,9% za cały okres” 100% luk wykrytych i opisanych przez detektor oraz
kompletność liczona względem danych, które giełda faktycznie udostępnia (luki po stronie
giełdy jawnie w raporcie); R2 i Telegram z E0 zamknięte dowodem z E3, do produktu
przechodzi tylko Resend. Zaakceptowane bez zmian: makiety w Figma Free (zamiast płatnego
Lovable), test prezentacji z 3 osobami i kwestionariuszem SUS, agent Historyczny jako kNN
(analogie z historii), historia od 01.2023, obrazy w PR przy zmianie zależności.

## Rozważane alternatywy

| Opcja                                                            | Za                                                    | Przeciw                                                                                      |
| ---------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Pełna roadmapa przed obroną                                      | jedna ścieżka, brak dwóch zestawów bramek             | kilka miesięcy więcej; ryzyko niezdążenia z pracą                                            |
| Okrojenie pełnych bramek G4–G12 (zmiana progów)                  | mniej plików i pojęć                                  | pełne kryteria produktu znikają albo są nadpisane; po obronie trzeba je odtwarzać z historii |
| Osobne bramki pracy `G<nr>p` + przełącznik w `requirements.yaml` | nic nie znika; egzekwuje automat; powrót jednym PR-em | zmiana `gate_guard` (kod bezpieczeństwa); dwa zestawy kryteriów do utrzymania w dokumentacji |
| Etykiety PR `E4p` zamiast przełącznika                           | ścieżka widoczna przy każdym PR                       | PR mógłby wybrać łagodniejszą ścieżkę etykietą; przełącznik z `main` jest poza zasięgiem PR  |

## Konsekwencje

- Zyskujemy: realny termin pracy, jednoznaczny opis dla każdej nowej rozmowy, pełny opis
  produktu zachowany obok, automat pilnujący kolejności także w ścieżce pracy.
- Tracimy (do czasu produktu): długie testy na staging (72 h, 14 dni, 30 dni), testy
  obciążeniowe, chaos i skany zewnętrzne poza E3, konta użytkowników, LLM, alerty, bota.
  Wszystko to jest opisane w podsekcjach „Dokończenie w ścieżce produktu” i w kolumnie
  „przechodzi do produktu” bramek pracy.
- Ryzyko: kod ścieżki pracy może wymagać przeróbek w produkcie (np. REST co godzinę →
  websockety w E4). Ograniczamy je, trzymając interfejsy z roadmapy (`MarketDataSource`,
  `MarketView`, `Evidence` v1, `Agent`), a okrajając tylko zakres.
- Ryzyko: szybszy proces = mniej przeglądu. Kontrolę dają CI, bramki pracy, CodeQL
  i przegląd właściciela przed scaleniem; obrazy i macOS i tak przechodzą na `main`,
  a wdrożenie czeka na zielone CI na `main`.
- Jak sprawdzimy, że decyzja była dobra: każdy wymóg zakresu pracy ma etap i dowód
  w tabeli `fundamenty.md`, sekcja 0.3, a mapa `docs/praca/README.md` wskazuje dowód dla
  każdego rozdziału pracy.
