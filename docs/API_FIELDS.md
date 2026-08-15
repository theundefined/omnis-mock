# API_FIELDS.md — pola odpowiedzi Layer 2 (wyszukiwarka katalogu), pole po polu

Ten plik uzupełnia `docs/SPEC.md` (REQ-15..REQ-18b): SPEC.md mówi CO endpoint musi zwrócić i jakie ma
zachowanie na brzegach, ten plik mówi DLACZEGO każde pole w fixture (`src/omnis_mock/search_data.py`)
tam jest — albo dlaczego pole obecne w realnym Primo świadomie w mocku nie występuje.

Źródła danych o realnym kształcie API (patrz też `docs/SPEC.md` "Kryterium akceptacji" i historia w
`docs/PLAN.md`):

- `omnis-py/debug_search_output/{1_top_search,2_delivery,3_raw_holding}.json` — statyczne zrzuty
  prawdziwych odpowiedzi Primo (zapytanie "harry potter", konto `BR484150@48OMNIS_BRP`).
- `omnis-mobile/docs/api-verification-response.md` — empiryczna weryfikacja bisekcją pole-po-polu na
  żywym API, w tym ustalenie o `holKey` (patrz REQ-18b w SPEC.md).
- `omnis-py/src/omnis/client.py` (`search_books()` i helpery, linie 436-717) i `omnis-mobile`'s
  `data/model/Models.kt`, `data/remote/OmnisApi.kt` — dokładny zestaw pól czytanych przez każdego z dwóch
  niezależnych klientów tego API.

Kolumny: **W realnym Primo** — czy pole faktycznie występuje w przechwyconych odpowiedziach; **`omnis-py`**
/ **`omnis-mobile`** — czy dany klient je czyta (na podstawie jego kodu, nie domysłu); **W mocku** — czy
`search_data.py` je generuje.

## Zasada włączania/wykluczania

Włączone: każde pole czytane przez **którykolwiek** z dwóch klientów, plus pola bez konsumenta, których
koszt wygenerowania jest zerowy i podnoszą realizm (np. `genre`/`subject`/`stackMapUrl` — `omnis-mobile`
ich nie czyta, ale Gson je bezkosztowo zignoruje, a `omnis-py` już z nich korzysta).

Wykluczone: pola, które są **wewnętrzną telemetrią/klasyfikacją bez żadnego konsumenta** i które dla
fikcyjnych rekordów demo byłyby czystym, niesprawdzalnym szumem (np. kody klasyfikacyjne biblioteki
`lds04`..`lds32`, timing wewnętrznego wyszukiwania). Wyjątek jednego pola z tej kategorii, `holKey`, jest
udokumentowany osobno niżej — to jedyne "dekoracyjne" pole holdingu, które okazało się mieć realny wpływ
na zachowanie API.

## `pnx.display`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `title` | ✅ | ✅ | ✅ | ✅ | |
| `edition` | ✅ | ✅ | ✅ | ✅ | |
| `type` | ✅ | ✅ (`resource_type`) | ✅ (`resourceType`) | ✅ | |
| `language` | ✅ | ✅ | ❌ | ✅ | |
| `format` | ✅ | ✅ (`physical_description`) | ❌ | ✅ | |
| `genre` | ✅ | ✅ (`genres`) | ❌ | ✅ | zero kosztu dla Kotlina (Gson ignoruje) |
| `subject` | ✅ | ✅ (`subjects`) | ❌ | ✅ | jw. |
| `series` | ✅ | ✅ (via `addata.seriestitle`, nie ten klucz) | ❌ | ✅ | dodane dla realizmu koperty, klient czyta z `addata` |
| `source`, `identifier`, `creationdate`, `publisher`, `mms`, `contributor`, `place`, `version` | ✅ | ❌ | ❌ | ✅ | brak konsumenta, ale realistyczna, tania dekoracja koperty |
| `description` | ✅ | ❌ | ❌ | ❌ | tekst opisowy — dla fikcyjnych tytułów byłby czystym wymysłem bez żadnej wartości informacyjnej |
| `lds04`, `lds05`, `lds07`, `lds10`, `lds11`, `lds12`, `lds15`, `lds18`, `lds19`, `lds30`, `lds31`, `lds32` | ✅ (~12 pól) | ❌ | ❌ | ❌ | wewnętrzne kody klasyfikacyjne/adnotacje biblioteki — zero konsumentów, niemożliwe do sensownego wypełnienia dla fikcyjnych rekordów |

