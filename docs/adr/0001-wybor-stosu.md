# ADR-0001: Wybór stosu technologicznego

- **Status:** zatwierdzona 2026-11-22 (scalenie PR #1, commit `c7e95c1`)
- **Data:** 2026-11-22
- **Etap:** E1
- **Źródło:** „Fundamenty i decyzje”, sekcja 1

## Kontekst

Platformę buduje i utrzymuje jedna osoba, równolegle ze studiami, przy kosztach bliskich
zera w fazie budowy. Repozytorium jest publiczne. System łączy dane rynkowe w czasie
rzeczywistym, modele ML, modele językowe i (później) bota handlowego, więc potrzebuje
jasnych granic modułów, odtwarzalnej infrastruktury i bezpiecznego zarządzania sekretami.

## Decyzja

Python (FastAPI) + PostgreSQL/TimescaleDB + Valkey na jednej maszynie Oracle Always Free
na czas budowy, Next.js na Cloudflare, modele ML własne, LLM przez bramkę z kilkoma
dostawcami. Całość w kontenerach, żeby przeniesienie na płatny serwer w UE przy publicznym
starcie było zmianą konfiguracji, nie przepisaniem.

| Obszar                  | Decyzja                                                                                                                      | Dlaczego                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Architektura            | Modularny monolit + workery + odizolowany executor bota                                                                      | Jedna osoba utrzymuje; granice modułów pozwalają później wydzielić serwisy       |
| Repozytorium            | Publiczny monorepo na GitHub (pnpm + uv)                                                                                     | Jeden PR zmienia kontrakt, backend i frontend naraz                              |
| Backend                 | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic                                                                     | Ekosystem ML i danych; typy współdzielone z kontraktem OpenAPI                   |
| Zadania w tle           | arq (Redis) + harmonogram cron arq                                                                                           | Natywnie asynchroniczne, lekkie, bez Celery i Ray                                |
| Baza                    | PostgreSQL 17 + TimescaleDB + pgvector                                                                                       | Szeregi czasowe, dane relacyjne i wektory w jednym silniku                       |
| Cache, strumienie       | Valkey (otwarty fork Redis)                                                                                                  | Kolejki, pub/sub, Redis Streams dla tablicy dowodów                              |
| Archiwum i kopie        | Cloudflare R2 (Parquet, kopie bazy, artefakty modeli)                                                                        | Brak opłat za transfer wychodzący                                                |
| Frontend                | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query, Lightweight Charts, ECharts                           | SSR dla publicznych stron aktywów (SEO), dojrzały ekosystem                      |
| Hosting frontu          | Cloudflare (Workers przez adapter OpenNext) + CDN + WAF                                                                      | Darmowy plan pozwala na użytek komercyjny; ochrona DDoS                          |
| Hosting backendu        | Faza budowy: Oracle Always Free (ARM 2 OCPU / 12 GB). Publiczny start: płatny VPS w UE                                       | Patrz Fundamenty, sekcja 4                                                       |
| Uwierzytelnianie        | Better Auth (w Next.js, dane w naszym Postgresie) + JWT weryfikowany w FastAPI przez JWKS                                    | Brak uzależnienia od dostawcy, 2FA i passkeys                                    |
| Dane rynkowe            | Publiczne API giełd przez ccxt (OKX, Bybit, Coinbase, Kraken) + CoinGecko + DefiLlama                                        | Patrz Fundamenty, sekcja 3                                                       |
| Giełdy dla bota         | Najpierw OKX i Bybit, potem Kraken i Coinbase                                                                                | Najlepsze środowiska testowe                                                     |
| ML                      | LightGBM, scikit-learn, statsmodels, arch, hmmlearn, Polars, DuckDB, Optuna, MLflow                                          | Modele tablicowe, interpretowalne, trening na CPU                                |
| LLM                     | Bramka LiteLLM; Claude Haiku 5.5 (narracja), Claude Sonnet 5.5 (analizy pogłębione), Gemini Flash-Lite i DeepSeek jako zapas | Patrz Fundamenty, sekcja 5                                                       |
| Obserwowalność          | OpenTelemetry → Grafana Cloud, Sentry, Langfuse dla LLM, zewnętrzny monitoring dostępności                                   | Wiemy, który agent, model lub źródło przestało działać                           |
| Sekrety                 | SOPS + age, GitHub Environments, gitleaks, push protection                                                                   | Bezpieczne w publicznym repo, bez dostawcy                                       |
| CI/CD                   | GitHub Actions → obrazy w GHCR → wdrożenie Docker Compose przez SSH z zatwierdzeniem                                         | Darmowe dla repo publicznego, proste do odtworzenia                              |
| Infrastruktura jako kod | Terraform (Oracle, Cloudflare) + Ansible                                                                                     | Każde środowisko odtwarzalne jedną komendą                                       |
| UI design               | Figma (system projektowy) + Lovable tylko do klikalnych prototypów                                                           | Patrz Fundamenty, sekcja 7                                                       |
| Licencja                | AGPL-3.0                                                                                                                     | Kopie hostowane jako usługa też muszą udostępniać kod (decyzja z E1, 2026-11-22) |

### Doprecyzowanie z E1

Pakiet Pythona w `services/platform/` nazywa się **`goatcash`**, a nie `platform`:
nazwa `platform` przesłania moduł standardowy Pythona o tej samej nazwie i psuje biblioteki,
które go używają. Granice modułów są takie jak w Fundamentach, sekcja 2:
`goatcash.<moduł>.api` (publiczne) i `goatcash.<moduł>._impl` (prywatne).

## Zasady nadrzędne

1. Analizy per aktyw, nie per użytkownik.
2. Jedna ścieżka kodu dla live i backtestu.
3. Żadnych cichych fallbacków: brak danych to stan jawny, widoczny w UI.
4. Każdy dostawca za adapterem.
5. Etap kończy się bramką jakości.

## Rozważane alternatywy

Porównania hostingu, modeli i narzędzi są w Fundamentach (sekcje 4, 5, 7). Odrzucone
m.in.: mikroserwisy od startu (koszt utrzymania dla jednej osoby), Celery/Ray (ciężkie),
Lovable jako docelowy frontend (prototypy tak, produkcja nie), Binance (wykluczony).

## Konsekwencje

- Jeden język backendu i jeden frontendu; CI pilnuje granic modułów od pierwszego dnia.
- Zależność od darmowych planów (Oracle, Cloudflare, Grafana) w fazie budowy; migracja na
  płatny VPS w UE jest zaplanowana na E16 i sprowadza się do zmiany konfiguracji.
- AGPL-3.0 ogranicza zamknięte, komercyjne kopie platformy.
