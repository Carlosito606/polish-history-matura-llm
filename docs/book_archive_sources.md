# Portale archiwizujące/indeksujące książki historyczne — research + dataset

Cel: poza Wikipedią polską, jakie portale legalnie archiwizują/indeksują książki historyczne
(i pokrewne otwarte zasoby), żeby wzbogacić RAG pod maturalne pytania z historii. Wynik badania
zapisany też jako dataset: `kb/external_sources/sources_catalog.{csv,json}` (14 pozycji) +
uruchamialna próbka CC0 z Wikidata: `kb/external_sources/wikidata_polish_monarchs_sample.json`.

Zasada z `CLAUDE.md`: żadnego materiału chronionego prawem autorskim w repo — tylko listy URL,
skrypty pobierające i to, co jest naprawdę CC0/domena publiczna.

## A. Portale archiwizujące/indeksujące książki historyczne

| Portal | Licencja | Dostęp | Wartość | Verdict |
|---|---|---|---|---|
| **Wolne Lektury** — wolnelektury.pl | Wolna Sztuka 1.3 (dawniej CC BY-SA), per książka; domena publiczna dla autorów zmarłych >70 lat temu | REST API `wolnelektury.pl/api/` (JSON/XML, bez klucza) + txt/html/epub/pdf | Czyste, zredagowane teksty źródłowe (kazania, pamiętniki, mowy) + metadane (autor/epoka/gatunek) idealne pod pytania ze źródłem | **use** |
| **Wikiźródła (pl.wikisource.org)** | CC BY-SA 4.0 (tekst wiki) / domena publiczna (oryginały) | MediaWiki API (ten sam, co Wikipedia) + zrzuty XML na dumps.wikimedia.org | Pełne konstytucje (1791/1815/1921/1935/1952/1997), traktaty, kategoria „Dokumenty historyczne” — dokładnie to, co CKE testuje w zadaniach źródłowych | **use** |
| **Federacja Bibliotek Cyfrowych (FBC)** — fbc.pionier.net.pl | zależna od biblioteki źródłowej (metadane Dublin Core zwykle otwarte; same obiekty różnie) | OAI-PMH (otwarte, bez klucza), OpenSearch, eksport CSV listy 130+ bibliotek | Master-indeks polskich bibliotek cyfrowych — dosłowna odpowiedź na „portal indeksujący książki historyczne”, ale to tylko wskaźniki/metadane | **maybe** |
| **Polona** (Biblioteka Narodowa) — polona.pl | per obiekt: domena publiczna/CC0 albo wszelkie prawa zastrzeżone, oznaczone na stronie obiektu | UI + IIIF image API; deweloperskie API przez `cpa.gov.pl/store/apis/info?name=polona` (wymaga rejestracji/tokenu) | Największe zbiory zeskanowanych książek/prasy historycznej, ale jako skany stron — trzeba OCR + sprawdzenie licencji per egzemplarz | **maybe** |
| **Encyklopedia Orgelbranda** (1859/1872/1898) | domena publiczna (wyd. 1859–1898) | transkrypcja na Wikiźródłach: `pl.wikisource.org/wiki/Indeks:S._Orgelbranda_Encyklopedia_Powszechna_(1859)` (ten sam pipeline co wyżej); skany też na Polonie/Cybra Łódź/JBC (wymagają OCR) | Definicje/terminologia, ale XIX-wieczna pisownia i historiografia sprzed 1945 nie pasują do współczesnego ujęcia w informatorze CKE | **maybe** |
| **Europeana** — europeana.eu / api.europeana.eu | metadane zawsze CC0 1.0; same obiekty per-item wg rightsstatements.org (`edmRights`) | darmowy klucz API (self-service, `api.europeana.eu/en`) | Agreguje też polskie zbiory (przez FBC), ale w dużej mierze duplikuje Polonę/FBC — niska wartość krańcowa dla tego zadania | **maybe** |
| **KRONIK@** — kronika.gov.pl (nowy, 2025) | wg komunikatu MC: „zgodnie z licencją, najczęściej domena publiczna” — niezweryfikowane per obiekt | portal www; publiczne API nie zostało znalezione (wzmiankowane tylko API integracyjne dla partnerów) | Potencjalnie duże (~4,5 mln obiektów) źródło w przyszłości, ale za wcześnie/za mało udokumentowane na 40-minutowy research | **maybe** |
| **dane.gov.pl** (Otwarte Dane) — w tym zbiór „Pomniki historii” | ustawa o ponownym wykorzystywaniu informacji sektora publicznego; licencja podana per zbiór (często CC0/CC BY) | REST API `api.dane.gov.pl/doc` + zasoby per-zbiór, np. `dane.gov.pl/pl/dataset/168/resource/35931` | Wąskie, ale legalne źródło faktów (nazwy pomników historii + daty rozporządzeń); strona zbioru renderuje się przez JS, więc dokładny schemat nie został w pełni zweryfikowany w tym przebiegu | **maybe** |
| **IPN — Przystanek Historia / Biblioteka Cyfrowa IPN** | „wszelkie prawa zastrzeżone” (potwierdzone na stronie) — darmowe pobranie ≠ wolna licencja | zwykłe linki HTTPS do PDF (~800 pozycji), bez API | Treściowo świetne (historia XX w., zgodne z zakresem CKE), ale zablokowane licencyjnie — dokładnie pułapka, przed którą ostrzegają zasady hackathonu | **avoid** |
| **Project Gutenberg (półka PL)** — gutenberg.org/browse/languages/pl | licencja PG, domena publiczna | mirror/rsync, bez klucza | Mała, głównie beletrystyka (Mickiewicz, Sienkiewicz) — fikcja nie nadaje się jako źródło twardych faktów egzaminacyjnych | **avoid** |
| **Internet Archive** — archive.org | mieszana per obiekt: prawdziwa domena publiczna (`_djvu.txt` do pobrania) vs. Controlled Digital Lending (tylko wypożyczenie, DRM, **nie** wolno redystrybuować) | metadata + advancedsearch API; pełny tekst tylko dla obiektów public-domain | Ryzykowne: pierwszy wynik wyszukiwania „historia Polski” (Zamoyski, *Poland: A History*) to pozycja CDL-only — łatwo przypadkiem złamać zasadę „bez łamania loginów/DRM” | **avoid** |
| **Google Books API / HathiTrust** | regulamin Google Books zabrania masowego scrapowania fragmentów chronionych; HathiTrust poza instytucjami partnerskimi ogranicza pełny tekst do pozycji public-domain w USA i wymaga umowy na Data API | Google: tylko metadane/fragmenty; HathiTrust: dostęp bramkowany | Wprost łamie zasadę „nie pobieraj z serwisów, których regulamin tego zabrania” | **avoid** |

