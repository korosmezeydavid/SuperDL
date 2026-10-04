# Super Surf – 1. mérföldkő: architektúra és adatmodellek

Állapot: az első mérföldkő terve, 2026-10-04. A későbbi, helyben elkészült
0.1.0 próbamodul leírása: `modules_src/supersurf/README.md`. Éles kiadás nincs.

## Hatókör és beillesztés

A Super Surf első célplatformja a Windows SuperDL: külön telepíthető modul
(`modules_src/supersurf/`), nem a letöltő Core része. A lekérdezési és olvasási
logika tiszta Python szolgáltatás, amely nem importál wxPython-t. A modul
belépőpontja a meglévő `CoreContext` / `WxHost` szerződésen keresztül nyitja a
felületet. Az Android SuperDL külön Kotlin-implementációt igényel; az alábbi
mezők és szemantika közös szerződésként szolgálhatnak, Python-kód megosztása
nélkül. A VoiceOver csak egy későbbi iOS kliens esetén releváns, jelenleg nincs
SuperDL iOS megvalósítás.

Rétegek: felület → vezérlő (állapot, megszakítás) → `ResearchService` →
forrásspecifikus API-kapcsolók vagy `ReaderService` → hálózati kliens. A
megjelenítő az eredményt kapja, nem nyers, tetszőleges weboldal-HTML-t. Az
API-kapcsolók strukturált JSON-t dolgoznak fel; a Reader csak olyan URL-nél
dolgozik HTML-lel, amelyhez nincs megfelelő strukturált API.

## Közös adatmodellek (logikai szerződés)

Az itt szereplő típusok platformfüggetlen leírások. A későbbi Python
`dataclass` és Kotlin `data class` ezeknek megfelelően készülhet.

### `ResearchQuery`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `request_id` | UUID/szöveg | Egy lekérdezés egyedi azonosítója; a későn érkező választ ehhez kötjük. |
| `kind` | `wikipedia_search \| article_url \| weather \| exchange_rate \| dictionary` | A választott művelet; nem következtetjük pusztán a beírt szövegből. |
| `input` | nem üres szöveg | Keresőszó, URL, hely vagy szó az adott művelet szerint. |
| `language` | BCP 47 nyelvi címke, alapérték `hu` | Kért nyelv, amelyet a forrás lehetőségeihez igazítunk. |
| `parameters` | műveletspecifikus, típusos adatok | Például árfolyamnál alap- és céldeviza; időjárásnál mértékegység. Nem tetszőleges URL vagy fejléc. |

Az `article_url` bemenetnél kizárólag `http`/`https` URL fogadható el; a
normalizált URL külön belső érték, az eredeti bemenet megmarad hibajelzéshez.
Egy kérés csak egy műveletet jelent. Több Wikipédia-találat esetén a szolgáltatás
nem állítja bizonyossággal, hogy az első a kívánt cikk: az eredményben a pontos
cím és forrás látható, a felület később találatválasztást kínálhat.

### `ResearchResult`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `request_id` | UUID/szöveg | Az eredeti kérés azonosítója. |
| `kind` | a `ResearchQuery.kind` értéke | A válasz típusa. |
| `status` | `success \| empty \| error \| cancelled` | A lekérdezés végállapota; a betöltés külön UI-állapot. |
| `title` | szöveg vagy null | Ember által olvasható eredménycím. |
| `content` | `ReaderContent` vagy null | Strukturált, biztonságos megjelenítési tartalom. |
| `source_name` | szöveg vagy null | A forrás közérthető neve. |
| `source_url` | ellenőrzött URL vagy null | Az eredeti forráshoz vezető hivatkozás. |
| `retrieved_at` | időpont vagy null | A tényleges lekérés ideje; nem keverhető a cikk publikálási idejével. |
| `error` | `ResearchError` vagy null | Gépileg azonosítható ok és magyar, felolvasható üzenet. |
| `warnings` | szövegek listája | Például hiányos cikk vagy bizonytalan találat. |

Invariáns: `success` esetén van olvasható `content`; `empty` és `error`
esetén nincs kitalált tartalom. A `source_url` és az időbélyeg a másolható
exportban is szerepel, hogy az eredet ne vesszen el.

### `ReaderContent`

