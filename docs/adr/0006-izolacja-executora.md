# ADR-0006: Izolacja executora bota

- **Status:** zatwierdzona 2026-11-22 (scalenie PR #24, commit `2e4cb62`)
- **Data:** 2026-11-22
- **Etap:** E2
- **Źródło:** roadmapa E14 („Architektura executora”), Fundamenty sekcje 2 i 8 (klasy
  sekretów), ADR-0001, kontrakty import-linter z E1

## Kontekst

Executor jest jedynym procesem, który ma dostęp do kluczy API giełd użytkowników i wysyła
zlecenia z prawdziwymi pieniędzmi (od E14c). Włamanie do `web`, `api` albo `worker`, błąd
w module analitycznym lub prompt injection w LLM nie mogą dać możliwości odczytu kluczy ani
złożenia zlecenia z pominięciem silnika ryzyka.

## Decyzja

1. **Osobny kod:** pakiet `goatcash_executor` w `services/executor`, osobny obraz Dockera.
   Import-linter zabrania mu importu modułów domenowych platformy, także pośrednio
   (`allow_indirect_imports = false`, sonda `executor-indirect` w G1); wspólny jest tylko
   `bot_core` (polityki, intencje, silnik ryzyka).
2. **Osobna maszyna i sieć:** mikro-VM AMD z zarezerwowanym publicznym IP (biała lista IP
   w kluczu giełdy), bez portów przychodzących z internetu; połączenie z bazą przez Tailscale.
   **Executor nie łączy się z Valkey ani z API** (ADR-0003).
3. **Osobna rola bazy** `goatcash_executor` z dostępem wyłącznie do schematu `bot` (ADR-0002).
   Procesy platformy zapisują `order_intents`, ale nie widzą kolumn z kluczami w
   `bot.exchange_connections`.
4. **Pobieranie intencji z Postgresa:** `SELECT … FOR UPDATE SKIP LOCKED` z budzeniem przez
   `LISTEN/NOTIFY` i odpytywaniem co 1 s jako zabezpieczeniem; mieści się w NF-07 (≤ 5 s od
   decyzji do zlecenia).
5. **Ryzyko sprawdzane dwa razy:** silnik ryzyka z `bot_core` przy tworzeniu intencji (worker)
   i ponownie w executorze tuż przed wysłaniem, na świeżych danych (≤ 2 min); executor odrzuca
   intencję, której nie przepuszcza jego własne sprawdzenie, niezależnie od tego, co zapisał
   worker.
6. **Klucze giełd:** szyfrowanie kopertowe: klucz danych per użytkownik (AES-256-GCM), klucz
   główny w OCI Vault, dostęp do Vault tylko z instancji executora (zasada instancji OCI).
   Odszyfrowany klucz istnieje tylko w pamięci procesu, nigdy w logach, zdarzeniach ani
   wyjątkach (filtr logów + test). Klucz z prawem wypłat jest odrzucany przy dodawaniu.
7. **Idempotencja i stan:** `clientOrderId` = skrót identyfikatora intencji; maszyna stanów
   zlecenia i każde przejście w `bot.bot_events`; uzgadnianie z giełdą co 15 s, rozbieżność =
   wstrzymanie bota użytkownika i alert; SL/TP po stronie giełdy.
8. **Kill switch** użytkownika, globalny (administrator) i automatyczny; stan w
   `bot.kill_switches` sprawdzany przed każdym zleceniem.
9. **Sekrety executora** (połączenie z bazą, dostęp do Vault) osobno od sekretów platformy:
   osobny plik SOPS dla executora w każdym środowisku (do dodania w E14, z własnym kluczem age).

## Rozważane alternatywy

| Opcja                                | Za                         | Przeciw                                                                       |
| ------------------------------------ | -------------------------- | ----------------------------------------------------------------------------- |
| Executor jako zadanie w `worker`     | mniej infrastruktury       | klucze w tym samym procesie co LLM, newsy i kod analityczny                   |
| Executor czyta zdarzenia z Valkey    | prostsze budzenie          | kolejna droga do executora i zależność od Valkey przy zleceniach              |
| Klucze w SOPS / zmiennych środowiska | prosto                     | wszystkie klucze użytkowników w jednym sekrecie, bez rotacji per użytkownik   |
| Osobna baza dla bota                 | mocniejsza izolacja danych | dodatkowa instancja na małej VM; role + schemat + sieć wystarczają (ADR-0002) |

## Konsekwencje

- Model zagrożeń STRIDE (PR `docs/E2-stride`) omawia executor jako osobną strefę zaufania.
- Migracja 0001 tworzy schemat `bot` i rolę `goatcash_executor`; test migracji sprawdza, że
  `goatcash_app` nie odczyta kolumn z kluczami.
- Testy G14b: próba odczytu kluczy z API, logów i zrzutu pamięci workera, klucz z prawem
  wypłat, chaos sieci; G14b blokuje tryb live.