## B. Inne otwarte/legalne źródła faktów strukturalnych (poza książkami)

| Źródło | Licencja | Dostęp | Wartość | Verdict |
|---|---|---|---|---|
| **Wikidata** — wikidata.org, SPARQL: `query.wikidata.org/sparql` | **CC0 1.0** (całość danych) | publiczny endpoint SPARQL (bez klucza), REST API, zrzuty JSON | Deterministyczne pytania o chronologię/kolejność (daty panowania, bitew, traktatów) — **zweryfikowane działającym zapytaniem**, patrz niżej | **use** |

### Zweryfikowane zapytanie Wikidata (rzeczywisty wynik, nie hipoteza)

Zapytanie SPARQL o władców Polski (pozycja `wd:Q3273712` „King of Poland”, kwalifikatory
P580/P582 = początek/koniec sprawowania urzędu), wykonane na żywo w trakcie tego researchu:

```sparql
SELECT ?rulerLabel ?start ?end WHERE {
  ?ruler p:P39 ?stmt .
  ?stmt ps:P39 wd:Q3273712 .
  ?stmt wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?stmt pq:P580 ?start .
  OPTIONAL { ?stmt pq:P582 ?end }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pl". }
}
ORDER BY ?start LIMIT 200
```

Przykładowy, realny wynik (pełne 37 wierszy w `kb/external_sources/wikidata_polish_monarchs_sample.json`):

| władca | początek | koniec |
|---|---|---|
| Bolesław I Chrobry | 1025-04-18 | 1025-06-17 |
| Mieszko II Lambert | 1025-12-25 | 1031-01-01 |
| Bolesław II Szczodry | 1076-12-25 | 1079-01-01 |
| Henryk I Brodaty | 1201-01-01 | 1238-01-01 |

**Zastrzeżenie (znalezione empirycznie, nie teoretyczne):** naiwne zapytanie bez filtra rangi
zwraca też pretendentów, którzy nigdy faktycznie nie panowali (np. elekta *Franciszek Ludwik
Burbon-Conti*, nigdy nie koronowany, czy *Maria Karolina Sobieska* — księżniczka, nie
monarchini). Dane trzeba czyścić (filtr rangi + ew. `P31`/kraj) zanim staną się „ground truth” do
pytań egzaminacyjnych. To realny koszt dodatkowy przy skądinąd bezpiecznym prawnie źródle.

Skrypt do ponownego uruchomienia: `python -m kb.external_sources.fetch_wikidata_chronology --out <ścieżka>`.

## Podsumowanie / rekomendacja na hackathon

1. **Rozszerz istniejący pipeline `kb/` (dump Wikipedii) o dump Wikiźródeł** — zero nowego
   kodu, ten sam `build_chunks.py`/`build_index.py`, dodaje realne teksty pierwotne (konstytucje,
   traktaty), których w encyklopedycznej prozie Wikipedii brakuje.
2. **Dodaj Wolne Lektury przez ich REST API** — czysty tekst, jawna wolna licencja, niski koszt.
3. **Wikidata jako generator pytań chronologicznych/porządkujących** — CC0 usuwa całe ryzyko
   prawne, ale wymaga warstwy czyszczącej (rangi, kwalifikatory) zanim trafi do zestawu pytań.
4. **Polona/FBC/Orgelbrand/Europeana/dane.gov.pl/KRONIK@** — realne i legalne, ale niższy
   stosunek wartości do wysiłku w 40-minutowym (i szerzej: hackathonowym) budżecie czasu;
   warte rewizyty po hackathonie, nie na krytycznej ścieżce teraz.
5. **Twarde „avoid”**: IPN (za darmo, ale bez wolnej licencji — nie wrzucać do repo/treningu),
   Gutenberg PL (zła treść — fikcja), Internet Archive (łatwo złapać egzemplarz tylko-do-wypożyczenia),
   Google Books/HathiTrust (regulamin wprost zabrania potrzebnego trybu dostępu).

## Dataset

- `kb/external_sources/sources_catalog.csv` / `.json` — pełna tabela 14 źródeł (id, url, typ,
  licencja, sposób dostępu, wartość, wysiłek, verdict, uzasadnienie).
- `kb/external_sources/wikidata_polish_monarchs_sample.json` — 37 realnie pobranych wierszy CC0.
- `kb/external_sources/fetch_wikidata_chronology.py` — skrypt do odtworzenia/rozszerzenia próbki.
- `kb/external_sources/README.md` — skrót + tabela verdictów.

Nic z powyższego nie zawiera treści chronionej prawem autorskim — tylko katalog źródeł, skrypt
i dane CC0.
