# ADR-0005: Bramka modeli językowych

- **Status:** proponowana (zatwierdzenie: scalenie PR `docs/E2-adr`)
- **Data:** 2026-11-22
- **Etap:** E2
- **Źródło:** Fundamenty sekcja 5 („Zarządzanie wieloma modelami”), ADR-0001

## Kontekst

Modele językowe piszą narracje, wyciągają zdarzenia z newsów, odpowiadają w czacie i oceniają
wyniki innych modeli. Liczby w tekście muszą zgadzać się z danymi (G10: 0 niezgodnych liczb na
500 narracjach), koszt ma twardy budżet, a awaria dostawcy nie może zatrzymać analizy. Treści
z internetu (newsy) mogą zawierać próby wstrzyknięcia poleceń.

## Decyzja

1. **LiteLLM jako biblioteka w module `goatcash.llm`** (nie osobny serwer proxy): mniej
   procesów na VM, klucze tylko w procesie `worker`/`api`.
2. **Aliasy ról zamiast nazw modeli:** `narrator`, `extractor`, `chat`, `deep`, `judge`.
   Plik konfiguracyjny w repo mapuje alias → model główny → modele zapasowe; wersje modeli
   przypięte (identyfikatory z datą, gdzie dostawca je oferuje). Zmiana modelu lub wersji
   tylko przez PR z wynikami ewaluacji (pipeline krok 4).
3. **Prompty jako pliki** `prompts/<rola>/<wersja>.yaml`; numer wersji zapisywany w każdym
   wyniku (`narratives` i Langfuse).
4. **Wyjście zawsze walidowane:** odpowiedź w strukturze (JSON Schema / Pydantic); liczby
   w narracji porównywane z danymi wejściowymi (walidator liczb); niezgodność = ponowienie,
   potem model zapasowy, potem narracja z szablonu bez LLM. Nigdy nie publikujemy tekstu,
   który nie przeszedł walidacji.
5. **Odporność:** timeout per alias, 2 ponowienia z backoffem, przełączenie na zapasowy model,
   wyłącznik obwodu per dostawca, a gdy wszystko zawiedzie, szablon.
6. **Budżety:** dzienny limit kosztów per alias i per użytkownik w Valkey; po przekroczeniu
   tańszy model albo szablon; alert po przekroczeniu 80%. Twarde limity także po stronie
   dostawcy (np. OpenRouter 5 USD).
7. **Wstrzykiwanie poleceń:** treści zewnętrzne trafiają do promptu wyłącznie jako dane
   (oddzielone i oznaczone), modele **nie** mają narzędzi z efektami ubocznymi (żadnych zapisów,
   zleceń, wywołań sieci); zbiór testów odporności w ewaluacji G10.
8. **Prywatność:** do dostawców nie trafiają dane osobowe; identyfikator użytkownika jest
   pseudonimizowany; telemetria w Langfuse (koszt, opóźnienie, wersja promptu, wynik walidacji).
9. **Sekrety:** klucze dostawców w `infra/secrets/<env>.enc.yaml` (SOPS), nigdy w kodzie.

## Rozważane alternatywy

| Opcja                              | Za                            | Przeciw                                                        |
| ---------------------------------- | ----------------------------- | -------------------------------------------------------------- |
| LiteLLM jako serwer proxy          | wspólny punkt dla wielu usług | kolejny proces i baza; u nas korzysta tylko jeden moduł        |
| SDK każdego dostawcy osobno        | pełny dostęp do funkcji       | własna obsługa przełączania i kosztów; kod zależny od dostawcy |
| Tylko jeden dostawca               | prostota                      | awaria lub zmiana cen dostawcy zatrzymuje narracje             |
| Swobodny tekst bez walidacji liczb | szybciej                      | sprzeczne z G10; ryzyko publikacji błędnych liczb              |

## Konsekwencje

- Moduł `llm` powstaje w E10; w E2 ustalamy tylko kontrakt (aliasy, format promptów, zapis
  wersji) i budżety.
- Ewaluacja przy każdej zmianie `prompts/` lub konfiguracji modeli (pipeline krok 4) blokuje
  scalenie przy regresji.
- Ryzyko: LiteLLM jako zależność z dużą liczbą wydań; wersja przypięta, aktualizacje przez
  Dependabota z cooldownem 7 dni i ewaluacją.