| Mező | Típus | Jelentés |
| --- | --- | --- |
| `title` | nem üres szöveg | A dokumentum címe, megjelenítéskor egyetlen H1. |
| `blocks` | rendezett `ContentBlock` lista | A cikk olvasási sorrendje. |
| `byline` | szöveg vagy null | Szerző, ha a forrásból megbízhatóan kinyerhető. |
| `published_at` | időpont vagy null | Csak akkor, ha egyértelműen azonosítható. |
| `canonical_url` | ellenőrzött URL vagy null | Az eredeti cikk címe, ha biztonságosan azonosítható. |
| `excerpt` | szöveg vagy null | Rövid kivonat, nem a törzsszöveg helyettesítője. |

`ContentBlock` változatok: `heading(level: 2|3, text)`, `paragraph(text)`,
`list(items, ordered)`, `quote(text)`, `link(label, url)` és indokolt esetben
`image_alt(text)`. A teljes cikket nem lapítjuk egyetlen szövegmezővé. Üres
blokkok és ismétlődő címsorok kiszűrendők. Az oldal címe H1, a kinyert
címsorok relatív szintje H2/H3; a forrás hibás címsorszintjeit rendezni kell.
Az egyszerű HTML nézet csak ezekből a biztonságos blokkokból épülhet, HTML
escape-pel és aktív tartalom nélkül. Ugyanezekből plain text/Markdown export
készülhet. A blokkok sorrendje egyezik a fókusz- és felolvasási sorrenddel.

### Kiegészítő szerződések

`ResearchError`: `code` (`invalid_input`, `unsupported_url`, `blocked_url`,
`timeout`, `network`, `http_error`, `invalid_response`, `no_content`,
`rate_limited`), `message_hu`, opcionális `retryable`. Belső stack trace és
nyers HTML nem kerül a felületre.

`ResearchProgress`: `request_id`, `phase` (`validating`, `fetching`,
`extracting`, `rendering`), magyar státuszszöveg. A vezérlő fázisváltáskor
egyszer jelzi a státuszt, majd egyszer a végállapotot; nem beszéli túl a
képernyőolvasót. Megszakítás és új kérés után csak az aktuális `request_id`
eredménye írhatja felül a képernyőt. A fókusz a bevitelen marad betöltéskor;
eredménynél kiszámíthatóan a H1-re vagy az eredmény elejére kerül.

## Szolgáltatási határok és döntések a következő lépésekhez

- `ResearchService.run(query, cancel_token, progress)` azonos szerződéssel
  választja ki a megfelelő kapcsolót. A hálózati művelet háttérben fut, nem
  fagyaszthatja le a GUI-t.
- `WikipediaConnector` előbb keresési találatot azonosít, majd a kiválasztott
  cikk strukturált összefoglalóját adja vissza. A pontos végpontot és annak
  feltételeit a 2. lépésben ellenőrizni kell.
- `ReaderService` letöltés → tartalomtípus/karakterkódolás ellenőrzés → DOM
  feldolgozás → főtartalom-azonosítás → `ReaderContent`. A `header`/`aside`
  elemeket nem töröljük vakon, mert tartalmazhatnak címet, szerzőt vagy
  cikkrészt; előbb a fő cikkhatárt azonosítjuk. Ha nem található megbízható
  tartalom, `no_content`, nem üres vagy félrevezető „siker” az eredmény.
- A Reader URL-jeinél a helyi/belső címek, visszairányítások és DNS-váltások
  külön ellenőrzést igényelnek; fájl-URL és nem webes séma tiltott. Méret-,
  idő- és átirányítási limit kell, valamint nincs JavaScript-futtatás,
  bejelentkezés vagy sütis munkamenet. A nem nyilvános/paywallos cikkek teljes
  kinyerése nem ígérhető.
- A UI egy egyszerű kereső/URL mezőt, módválasztást, státuszt, eredménynézetet,
  másolás- és mentésműveletet kap a 4. lépésben. A Core és a platform saját
  képernyőolvasója elsőbbséget élvez a saját hanggal szemben.

## Mérföldkő elfogadási pontja

Az első mérföldkő akkor zárható le, ha a platformhatár, a három fő modell, az
eredetadatok, a hibák és a fókusz-/állapot-szerződés megfelel a felhasználói
elképzelésnek. A 2. lépés csak a visszajelzés és tesztelési egyeztetés után
indul; ez a dokumentum még nem állít működő funkciót.