## `pnx.addata`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `btitle` | ✅ | ✅ | ✅ | ✅ | |
| `au` | ✅ (bywa `null`!) | ✅ | ✅ | ✅ (zawsze wypełnione) | w realnej próbce bywało `null`, gdy autorstwo niejednoznaczne — nasze fikcyjne dzieła mają zawsze jednego autora, więc zawsze wypełnione |
| `pub` | ✅ | ✅ | ✅ | ✅ | |
| `date` | ✅ | ✅ | ✅ | ✅ | |
| `isbn` | ✅ | ✅ | ✅ | ✅ | |
| `edition` | ✅ | ❌ (czyta `display.edition`) | ❌ | ✅ | realistyczna dekoracja, real Primo duplikuje edition w obu miejscach |
| `seriestitle` | ✅ | ✅ (`series`) | ❌ | ✅ | |
| `aulast`, `aufirst`, `auinit`, `addau`, `cop`, `format`, `genre`, `ristype` | ✅ | ❌ | ❌ | ✅ | tanie, realistyczne, zero ryzyka |
| `abstract`, `contributorfull`, `originatingSystemIDSubject`, `originatingSystemIDContributor`, `oclcid` | ✅ | ❌ | ❌ | ❌ | wewnętrzne identyfikatory źródłowego systemu / długi tekst — zero konsumentów, dla fikcyjnych rekordów czysty wymysł |

## `pnx.control`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `recordid` | ✅ | ✅ (alma-id) | ✅ | ✅ | musi mieć prefiks `alma` |
| `sourcerecordid` | ✅ | ✅ (bare mmsid) | ✅ (preferowane przed `recordid`) | ✅ | |
| `sourceid`, `originalsourceid`, `sourcesystem`, `sourceformat`, `score`, `isDedup` | ✅ | ❌ | ❌ | ✅ | tanie, realistyczne |

## `pnx.sort`, `pnx.facets`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `facets.frbrgroupid` | ✅ | ✅ (grupowanie wersji) | ✅ | ✅ | **kluczowe** dla group expansion (REQ-16) |
| `facets.frbrtype` | ✅ | ❌ | ❌ | ✅ | dekoracja |
| `sort.title`, `sort.author`, `sort.creationdate` | ✅ | ❌ | ❌ | ✅ | dekoracja, tanie |

## Koperta odpowiedzi `GET /primaws/rest/pub/pnxs` (poza `docs[]`)

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `info.total` | ✅ | ❌ (brak paginacji w `search_books`) | ✅ (`PnxInfo.total`, "Załaduj więcej") | ✅ | |
| `info.totalResultsLocal`, `.totalResultsPC`, `.first`, `.last` | ✅ | ❌ | ❌ | ✅ | dekoracja koperty `info`, tanie |
| `beaconO22`, `highlights`, `timelog`, top-level `facets` (lista fasetowań UI) | ✅ | ❌ | ❌ | ❌ | telemetria/dane do widżetów UI wyszukiwania (podświetlanie, czas wykonania, liczniki fasetowań) — zero konsumentów w żadnym z dwóch klientów, i wymagałyby wymyślonych rozkładów statystycznych bez żadnego znaczenia |

## `delivery.holding[]` (obiekt zwracany w `POST /primaws/rest/pub/delivery`)

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `mainLocation` | ✅ | ✅ | ✅ | ✅ | |
| `libraryCode` | ✅ | ✅ | ✅ | ✅ | |
| `subLocation` | ✅ | ✅ (`sub_location`, adres) | ✅ | ✅ | |
| `availabilityStatus` | ✅ | ✅ | ✅ | ✅ | |
| `holdId` | ✅ | ✅ (w body do `ILSServices`) | ✅ | ✅ | |
| `stackMapUrl` | ✅ | ✅ (`maps_url`) | ❌ (`Holding` w Kotlinie nie ma tego pola) | ✅ | |
| **`holKey`** | ✅ | ✅ (przekazywane 1:1, nie parsowane) | ❌ (luka w `Models.kt`, `omnis-mobile/docs/api-verification-response.md` rekomenduje dodanie) | ✅ | **Funkcjonalnie wymagane** przez `POST ILSServices/holdings/{id}` — bez niego endpoint zwraca `200` z pustą `items`, z nim zwraca poprawny `itemstatusname`. Zweryfikowane empirycznie bisekcją pole-po-polu na żywym Primo (patrz `omnis-mobile/docs/api-verification-response.md`, sekcja 1) — jedyne z pozostałych 16 pól poniżej, które ma jakikolwiek wpływ na zachowanie API. Mock replikuje tę zależność (SPEC.md REQ-18b): `holding_status()` w `search_data.py` zwraca dane TYLKO gdy przychodzące `locations[0]` zawiera niepusty `holKey`. |
| `isValidUser`, `organization`, `subLocationCode`, `callNumber`, `callNumberType`, `holdingURL`, `adaptorid`, `ilsApiId`, `matchForHoldings`, `relatedTitle`, `translateRelatedTitle`, `yearFilter`, `volumeFilter`, `singleUnavailableItemProcessType`, `boundWith`, `@id` | ✅ (16 pól) | ❌ | ❌ | ✅ (stałe realistyczne wartości) | Potwierdzone bisekcją, że **żadne** z tych 16 pól nie wpływa na odpowiedź `ILSServices/holdings` — obecne w mocku wyłącznie dla realizmu koperty, wartości stałe skopiowane 1:1 z realnego zrzutu (`3_raw_holding.json`) |
| Koperta `delivery` poza `holding[]` (`bestlocation`, `electronicServices`, `additionalElectronicServices`, `deliveryCategory`, `serviceMode`, `availability`, `displayedAvailability`, `displayLocation`, `titleRequestableAtItemLevel`, `recordOwner`, `physicalServiceId`, ... ~20 dalszych pól) | ✅ (~29 pól) | ❌ | ❌ | ❌ | żaden znany klient nie czyta z koperty `delivery` nic poza `holding[]` — replikowanie tego byłoby złożonością bez żadnej obserwowalnej różnicy zachowania |
| Koperta `DeliveryItem` poza `pnx`/`delivery` (`beaconO22`, `context`, `@id`, `adaptor`, `enrichment`) | ✅ | ❌ | ❌ | ❌ | jw., dodatkowo `enrichment.*BrowseObject` wymagałoby wymyślonych numerów klasyfikacji UKD bez żadnego znaczenia dla fikcyjnych tytułów |

## `GET /primaws/rest/pub/getPhysicalService/{bare_mmsid}`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `physicalServiceId` (top-level) | ✅ | ✅ | ✅ | ✅ | jedyne pole w tej odpowiedzi u obu klientów; potwierdzone empirycznie jako top-level string |

## `POST /primaws/rest/priv/ILSServices/holdings/{physicalServiceId}`

| Pole | Realny Primo | `omnis-py` | `omnis-mobile` | W mocku | Uwagi |
|---|---|---|---|---|---|
| `data.itemInfo.locations[].items[].itemstatusname` | ✅ | ✅ (regex daty + "przekroczon") | ✅ | ✅ | jedyna ścieżka czytana przez obu klientów; brak realnego zrzutu pełnej koperty tego endpointu (tylko ta ścieżka była empirycznie weryfikowana), więc mock nie dodaje niczego poza nią |

## Świadome uproszczenia zachowania (nie tylko kształtu pól)

- **`delivery` nie waliduje, że przekazane `q`/`qInclude` faktycznie odpowiadają grupie, do której należą
  przekazane alma-id.** Realne Primo to robi (wewnętrznie re-uruchamia search i filtruje po stronie
  wyników — stąd wymóg wywoływania `delivery` raz na grupę z jej własnymi id, udokumentowany w
  `omnis-py/CLAUDE.md`). Oba znane klienty (Python, Kotlin) zawsze się do tego stosują, więc efekt
  zewnętrzny mocka jest identyczny — symulowanie wewnętrznego mechanizmu re-search byłoby złożonością bez
  obserwowalnej różnicy zachowania dla jakiegokolwiek zgodnego z dokumentacją klienta.
- **`holding_status()` sprawdza tylko obecność/niepustość `holKey`, nie jego treść.** Realne Primo
  prawdopodobnie parsuje ten string (`mid=...,libraryId=...,locationCode=...`), ale żaden znany klient go
  nie modyfikuje między pobraniem z `delivery` a wysłaniem do `ILSServices` — sam fakt obecności
  wystarcza do odtworzenia obserwowanego zachowania bez rekonstruowania nieudokumentowanego formatu.
