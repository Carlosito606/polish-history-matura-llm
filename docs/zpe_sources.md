# ZPE (zpe.gov.pl) — history e-materials used as sources

Attribution list only — no content is committed. Text lives in the git-ignored
`sources/raw/zpe/` and is rebuilt with `scripts/fetch_zpe.py` (catalog → fetch → batches/chunks → docs).

## Licence gate (read this first)

- Source: Zintegrowana Platforma Edukacyjna, operated by the Ministerstwo Edukacji Narodowej;
  `robots.txt` = `Allow: /`. Only public, anonymous endpoints the site itself calls; sequential
  requests >= 1.5 s apart; UA `WMT-hackathon-research/1.0 (contact: see repository README)`; no login areas.
- Checked in Chromium (Playwright), in the server HTML and in the platform's own PDF/EPUB
  downloads: **the lesson prose of ZPE history e-materials carries no licence statement**, and
  the regulamin grants the public none. Licences appear only per element, in captions such as
  `Źródło: Contentplus.pl sp. z o.o., licencja: CC BY-SA 3.0.`
- So only the text of elements whose own caption shows CC BY / CC BY-SA / CC0 is kept
  (interactive maps, schematy, animations, galleries, timelines with such a caption).
  Lesson prose ("Wprowadzenie", "Przeczytaj", exercises, "Dla nauczyciela") is never kept.
  Public-domain captions cover the reproduced image, not ZPE's description: logged, not kept.
  Quotations from third-party books inside a kept element are stripped.
- CC BY-SA obliges attribution + share-alike for derived text; attribution is listed below
  (material title, URL, licence, author/licensor shown in the caption).

## Coverage

- Catalogue (stage E4 = liceum/technikum, subjects Historia + Historia PP 2022): 1108 e-materials.
- Processed (random order, so coverage is uniform across eras): 1108; kept 409, skipped 699, errors 0.
- Kept text: 222105 words. Licences in kept elements: CC BY-SA 3.0 (365), CC BY 3.0 (91), CC BY-SA 4.0 (28), CC BY-SA 2.5 (16), CC BY 4.0 (16), CC BY 2.0 (14), CC BY-SA 2.0 (14), CC BY 2.5 (6), CC0 (4).
- Per-material status and skip reasons: `sources/raw/zpe/manifest.csv` (git-ignored, rebuilt by the script).

## Kept materials

| # | Title | URL | Licence(s) | Author / licensor (from captions) | Words |
|---|---|---|---|---|---|
| 1 | (De)stabilizacja życia politycznego. Rok 1922 pod znakiem wyborów prezydenckich oraz parlamentarnych | https://zpe.gov.pl/b/PbN8JFj6p | CC BY-SA 3.0 | Contentplus.sp. z o.o. | 656 |
| 2 | Agresja ZSRS na Polskę. Wojna sowiecko‑fińska i aneksje sowieckie | https://zpe.gov.pl/b/PdYK0S2XR | CC BY-SA 3.0 | Contentplus.pl | 938 |
| 3 | Alma Mater Cracoviensis | https://zpe.gov.pl/b/P14QPtDry | CC BY-SA 3.0 | Krystian Chariza i zespół; Lestat, Wikimedia Commons | 286 |
| 4 | Ameryka Południowa po epoce kolonializmu | https://zpe.gov.pl/b/PfFoX94FK | CC BY-SA 3.0 | Contentplus.pl | 808 |
| 5 | Anglia, Skandynawia i Normanowie. Podboje normańskie | https://zpe.gov.pl/b/PB2LLT1RP | CC BY-SA 3.0 | Contentplus.sp. z o.o.; Contentplus.sp. z o.o. na podstawie R. F. Barkowski, Paryż 885-886 , Warszawa 2018, str. 142; Krystian Chariza i zespół | 704 |
| 6 | Apogeum rozbicia dzielnicowego i jego skutki | https://zpe.gov.pl/b/PmQzBu6lc | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Contentplus .pl sp. z o.o. na podstawie wodip.opole.pl | 948 |
| 7 | Architektura, sztuka i osiągnięcia techniczne Rzymian | https://zpe.gov.pl/b/PWiTqci59 | CC BY 2.0 | Jean-Pierre Dalbéra , Wikimedia Commons | 972 |
| 8 | Austria w czasie wojen XVIII w. Wojna siedmioletnia | https://zpe.gov.pl/b/P10N5oH1t | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o. na podstawie Bryan Rutherford, Wikimedia Commons; Contentplus.sp. z o.o. na podstawie Wikimedia Commons | 327 |
| 9 | Austro‑Węgry. Monarchia wielu narodów | https://zpe.gov.pl/b/Ptu2Ocrrp | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 784 |
| 10 | Batalia o „ziemie ruskie”. Wojny z Moskwą | https://zpe.gov.pl/b/PF8MZzK0j | CC BY-SA 3.0 | Contentplus.pl | 129 |
| 11 | Beczka z prochem. Sytuacja w Królestwie Polskim przed wybuchem powstania styczniowego | https://zpe.gov.pl/b/P7GleyiIO | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.pl; Contentplus.pl sp. z o.o.; Krkpr, Wikimedia Commons | 373 |
| 12 | Belgia – walka o własne państwo. Pierwsza połowa XIX w. | https://zpe.gov.pl/b/PCWydtnjH | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 843 |
| 13 | Betonowa granica dwóch światów. Budowa muru berlińskiego | https://zpe.gov.pl/b/PsDBbQORU | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie krainaoza.pl | 590 |
| 14 | Bitwa narodów i ostateczny upadek Napoleona | https://zpe.gov.pl/b/Pyj82NVTZ | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. na podstawie Wikimedia Commons | 649 |
| 15 | Bizancjum – greckie cesarstwo Rzymian | https://zpe.gov.pl/b/PrL6vowZK | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0 | Aleksiej Rodakow; Contentplus.pl sp. z o.o. | 744 |
| 16 | Blaski i cienie zwycięstwa pod Wiedniem. Ostatnie lata panowania Jana III Sobieskiego | https://zpe.gov.pl/b/P1B4pg4ez | CC BY-SA 3.0 | Contentplus.pl | 640 |
| 17 | Bliski Wschód po II wojnie | https://zpe.gov.pl/b/P5jHqZ5ZE | CC BY-SA 3.0 | Contentplus.pl; Contentplus.sp. z o.o. na podstawie Sepehr.Sǎsǎni, Wikimedia Commons | 199 |
| 18 | Bolesław Chrobry – pierwszy król Polski | https://zpe.gov.pl/b/PKvdiOo0c | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Ośrodek Rozwoju Edukacji | 80 |
| 19 | Budowa imperium osmańskiego. Zagrożenie tureckie i upadek Konstantynopola | https://zpe.gov.pl/b/PzLsLmFmF | CC BY-SA 3.0 | Contentplus.pl sp. z o.o., Stentor | 192 |
| 20 | Budowa portu Gdynia oraz Centralny Okręg Przemysłowy na tle dokonań gospodarki II Rzeczypospolitej | https://zpe.gov.pl/b/PmucfFJxH | CC BY-SA 3.0 | Krystian Chariza i zespół | 770 |
| 21 | Budowa powojennego ładu. Okupacja aliancka Niemiec i Austrii | https://zpe.gov.pl/b/PIgV7x1xE | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 580 |
| 22 | Cesarstwo Karola Wielkiego. Renesans karoliński | https://zpe.gov.pl/b/P7PmyPhRq | CC BY-SA 3.0 | Contentplus .sp. z o.o. na podstawie Wikimedia Commons | 177 |
| 23 | Chiny po II wojnie światowej | https://zpe.gov.pl/b/PrQCEWYOA | CC BY 3.0; CC BY-SA 3.0 | Addicted04, Wikimedia Commons; Contentplus.pl sp. z o.o.; Diego Delso, Wikimedia Commons; Poco a poco | 185 |
| 24 | Chrzest Chlodwiga i rządy Merowingów | https://zpe.gov.pl/b/PVec8eqUq | CC BY-SA 3.0 | Contentplus sp. z o. o. na podstawie Wikimedia Commons | 1206 |
| 25 | Cud nad Wisłą. Kontrofensywa bolszewicka i Bitwa Warszawska w 1920 r. | https://zpe.gov.pl/b/P1Ejz6FmX | CC BY-SA 3.0 | Contentplus.pl na podstawie Halibutt, Wikimedia Commons | 1458 |
| 26 | Cywilizacja przemysłowa. Zmiany w transporcie i komunikacji | https://zpe.gov.pl/b/P12glh8uK | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 86 |
| 27 | Cywilizacje Azji | https://zpe.gov.pl/b/PKLJchiYj | CC BY-SA 3.0 | ContentPlus.sp. z o.o. na podstawie Historia 2. Ze Świata do Polski przez Europę. Część 1. Podręcznik dla liceum ogólnokształcącego, liceum profilowanego i technikum. Klasa 2. Część Wójcik Marek | 241 |
| 28 | Czas królestw – Europa XIV–XV w. | https://zpe.gov.pl/b/PN1sL00r | CC BY 3.0; CC BY-SA 3.0 | Andreas Praefcke; Bigdaddy1204; Contentplus sp. z o.o.; Contentplus.pl sp. z o.o.; a. nn. | 404 |
| 29 | Czechy pod rządami Luksemburgów | https://zpe.gov.pl/b/PznTWP2oz | CC BY-SA 3.0 | Contentplus.pl | 632 |
| 30 | Czy I Rzeczpospolita musiała upaść? – wypracowanie | https://zpe.gov.pl/b/P2g9lAfpA | CC BY-SA 3.0 | Krystian Chariza i zespół | 103 |
| 31 | Czynniki integrujące Polaków pod zaborami | https://zpe.gov.pl/b/P17hE5af5 | CC BY 4.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Mach240390, Wikimedia Commons | 133 |
| 32 | Dalsze podboje – basen Morza Śródziemnego | https://zpe.gov.pl/b/PwiVaRaiC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. na podstawie ColdEel, Wikimedia Commons | 1222 |
| 33 | Decyzje kongresu w sprawie polskiej | https://zpe.gov.pl/b/Pbv0Affow | CC BY-SA 3.0 | Contentplus.sp. z o.o.; Contentplus.sp. z o.o. na podstawie Maciej Szczepańczyk, Wikimedia Commons Teksty: Akt końcowy Kongresu Wiedeńskiego z 9 czerwca 1815 r. , Z. Fras, Galicja , Wrocław 1999, s. 88-89; Contentplus.sp. z o.o. na podstawie wlaczpolske.pl | 136 |
| 34 | Dekolonizacja Afryki. Polityka apartheidu | https://zpe.gov.pl/b/PidzRUyTr | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 453 |
| 35 | Do trzech razy sztuka? Powstania śląskie 1919–1921 i podział Górnego Śląska | https://zpe.gov.pl/b/P8yrQkUlm | CC BY-SA 3.0 | Contentplus.pl | 75 |
| 36 | Droga do wojny – Japonia, Włochy i Niemcy | https://zpe.gov.pl/b/PnhZ8pPfy | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1705 |
| 37 | Dwa oblicza pryncypatu. Panowanie Flawiuszów i Antoninów | https://zpe.gov.pl/b/P6nyqM70J | CC BY-SA 3.0 | ContentPlus.sp.z o.o.; Ilustracje lic. edukacyjna, Wikimedia Commons | 279 |
| 38 | Dwa państwa niemieckie | https://zpe.gov.pl/b/PTJsSlymm | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 72 |
| 39 | Dwie okupacje | https://zpe.gov.pl/b/PJkRlAc9Y | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Wilhelm Holtfreter , Bundesarchiv; a. nn.; a. nn., Bundesarchiv | 305 |
| 40 | Dynastia julijsko‑klaudyjska. Od komedii republiki po rządy terroru | https://zpe.gov.pl/b/PS3lt1MP6 | CC BY-SA 3.0 | ContentPlus .sp.z o.o. na podstawie imperiumromanum.edu.pl | 526 |
| 41 | Działania wojenne na pozostałych frontach w latach 1915–1916 | https://zpe.gov.pl/b/P1FpQwiFh | CC BY-SA 3.0 | Contentplus.pl | 419 |
| 42 | Dziedzictwo antyku i renesans w średniowieczu | https://zpe.gov.pl/b/P16CVMfy5 | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; dostępny w internecie: wikipedia.org | 364 |
| 43 | Dziedzictwo kultury greckiej i rzymskiej w dorobku kulturowym Europy – podsumowanie | https://zpe.gov.pl/b/PBIwrg42n | CC BY-SA 2.0; CC BY-SA 3.0 | Adrian Grycuk, Wikimedia Commons; Carole Raddato, Muzea Watykańskie | 89 |
| 44 | Edukacja i nauka na ziemiach polskich w XVI‑XVIII wieku | https://zpe.gov.pl/b/P1D7kBkcr | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 74 |
| 45 | Egipt i Mezopotamia | https://zpe.gov.pl/b/PBNPslVxL | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. na podstawie Bosyantek, Wikimedia Commons | 762 |
| 46 | Ekspansja III Rzeszy | https://zpe.gov.pl/b/P19vGokeN | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 161 |
| 47 | Ekspansja Japonii w Azji i jej agresja na Chiny | https://zpe.gov.pl/b/PjovEkwyI | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 723 |
| 48 | Ekspansja kolonialna mocarstw | https://zpe.gov.pl/b/PhINjhdSW | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 365 |
| 49 | Ekspansja turecka w XVI w. | https://zpe.gov.pl/b/PjbIGhXJB | CC BY-SA 3.0 | Contentplus.pl | 179 |
| 50 | Eksterminacja ludności żydowskiej przez Niemcy na okupowanych ziemiach polskich podczas II wojny światowej | https://zpe.gov.pl/b/P14CZZ8XL | CC BY 2.5; CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Cezary Piwowarski; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Mariusz Kubik; Michał Józefaciuk; Pimke; Spacejam2; a. nn., Bundesarchiv; a. nn., Bundesarchiv, Bild 183-N0827-318 | 433 |
| 51 | Emigracja popowstaniowa i zsyłki w głąb Rosji | https://zpe.gov.pl/b/PmxGxfACn | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.pl sp. z o.o.; Jirew, Wikimedia Commons | 1051 |
| 52 | Europa Karola Wielkiego | https://zpe.gov.pl/b/PGWsvtD1n | CC BY 3.0; CC BY-SA 3.0 | Aliesin; Berthold Werner , Wikimedia Commons; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 304 |
| 53 | Europa po Wielkiej Wojnie | https://zpe.gov.pl/b/PcbQspZQj | CC BY-SA 2.5; CC BY-SA 3.0 | Classical Numismatic Group , Wikimedia Commons; Contentplus.pl sp. z o.o. na podstawie Magyarorszag_1920; Contentplus.pl sp. z o.o. na podstawie Stentor; Krystian Chariza i zespół | 208 |
| 54 | Europa po Wiośnie Ludów | https://zpe.gov.pl/b/PVGK6RN7u | CC BY-SA 3.0 | Contentplus.pl | 281 |
| 55 | Europa pod koniec XIX w. Przemiany ustrojowe i układ sił | https://zpe.gov.pl/b/P3sAXCFY9 | CC BY-SA 3.0 | Joseph Kürschner , Wikimedia Commons; Joseph Kürschner, Wikimedia Commons | 136 |
| 56 | Europa w cieniu Francji. Wojny Ludwika XIV | https://zpe.gov.pl/b/P11ho3t4F | CC BY 4.0; CC BY-SA 3.0 | Englishsquare.pl sp. z o.o.; Wikimedia Commons, Wellcome Trust , R. de Hooghe | 659 |
| 57 | Europa Środkowa od XIII do początków XV wieku. Czasy ekspansji wielkich dynastii i łączenia królestw | https://zpe.gov.pl/b/PCAiyXlkU | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. | 643 |
| 58 | Europejczycy w Afryce, Chinach i Indiach. Kontakty nie tylko gospodarcze od XV do XIX w. | https://zpe.gov.pl/b/PZODoSBen | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 976 |
| 59 | Finis belle époque. Zamach w Sarajewie i wybuch I wojny światowej | https://zpe.gov.pl/b/Ptx54IXGe | CC BY-SA 3.0 | Contenplus sp. z o. o. | 343 |
| 60 | Geneza II wojny światowej | https://zpe.gov.pl/b/PQSO57QVl | CC BY 3.0 | Contentplus.pl sp. z o.o. | 71 |
| 61 | Geneza konfliktu Anglii i Francji. Kapetyngowie i Plantageneci | https://zpe.gov.pl/b/PfGvRxzVC | CC BY-SA 3.0 | Contentplus .pl | 74 |
| 62 | Gospodarka Rzeczpospolitej w XVI i XVII wieku | https://zpe.gov.pl/b/P6TqS5ZTI | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 75 |
| 63 | Granica z Niemcami i Czechami. Powstanie wielkopolskie i powstania śląskie | https://zpe.gov.pl/b/PDcbhrWvM | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 121 |
| 64 | Grecja po wojnie peloponeskiej: walka o hegemonię | https://zpe.gov.pl/b/P18DOCqMs | CC BY-SA 3.0 | Contentplus.pl na podstawie wikipedia.org; Marcus Cyron, Wikimedia Commons; Nefasdicere, Wikimedia Commons | 146 |
| 65 | Grecki geniusz. Podział dziejów kultury greckiej | https://zpe.gov.pl/b/P15Fo1nH6 | CC BY-SA 3.0 | A. Savin; Berthold Werner; Harrieta171 | 2556 |
| 66 | Handel i pieniądz w Rzeczypospolitej | https://zpe.gov.pl/b/P184m7Jz1 | CC BY-SA 3.0 | Contentplus.pl | 83 |
| 67 | Hetyci i Fenicjanie | https://zpe.gov.pl/b/P1ikcWtRd | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 496 |
| 68 | Hiszpania rozdarta. Wojna domowa 1936 - 1939 | https://zpe.gov.pl/b/P16RxFFkW | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 240 |
| 69 | II rozbiór Polski | https://zpe.gov.pl/b/PkQYC4Kpa | CC BY-SA 3.0 | — | 633 |
| 70 | III Rzeczpospolita. Dziedzictwo PRL | https://zpe.gov.pl/b/PoWvhWMyq | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Stentor | 1220 |
| 71 | Ideał i rzeczywistość trzech stanów | https://zpe.gov.pl/b/P11KFzEBQ | CC BY 3.0; CC BY 4.0 | Contentplus.pl sp. z o.o.; Learnetic SA; rycina | 749 |
| 72 | Imperia bliskowschodnie i ich wierzenia: Egipt, Babilon, Asyria, Medowie i Persja. Żydzi | https://zpe.gov.pl/b/P14KUYXGp | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1028 |
| 73 | Imperium Aleksandra Wielkiego | https://zpe.gov.pl/b/Pl9886Xjk | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 1297 |
| 74 | Insurekcja kościuszkowska i III rozbiór Polski | https://zpe.gov.pl/b/PEe6U0Fc8 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 154 |
| 75 | Integracja europejska. Polska w strukturach NATO i UE | https://zpe.gov.pl/b/PMOP7bAIw | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Mateusz War | 148 |
| 76 | Integracja na świecie | https://zpe.gov.pl/b/PUhIq4tV0 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Lateiner | 934 |
| 77 | Inwestycje II Rzeczypospolitej. Budowa Gdyni i COP‑u | https://zpe.gov.pl/b/PAgonuAzu | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Mix321, Wikimedia Commons | 122 |
| 78 | Italia i Etruskowie | https://zpe.gov.pl/b/PBPfFQXTX | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 581 |
| 79 | Italia podczas powstania Spartakusa | https://zpe.gov.pl/b/PM3XidZK6 | CC BY-SA 3.0 | Contentplus .pl na podstawie mikotoendo.tumblr.com | 744 |
| 80 | Jadwiga Andegaweńska na polskim tronie | https://zpe.gov.pl/b/PVHLUDGtE | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0 | Cezary Piwowarski, Wikimedia Commons; Contentplus.pl sp. z o.o.; Poznaniak, Wikimedia Commons | 86 |
| 81 | Jak powstały Stany Zjednoczone Ameryki? | https://zpe.gov.pl/b/PVfNQzzg0 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 2266 |
| 82 | Jak się żyło w PRL | https://zpe.gov.pl/b/PheoZinPj | CC BY-SA 3.0 | Mirosław Makowski | 72 |
| 83 | Jaka jesień średniowiecza? (podsumowanie) | https://zpe.gov.pl/b/P1HmsRQbU | CC BY 3.0 | Contentplus.pl sp. z o.o. | 104 |
| 84 | Japonia mocarstwem kolonialnym. Wojna rosyjsko‑japońska | https://zpe.gov.pl/b/PHYt3oPnf | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Stentor; Contentplus.sp. z o.o. na podstawie Tosaka, Wikimedia Commons | 144 |
| 85 | Jesień Ludów i upadek komunizmu w krajach Europy Środkowo‑Wschodniej | https://zpe.gov.pl/b/PQ8wDf3vD | CC BY-SA 3.0 | Contentplus.pl | 1449 |
| 86 | Jesień Narodów | https://zpe.gov.pl/b/PzHjcrbZ1 | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Denoel Paris; Ondřej Sláma; Robert Roeske; a. nn. | 176 |
| 87 | Kamienie przeciw czołgom. Powstanie berlińskie (1953) | https://zpe.gov.pl/b/PlEnbqpNS | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie plakatu „Powstanie ludowe 17 czerwca 1953", Federalne Centrum Służby Krajowej; Fundacja Dom Historii; EB no. 1993/10/1667; dostepny na hdg.de | 503 |
| 88 | Kampania polska | https://zpe.gov.pl/b/PNbvKZTQl | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; GregorioW; a. nn. | 353 |
| 89 | Kazimierz Odnowiciel i jego panowanie | https://zpe.gov.pl/b/PsRwVBsiE | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Contentplus.pl | 288 |
| 90 | Kiedy Legiony stały się zbędne | https://zpe.gov.pl/b/PU7w91wLY | CC BY-SA 3.0 | Contentplus sp. z o. o. na podstawie S. Grodziski, E. Kozłowski, Polska zniewolona 1795-1806. Dzieje Narodu i Państwa Polskiego, T. III, Warszawa 1987, s. 62 | 330 |
| 91 | Kolonie brytyjskie (Półwysep Indyjski, Afryka Południowa) | https://zpe.gov.pl/b/PKoRwt5tS | CC BY-SA 3.0 | Contentplus.pl | 1035 |
| 92 | Kolonie francuskie (Półwysep Indochiński, kraje Maghrebu) | https://zpe.gov.pl/b/P1D5mYJHw | CC BY 3.0 | ContentPlus na podstawie WikimediaCommons | 275 |
| 93 | Kolonie w Ameryce Południowej i Północnej | https://zpe.gov.pl/b/P19Ztk8yo | CC BY-SA 3.0 | Contenplus sp. z o. o. | 97 |
| 94 | Kolonie w Ameryce Północnej. Konflikt między osadnikami a metropolią, powstanie Stanów Zjednoczonych | https://zpe.gov.pl/b/PsNWYR8Ms | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o. | 116 |
| 95 | Koncepcje granicy wschodniej | https://zpe.gov.pl/b/PEspcuLu8 | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Wikimedia Commons | 707 |
| 96 | Konferencja paryska i traktat wersalski | https://zpe.gov.pl/b/P16IjKlVj | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 251 |
| 97 | Konflikt indyjsko‑pakistański | https://zpe.gov.pl/b/Pbe56HovH | CC BY-SA 4.0 | Contentplus.pl sp. z o.o. na podstawie Hyderabad in India, Wikimedia Commons | 145 |
| 98 | Konflikt z Turcją. Elekcja Jana III Sobieskiego | https://zpe.gov.pl/b/PIK1HKEyg | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.sp. z o.o. na podstawie Wikimedia Commons; Grzegorz Gołębiowski | 92 |
| 99 | Konflikty bliskowschodnie | https://zpe.gov.pl/b/PhwsT51yg | CC BY 2.5; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; High Contrast; Krystian Chariza i zespół; Moshe Pridan; a. nn. | 232 |
| 100 | Kongres wiedeński: uczestnicy i zasady | https://zpe.gov.pl/b/PQhhTNAH9 | CC BY-SA 3.0 | Contentplus.pl | 921 |
| 101 | Koniec I wojny światowej | https://zpe.gov.pl/b/P1FE8HgWS | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 2219 |
| 102 | Koniec „najdłuższej wojny nowoczesnej Europy”. Powstanie wielkopolskie 1918–1919 | https://zpe.gov.pl/b/PDRbh6bnC | CC BY-SA 3.0 | Bartek Wawraszko (fotografia), Contentplus.pl Sp. z o. o. | 1082 |
| 103 | Konstantynopol. Nowy Rzym | https://zpe.gov.pl/b/P1E4poOJ7 | CC BY-SA 3.0 | Contentplus .sp. z o.o. Ilustracja z Wikimedia Commons , domena publiczna. Cytaty w punktach 1-6 pochodzą z Odahl Ch., Konstantyn i chrześcijańskie cesarstwo, rozdz: „Troski cesarza i chrześcijański Konstantynopol” , Oświęcim 2015. Cytat w pkt 7: Konstantynopol. Nowy Rzym, red. nauk. Leszka | 674 |
| 104 | Kontrreformacja w Polsce | https://zpe.gov.pl/b/PqoQ2FA9 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Mathiasrex, Wikimedia Commons; Contentplus.pl sp. z o.o. na podstawie wlaczpolske.pl | 146 |
| 105 | Kościół we wczesnym średniowieczu | https://zpe.gov.pl/b/PejwnzCI6 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Wielka historia świata , t. 4, Kształtowanie średniowiecza , A. Bieniek, K. Kościelniak, M. Salamon, K. Stopka, A. Waśko, Kraków 2005 s. 38 | 69 |
| 106 | Kraje demokracji ludowej | https://zpe.gov.pl/b/P1B8Z3hFf | CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.pl sp. z o.o.; Fenn-O-maniC; Marxists Internet Archive, 1942; a. nn. | 218 |
| 107 | Kryzys i upadek cesarstwa rzymskiego | https://zpe.gov.pl/b/P7tYvJ9ko | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0 | G.dallorto , Wikimedia Commons; Krystian Chariza i zespół; Luis García, Wikimedia Commons; Lure, Wikimedia Commons; Rosa Cabecinhas & Alcino Cunha (Rosino) | 713 |
| 108 | Kryzys i upadek republiki | https://zpe.gov.pl/b/P14bes5b1 | CC BY-SA 2.0; CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Wikimedia Commons; Lasha Tskhondia, Wikimedia Commons; Wikimedia Commons | 90 |
| 109 | Kryzys kubański | https://zpe.gov.pl/b/PmQzK7GFS | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1485 |
| 110 | Kryzys republiki rzymskiej. Reformy Grakchów i kariera Gajusza Mariusza | https://zpe.gov.pl/b/PLNFikl2A | CC BY-SA 3.0 | Contentplus.pl na podstawie wikipedia.org autor: Antoine Glédel, domena publiczna | 957 |
| 111 | Kryzys wewnętrzny cesarstwa i jego podział | https://zpe.gov.pl/b/PSWzijjq8 | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 230 |
| 112 | Kryzysy społeczno‑polityczne w PRL | https://zpe.gov.pl/b/PjCjy261B | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Radomil; Witold Pietrusiewicz; a. nn. | 281 |
| 113 | Królestwa Wschodnich i Zachodnich Franków | https://zpe.gov.pl/b/PNjkmU5C9 | CC BY 3.0; CC BY 4.0; CC BY-SA 3.0 | Biblioteka Narodowa w Paryżu; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Learnetic SA | 986 |
| 114 | Księstwo Warszawskie – małe państwo wielkich nadziei | https://zpe.gov.pl/b/Pc8oZA38k | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1588 |
| 115 | Kształtowanie się granicy z Niemcami i Czechosłowacją | https://zpe.gov.pl/b/P12nwUCBF | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 181 |
| 116 | Ku ostatecznemu rozstrzygnięciu. Cele wojenne Stalina i Hitlera | https://zpe.gov.pl/b/PuHyQZ1mb | CC BY-SA 3.0 | Wikimedia Commons | 338 |
| 117 | Kultura i religia Bizancjum. Między Wschodem a Zachodem | https://zpe.gov.pl/b/PAsn6B5fW | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0; CC0 | Antonio Nardelli; Contentplus sp. z o.o.; Contentplus.pl sp. z o.o.; Daderot, Cincinnati Art Museum; HOWI; a. nn. | 963 |
| 118 | Kultura rycerska i motyw rycerza | https://zpe.gov.pl/b/PZeKlZI1H | CC BY 4.0 | LEARNETIC SA | 91 |
| 119 | Legiony Polskie. Wojska polskie u boku ententy | https://zpe.gov.pl/b/P18M58VgZ | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Muzeum Narodowe w Krakowie | 150 |
| 120 | Liga Narodów – geneza i cele powołania | https://zpe.gov.pl/b/P199T5Xr7 | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 224 |
| 121 | Lądowanie we Włoszech i w Normandii. Upadek III Rzeszy | https://zpe.gov.pl/b/PiMuQ4XWf | CC BY-SA 3.0 | Contentplus .sp. z o.o. na podstawie Lonio17; Contentplus .sp. z o.o. na podstawie Lonio17, Wikimedia Commons; Contentplus .sp. z o.o. na podstawie Wikimedia Commons | 399 |
| 122 | Macedonia Filipa II. Podboje Aleksandra Macedońskiego | https://zpe.gov.pl/b/PboEz46zn | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.pl, Stentor | 298 |
| 123 | Mahomet i powstanie islamu | https://zpe.gov.pl/b/P4lIINuLn | CC BY-SA 3.0; CC BY-SA 4.0 | Arkadiusz Kucharski "Arski", Wikimedia Commons; Contentplus .pl sp. z o.o.; Jerzy Strzelecki, Wikimedia Commons; Krystian Chariza i zespół; Krystian Chariza i zespół. Contentplus .pl sp. z o.o.; MaKa, Wikimedia Commons; PereslavlFoto, Wikimedia Commons | 447 |
| 124 | Mezopotamia – kraina między Eufratem a Tygrysem | https://zpe.gov.pl/b/PMlLGVZzD | CC BY 2.0; CC BY 3.0; CC BY 4.0; CC BY-SA 2.0; CC BY-SA 3.0 | Carole Raddato, Flickr; Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o., Dariusz Bufnal; Dûrzan Cîrano, Wikimedia Commons; Learnetic S.A.; Learnetic SA; LeastCommonAncestor, Wikimedia Commons; Musée du Louvre; Ośrodek Rozwoju Edukacji; Rictor Norton, David Allen, Wikimedia Commons | 562 |
| 125 | Mieszkańcy II Rzeczypospolitej: struktura społeczna i narodowości | https://zpe.gov.pl/b/PC7n1e3iM | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o. na podstawie Mathiasrex, Wikimedia Commons; Krystian Chariza i zespół | 435 |
| 126 | Mieszko II. Kryzys monarchii wczesnopiastowskiej | https://zpe.gov.pl/b/P13ynwkLF | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Contentplus .sp. z o.o., Stentor | 287 |
| 127 | Misja: pokój na świecie. Powstanie i struktura ONZ | https://zpe.gov.pl/b/P19kuzZoV | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie wikipedia.org | 356 |
| 128 | Mniejszości narodowe II RP i konflikty na tle narodowościowym | https://zpe.gov.pl/b/PoypL4fA9 | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 96 |
| 129 | Monarchia Bolesława Śmiałego | https://zpe.gov.pl/b/PLK2BAS5F | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 887 |
| 130 | Mongołowie i ich podboje. Podbój Rusi | https://zpe.gov.pl/b/PgGRkBp9T | CC BY-SA 3.0 | Contentplus .pl | 187 |
| 131 | NATO i Układ Warszawski | https://zpe.gov.pl/b/PR7BU1xZt | CC BY-SA 3.0 | Contentplus.pl sp. z o.o., Stentor; Contentplus.sp. z o.o., Stentor; Krystian Chariza i zespół | 501 |
| 132 | NEP. Leninowski krok wstecz | https://zpe.gov.pl/b/P8XjZf6MC | CC BY-SA 3.0 | Contenplus.pl | 538 |
| 133 | Na drodze do zjednoczenia. Kształtowanie się pierwszych ośrodków władzy u progu odzyskania przez Polskę niepodległości | https://zpe.gov.pl/b/Pmafwwbmn | CC BY-SA 3.0 | Contentplus.pl | 833 |
| 134 | Na drodze ku stabilizacji. Sejm Ustawodawczy 1919–1922 i uchwalenie małej konstytucji | https://zpe.gov.pl/b/PxUgaaPzs | CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl, na podstawie danych z: Piotr A. Tusiński, Sejm Ustawodawczy Rzeczypospolitej Polskiej 1919-1922 , Warszawa 2019 | 1638 |
| 135 | Na lądach, pustyniach i oceanach. II wojna światowa w Afryce, na Atlantyku i na Dalekim Wschodzie | https://zpe.gov.pl/b/PHhi5q9ut | CC BY-SA 3.0 | Contentplus.pl | 277 |
| 136 | Nad limes. Wojny w okresie pryncypatu | https://zpe.gov.pl/b/PR5aQigG6 | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 1217 |
| 137 | Nadzieje i rozczarowania. Społeczne skutki rewolucji przemysłowej | https://zpe.gov.pl/b/P187YRpsU | CC BY 4.0 | Wikimedia Commons | 544 |
| 138 | Napoleona Bonapartego droga do władzy | https://zpe.gov.pl/b/PsQ8MrvFJ | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Wikimedia Commons; Contentplus.pl sp. z o.o., Stentor | 197 |
| 139 | Narodziny mocarstwa. USA w II połowie XIX wieku | https://zpe.gov.pl/b/PuvTUKnAa | CC BY 3.0 | Krystian Chariza i zespół. | 245 |
| 140 | Natura i ludzie. Ramy życia społecznego w średniowieczu | https://zpe.gov.pl/b/Pv5wID8PY | CC BY 3.0 | Contentplus.pl sp. z o.o.; Contetplus.pl sp. z o.o.; a. nn. | 99 |
| 141 | Niepokoje średniowiecza | https://zpe.gov.pl/b/PInD8HMec | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplusp.sp. z o.o. na podstawie MesserWoland, Petr Dlouhý, Wikimedia Commons | 417 |
| 142 | Niewola i powstanie. Przyczyny wojen perskich | https://zpe.gov.pl/b/PF50aXvod | CC BY-SA 3.0 | Contentplus .pl | 192 |
| 143 | Niewypowiedziana wojna. Początek walk polsko‑bolszewickich i wyprawa kijowska w latach 1919–1920 | https://zpe.gov.pl/b/PZDHYYbI5 | CC BY-SA 3.0 | ContentPlus.sp.z o.o. | 119 |
| 144 | Nowela sierpniowa i Konstytucja kwietniowa | https://zpe.gov.pl/b/PTDEGc7rn | CC BY 3.0; CC BY-SA 2.5 | Contentplus.pl sp. z o.o.; Narodowe Archiwum Cyfrowe | 92 |
| 145 | Nowy rozdział. Rządy dyrektoriatu | https://zpe.gov.pl/b/PlLIn9U6I | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1261 |
| 146 | Ocena polityki wewnętrznej i zagranicznej Justyniana I | https://zpe.gov.pl/b/P6WsYl9F | CC BY-SA 2.5; CC BY-SA 3.0 | Neuceu, Wikimedia Commons; Osvaldo Gago, Wikimedia Commons | 101 |
| 147 | Od Mieszka II do Bolesława Krzywoustego - podsumowanie | https://zpe.gov.pl/b/PvcOkDdS6 | CC BY-SA 3.0 | Contentplus .sp. z o.o.; Contentplus .sp. z o.o. na podstawie Poznaniak, Wikimedia Commons | 70 |
| 148 | Od Polski drewnianej do murowanej – rządy Kazimierza Wielkiego | https://zpe.gov.pl/b/Pn1yRO5Me | CC BY 3.0; CC BY 4.0; CC BY-SA 3.0; CC BY-SA 4.0 | Krystian Chariza i zespół; Learnetic S.A.; Ludan, Wikimedia Commons; Tomasz Czapla; Ufoizba, Wikimedia Commons; mzopw | 197 |
| 149 | Od Prus Zakonnych do Książęcych | https://zpe.gov.pl/b/P1GD7LJzA | CC BY-SA 3.0 | Contentplus.pl; Krystian Chariza i zespół, Contentplus.pl | 224 |
| 150 | Odnowione cesarstwo Ottonów | https://zpe.gov.pl/b/PQ4ORX8Lx | CC BY 3.0; CC BY 4.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Learnetic S.A.; Learnetic SA | 1144 |
| 151 | Ofensywa niemiecka i upadek Francji | https://zpe.gov.pl/b/P3eThLjt2 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 488 |
| 152 | Ogniem i mieczem. Powstania kozackie | https://zpe.gov.pl/b/PkTX3viXY | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Krystian Chariza i zespół; Lonio17, Wikimedia Commons; Wikimedia Commons , Hoodinski; Wikimedia Commons , Lonio17; Wikimedia Commons , MaKa; Wikimedia Commons , Maciej Szczepańczyk; Wikimedia Commons , a. nn.; a. nn. | 577 |
| 153 | Okres stalinizmu w Polsce | https://zpe.gov.pl/b/PA5ulCKtU | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0 | Ariadna Rokossowska; Contentplus.pl sp. z o.o.; Jan Mehlich; Poznaniak1975 | 223 |
| 154 | Okupacja Niemiec i Austrii. Powstanie dwóch państw niemieckich | https://zpe.gov.pl/b/P17qu7Jw1 | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie xyboi, based on work Nordelch, SebastianWilken and morwen, Wikimedia Commons; Helmut J. Wolf; Jörg Zägel, Wikimedia Commons; Wikimedia Commons | 103 |
| 155 | Okupacja niemiecka w Polsce | https://zpe.gov.pl/b/P1FrZMZ0q | CC BY 2.0; CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Lonio17, Wikimedia Commons; Jochen Zimmermann, Wikimedia Commons | 201 |
| 156 | Organizacja państwa Mieszka I | https://zpe.gov.pl/b/PXLPInFB7 | CC BY-SA 3.0 | Contentplus .pl za Gazeta Wyborcza | 289 |
| 157 | Organizacja państwa za Kazimierza Wielkiego. Monarchia stanowa | https://zpe.gov.pl/b/PaLcfho1C | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 608 |
| 158 | Osiągnięcia cywilizacji islamu. Kultura arabska | https://zpe.gov.pl/b/P17Pepawo | CC BY-SA 3.0 | Contentplus.pl; Wikimedia Commons | 378 |
| 159 | Osiągnięcia kulturalne i naukowe w dwudziestoleciu międzywojennym | https://zpe.gov.pl/b/P1fSlgwaQ | CC BY 3.0; CC BY-SA 2.0; CC BY-SA 4.0 | Contentplus.pl sp. z o.o.; Flickr; Mariusz Paździora, fotografia; a. nn.; fotografia, Bundesarchiv | 193 |
| 160 | Osiągnięcia starożytnych Rzymian | https://zpe.gov.pl/b/P8u3Ry8gZ | CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Benh LIEU SONG; Contentplus.pl sp. z o.o.; Matthias Kabel; Petar Milošević; Woeterman 94; a. nn. Ośrodek Rozwoju Edukacji | 184 |
| 161 | Ostatni etap zmagań o wschodnią granicę Polski. Traktat ryski oraz kwestia wileńska w latach 1920–1921 | https://zpe.gov.pl/b/PnviQzSyk | CC BY-SA 3.0 | Contentplus.pl na podstawie Mix321 - wikipedia.pl | 64 |
| 162 | O greckim teatrze, igrzyskach olimpijskich i filozofii | https://zpe.gov.pl/b/Pq467D2zC | CC BY 2.0; CC BY 2.5; CC BY 3.0; CC BY-SA 2.0; CC BY-SA 3.0 | Bernard Gagnon, Wikimedia Commons; Contentplus.pl Sp. z o.o.; Derek Key; Learnetic S.A.; Marie-Lan Nguyen; Rosino; a. nn., Ośrodek Rozwoju Edukacji, | 305 |
| 163 | Palestyna i Żydzi w Imperium Rzymskim | https://zpe.gov.pl/b/PtohnHoFB | CC BY-SA 3.0 | Contentplus .pl | 549 |
| 164 | Paryskie traktaty pokojowe z sojusznikami III Rzeszy | https://zpe.gov.pl/b/PgtM5wf92 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 85 |
| 165 | Paryż w ofensywie. Wprowadzenie monarchii konstytucyjnej | https://zpe.gov.pl/b/Pnh4SQXsl | CC BY-SA 3.0 | Contentplus.sp.z o.o. | 432 |
| 166 | Pax Romana. Rzymska Europa | https://zpe.gov.pl/b/PEmmcLYQp | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 178 |
| 167 | Państwa barbarzyńskie na gruzach cesarstwa zachodniorzymskiego. Koniec starożytności | https://zpe.gov.pl/b/PFiAyhLBD | CC BY-SA 3.0 | Contentplus .pl, Krystian Chariza i zespół | 95 |
| 168 | Państwa średniowieczne – różnorodność etniczna i kulturowa | https://zpe.gov.pl/b/PS1hD0jEB | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Killroyus | 958 |
| 169 | Państwo Hitlera | https://zpe.gov.pl/b/PC2J3b8kt | CC BY 3.0; CC BY-SA 2.0 | Andrzej Otrębski; Bundesarchiv Bild 146-1970-083-42; Bundesarchiv Bild 152-42-31; Bundesarchiv Bild 183-R99035; Carl Weinrother; Contentplus.pl sp. z o.o.; Robert Sennecke , Bundesarchiv , Bild 146-1972-026-11; Stefan Wagner; Theo Eisenhart; a. nn. | 658 |
| 170 | Państwo Karolingów | https://zpe.gov.pl/b/PVRU5x9Pw | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 144 |
| 171 | Państwo krzyżackie. Krzyżacy i Litwa | https://zpe.gov.pl/b/PcCHfZJKY | CC BY-SA 3.0 | Contentplus.pl | 4425 |
| 172 | Persowie | https://zpe.gov.pl/b/Pd078pO5r | CC BY-SA 3.0 | Contentplus.pl | 1075 |
| 173 | Pierwsze państwa plemienne na ziemiach polskich | https://zpe.gov.pl/b/Pp8EOsx2v | CC BY-SA 3.0 | Contentplus .pl | 115 |
| 174 | Pistolet i gałązka oliwna. Jasir Arafat i Organizacja Wyzwolenia Palestyny | https://zpe.gov.pl/b/PquPvMix6 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. | 886 |
| 175 | Plan „Burza” | https://zpe.gov.pl/b/PyPaZnAt7 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 152 |
| 176 | Początki Polskiej Rzeczypospolitej Ludowej. Polska Lubelska | https://zpe.gov.pl/b/P5skFtOek | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 572 |
| 177 | Początki faszyzmu w Niemczech i we Włoszech | https://zpe.gov.pl/b/PVSlGcQ0k | CC BY 3.0; CC BY-SA 3.0 | Bundesarchiv, Bild 183-2007-1022-506; Contentplus.pl sp. z o.o.; a. nn. | 175 |
| 178 | Początki integracji europejskiej | https://zpe.gov.pl/b/PtfPKT4UI | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 362 |
| 179 | Początki najstarszych cywilizacji | https://zpe.gov.pl/b/PodHYPuPk | CC BY-SA 3.0 | Contentplus.pl | 979 |
| 180 | Początki parlamentaryzmu | https://zpe.gov.pl/b/PTx8S6dmu | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 519 |
| 181 | Początki rządów Bolesława Chrobrego. Dzieje jednej przyjaźni | https://zpe.gov.pl/b/P1CVSgrqQ | CC BY-SA 2.5 | Tomasz Fedor, Wikimedia Commons | 86 |
| 182 | Początki starożytnej Grecji. Cywilizacja minojska i mykeńska | https://zpe.gov.pl/b/PwMgt9ka | CC BY-SA 3.0 | Contentplus.pl | 1234 |
| 183 | Podboje Rzymu. Wojny punickie | https://zpe.gov.pl/b/PhxyOtmZ7 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. na podstawie Abalg, Pinpin, Wikimedia Commons; Contentplus.sp. z o.o. na podstawie Pitert, Wikimedia Commons | 1491 |
| 184 | Podboje arabskie i ich wpływ na cywilizację łacińską i bizantyjską | https://zpe.gov.pl/b/PNf2xq8Hs | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.sp. z o.o. na podstawie Wikimedia Commons; Effems, Wikimedia Commons | 173 |
| 185 | Podbój Ameryki | https://zpe.gov.pl/b/Pp8sCCvJ3 | CC BY-SA 3.0 | Contentplus.pl na podstawie Stentor | 226 |
| 186 | Podbój Europy przez Stalina i Hitlera | https://zpe.gov.pl/b/P8KXY2MvI | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 151 |
| 187 | Podbój Rusi Halickiej i sprawa sukcesji | https://zpe.gov.pl/b/P72bl21zP | CC BY-SA 3.0 | Contentplus .sp. z o.o. na podstawie Krystian Chariza i zespół | 391 |
| 188 | Podbój państw hellenistycznych. Rzymski imperializm i logika jego działania | https://zpe.gov.pl/b/P1EJenNgB | CC BY-SA 3.0 | Contentplus .pl | 775 |
| 189 | Podróż dookoła świata Ferdynanda Magellana. Wyprawy angielskie i francuskie | https://zpe.gov.pl/b/PsXXW5DNp | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1787 |
| 190 | Podział Cesarstwa Rzymskiego – wypracowanie | https://zpe.gov.pl/b/PvxdYEcwc | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Geuiwogbil, Wikimedia Commons; Contentplus.pl sp. z o.o., Stentor | 134 |
| 191 | Podziały polityczne i wyznaniowe Europy w XVI w. | https://zpe.gov.pl/b/P13uNAcZ4 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1910 |
| 192 | Podzielona, zniszczona i zmarginalizowana. Rzeczpospolita w czasie wielkiej wojny północnej | https://zpe.gov.pl/b/PW5mdkSrM | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 591 |
| 193 | Pokój i bezpieczeństwo dla świata | https://zpe.gov.pl/b/PXZfYMj7T | CC BY-SA 3.0 | Contentplus .pl | 410 |
| 194 | Polacy na frontach II wojny światowej | https://zpe.gov.pl/b/PBDuQ2zn2 | CC BY 3.0; CC BY 4.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Learnetic S.A.; Learnetic SA; a. nn. | 212 |
| 195 | Polacy na frontach II wojny światowej – podsumowanie | https://zpe.gov.pl/b/PCSJDzc11 | CC BY-SA 3.0 | Contentplus.pl | 275 |
| 196 | Polacy podczas europejskiej Wiosny Ludów | https://zpe.gov.pl/b/P14LgkC2l | CC BY-SA 3.0 | Contentplus.pl | 125 |
| 197 | Polacy w walce o niepodległość Stanów Zjednoczonych | https://zpe.gov.pl/b/PkukLju5n | CC BY-SA 3.0 | Contentplus.sp. z o.o., Stentor | 324 |
| 198 | Polis. Miasto‑państwo w Grecji i jego organizacja | https://zpe.gov.pl/b/PUYBnMtA | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 457 |
| 199 | Polityka dynastyczna ostatnich Jagiellonów | https://zpe.gov.pl/b/P37AVEhXA | CC BY-SA 3.0 | Contentplus.pl | 135 |
| 200 | Polityka ustępstw państw europejskich wobec państw faszystowskich | https://zpe.gov.pl/b/P1CfjfZuY | CC BY 3.0; CC BY-SA 2.0; CC BY-SA 3.0 | Bundesarchiv Bild 119-5243; Bundesarchiv Bild 146-1972-028-14; Bundesarchiv Bild 183-R69173; Bundesarchiv, Bild 183-H01212; Contentplus.pl sp. z o.o.; Marion Doss; Scherl , Bundesarchiv Bild 137-049278; a. nn. | 379 |
| 201 | Polityka zagraniczna II RP w l. 1922‑1936 | https://zpe.gov.pl/b/PSZbeKxqf | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; a. nn. domena publiczna; a. nn. domena publiczna, Bundesarchiv | 251 |
| 202 | Polityka zagraniczna i armia Ludwika XIV | https://zpe.gov.pl/b/Pb1woABlh | CC BY-SA 3.0 | Contentplus.pl | 102 |
| 203 | Polska i Litwa za panowania Jagiełły | https://zpe.gov.pl/b/P105zQlIr | CC BY-SA 3.0 | Contentplus.pl | 1078 |
| 204 | Polska i świat w okresie II wojny światowej (lekcja powtórzeniowa) | https://zpe.gov.pl/b/Pi6ltU6su | CC BY 3.0 | — | 230 |
| 205 | Polska po śmierci Bolesława Chrobrego | https://zpe.gov.pl/b/P1G4yIJaX | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Gryffindor; Krystian Chariza i zespół; Marcin Polak, Wikimedia Commons | 344 |
| 206 | Polska pod okupacją niemiecką i sowiecką | https://zpe.gov.pl/b/Pj2vSewxC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 945 |
| 207 | Polska wraca na mapy. Traktat wersalski | https://zpe.gov.pl/b/PkuGuzAxP | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 429 |
| 208 | Polska, Europa, świat po I wojnie światowej (lekcja powtórzeniowa) | https://zpe.gov.pl/b/P17xMHkcz | CC BY 3.0; CC BY-SA 3.0 | Bundesarchiv , Bild 183-R01213; Krystian Chariza i zespół | 74 |
| 209 | Polskie państwo podziemne. Komuniści w czasie okupacji. | https://zpe.gov.pl/b/PUVAhuqDH | CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Adrian Grycuk; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Marek Ruszczyc; a. nn.; a. nn., domena publiczna | 262 |
| 210 | Potęga Habsburgów – „imperium, w którym nie zachodzi słońce" | https://zpe.gov.pl/b/PGsAUVB5X | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1068 |
| 211 | Potęga i ekspansja Szwecji. Brandenburgia | https://zpe.gov.pl/b/PUeha80TX | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 107 |
| 212 | Powstanie Chmielnickiego | https://zpe.gov.pl/b/PEqnIpchx | CC BY-SA 3.0 | Contentplus.pl sp. z o.o; Englishsquare .pl sp. z o.o. | 1685 |
| 213 | Powstanie Księstwa Warszawskiego i jego ustrój | https://zpe.gov.pl/b/PrhfsI0aa | CC BY-SA 3.0 | Contentplus.pl | 356 |
| 214 | Powstanie Rzeszy i cesarstwa Ottonów | https://zpe.gov.pl/b/P3zBRNPUq | CC BY-SA 3.0 | Contentplus.sp. z o.o.; Contentplus.sp. z o.o. na podstawie Wikimedia Commons | 333 |
| 215 | Powstanie Solidarności i stan wojenny | https://zpe.gov.pl/b/P9lSQu4gG | CC BY 3.0; CC BY-SA 2.0; CC BY-SA 3.0; CC0 | Ahorcado; Artur Andrzej; Contentplus.pl sp. z o.o.; Tadeusz Kłapyta; a. nn. | 252 |
| 216 | Powstanie listopadowe | https://zpe.gov.pl/b/PkNHjMnNz | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Stentor | 1122 |
| 217 | Powstanie państw w Europie Zachodniej | https://zpe.gov.pl/b/P8z9HbsNA | CC BY-SA 3.0 | Contentplus.pl | 600 |
| 218 | Powstanie styczniowe | https://zpe.gov.pl/b/PPrqk3hAd | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 2323 |
| 219 | Powstanie warszawskie | https://zpe.gov.pl/b/P1ApMNHN8 | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Kalinka261015; Krystian Chariza i zespół; a. nn. | 145 |
| 220 | Powstanie warszawskie | https://zpe.gov.pl/b/P7lebsuSW | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1028 |
| 221 | Powstanie w getcie warszawskim | https://zpe.gov.pl/b/P1FjAZyen | CC BY-SA 3.0 | Contentplus.sp. z o.o. Ilustracje na podstawie Muzeum Historii Żydów Polskich POLIN | 1325 |
| 222 | Powtórka z historii cz. 14: nowożytność | https://zpe.gov.pl/b/PNHP62ZFJ | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Mix321, Straty demograficzne w Rzeszy Niemieckiej w wyniku wojny trzydziestoletniej , Wikipedia Commons | 67 |
| 223 | Położenie międzynarodowe Polski przed wybuchem II wojny światowej | https://zpe.gov.pl/b/P9TImz0Su | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 305 |
| 224 | Prehistoria | https://zpe.gov.pl/b/P1DWVt2Ge | CC BY 3.0; CC BY 4.0; CC BY-SA 2.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o., Sol90; Krystian Chariza i zespół; Learnetic S.A.; Prof saxx; Simon Wakefield; a.nn. | 1173 |
| 225 | Prehistoria i historia | https://zpe.gov.pl/b/Pnh18qync | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.pl sp. z o.o.; Nevit Dilmen, Wikimedia Commons; Wolfgang Sauber | 403 |
| 226 | Proces dekolonizacji | https://zpe.gov.pl/b/PlKRScILy | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; R. Barraez D´Lucca; Ulrich Stelzner; a. nn. | 160 |
| 227 | Przebieg reformacji w innych krajach europejskich | https://zpe.gov.pl/b/Pscpu4GWL | CC BY-SA 3.0 | Contentplus.pl | 131 |
| 228 | Przejęcie władzy przez komunistów w Polsce | https://zpe.gov.pl/b/PPYGdmQCt | CC BY 3.0; CC BY-SA 4.0 | Archiwum Kancelarii Prezydenta RP; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Mateusz Opasiński | 194 |
| 229 | Przekształcenia ustrojowe w Europie Środkowej i Wschodniej na przełomie lat 80. i 90. XX w. | https://zpe.gov.pl/b/PDAIXYtlL | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 2464 |
| 230 | Przemiany gospodarcze epoki stalinowskiej | https://zpe.gov.pl/b/PX6aVF06x | CC BY-SA 3.0 | Contentplus.pl | 307 |
| 231 | Przemiany w Chinach. Korea Północna | https://zpe.gov.pl/b/PhFlILMPq | CC BY 2.0; CC BY 2.5; CC BY-SA 2.5; CC BY-SA 3.0 | Alanmak~commonswiki, Wikimedia Commons; Andreas Habich, Wikimedia Commons; Contentplus.pl sp. z o.o.; Derzsi Elekes Andor, Wikimedia Commons; Markus23~commonswiki, Wikimedia Commons; Michail Kapustin, Wikimedia Commons; Mimura; Shubert Ciencia, Wikimedia Commons; Wikimedia Commons | 441 |
| 232 | Przemiany w rolnictwie i rozwój nauk przyrodniczych w XIX w. | https://zpe.gov.pl/b/PJanCO2ZL | CC BY 2.0; CC BY-SA 3.0; CC BY-SA 4.0 | Adi; Contentplus.pl sp. z o.o. na podstawie wikipedia.org; Hellerhoff, Wikimedia Commons; NASA, Wikimedia Commons; Sandbh, Wikimedia Commons | 155 |
| 233 | Przemiany średniowiecznej religijności – ruchy ubóstwa, zakony | https://zpe.gov.pl/b/Puu6Rnrfr | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 2669 |
| 234 | Przewrót majowy i jego konsekwencje | https://zpe.gov.pl/b/P15ODTXNJ | CC BY 3.0 | Contentplus.pl sp. z o.o.; a. nn. | 159 |
| 235 | Przełomowe bitwy i wydarzenia II wojny - podsumowanie | https://zpe.gov.pl/b/PlFFIJwuH | CC BY-SA 3.0 | Bundesarchiv, Bild, Wikimedia Commons; Contentplus.sp. z o.o. na podstawie Wikimedia Commons | 140 |
| 236 | Przełomowe odkrycia. Jak szukając drogi do Indii, odkryto Amerykę | https://zpe.gov.pl/b/P13sPlVfG | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie K. Mikulski, J. Wijaczka, Historia powszechna. Wiek XVI-XVIII , Wydawnictwo Naukowe PWN, Warszawa 2012, str. 40 | 166 |
| 237 | Przyczyny I wojny światowej. Zamach w Sarajewie i wybuch wojny | https://zpe.gov.pl/b/PbgGrIAL7 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. na podstawie Department of History, United States Military Academy , Wikimedia Commons | 287 |
| 238 | Przystąpienie Polski do Unii Europejskiej | https://zpe.gov.pl/b/PdbIP8bE9 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 330 |
| 239 | Próby zjednoczenia ziem polskich w okresie rozbicia dzielnicowego | https://zpe.gov.pl/b/PWw5OIuhq | CC BY-SA 3.0 | Contentplus .pl | 487 |
| 240 | Referendum ludowe 1946 r. i wybory parlamentarne | https://zpe.gov.pl/b/P172BMZ9s | CC BY-SA 3.0 | ANK | 289 |
| 241 | Reformacja w Niemczech | https://zpe.gov.pl/b/PRuOFwR5t | CC BY-SA 3.0 | Contentplus.pl | 150 |
| 242 | Reformacja w Rzeczypospolitej | https://zpe.gov.pl/b/Pe5E2VpYU | CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o. na podstawie Hoodinski; Loraine, Wikimedia Commons | 277 |
| 243 | Reformacja w innych krajach europejskich. Wyznania protestanckie | https://zpe.gov.pl/b/P12uMHR2n | CC BY-SA 3.0 | Contentplus.pl | 133 |
| 244 | Reformatorzy religijni w Szwajcarii | https://zpe.gov.pl/b/PTdDVk5un | CC BY-SA 3.0 | Henri Bouchard , Paul Landowski, Wikimedia Commons | 320 |
| 245 | Reformy Michaiła Gorbaczowa | https://zpe.gov.pl/b/PVZilWYDs | CC BY 2.0 | The Official CTBTO Photostream - Reagan and Gorbachev Arrive , 1986, Wikimedia Commons | 142 |
| 246 | Rekonkwista na Półwyspie Iberyjskim | https://zpe.gov.pl/b/PJ5XOmQxo | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Jorgenmar, Wikimedia Commons; Roylindman, Wikimedia Commons | 1047 |
| 247 | Religia i polityka. Rewolucja islamska w Iranie i konflikt iracko‑irański | https://zpe.gov.pl/b/PtjCTJO5n | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 665 |
| 248 | Religia, społeczeństwo i gospodarka – przestrzenie zmian w późnośredniowiecznej Europie | https://zpe.gov.pl/b/PeLl17AQb | CC BY 3.0 | Contentplus sp. z o.o.; Contentplus.pl sp. z o.o. | 214 |
| 249 | Renesans w Polsce - związki z reformacją i renesansem europejskim | https://zpe.gov.pl/b/P14648Haq | CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Henryk Bielamowicz, Wikimedia Commons; MaKa, Wikimedia Commons; Radomil, Wikimedia Commons | 107 |
| 250 | Republika rzymska i jej podboje | https://zpe.gov.pl/b/P11kpOJTM | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1320 |
| 251 | Rewolucja w Niderlandach | https://zpe.gov.pl/b/Pa55onOEZ | CC BY-SA 3.0 | Contentplus.pl | 992 |
| 252 | Rewolucje liberalne i powstania narodowe | https://zpe.gov.pl/b/P1HoMeEHB | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1989 |
| 253 | Rewolucje w krajach niemieckich w 1848 r. | https://zpe.gov.pl/b/P176JX6Wp | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 524 |
| 254 | Rokoko i klasycyzm | https://zpe.gov.pl/b/PC5ZfoHuw | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Cancre, Wikimedia Commons; Diego Delso; HeiligerSatyr; Pedelecs, Wikimedia Commons; Rufus46, Wikimedia Commons; Wikimedia Commons; fot. Ludmiła Pilecka, Wikimedia Commons | 66 |
| 255 | Rozbicie dzielnicowe | https://zpe.gov.pl/b/P6Pp78D1B | CC BY-SA 3.0 | Contentplus.pl | 260 |
| 256 | Rozkwit Aten. Wojna peloponeska | https://zpe.gov.pl/b/PlDJRXqgY | CC BY-SA 3.0 | Contentplus .pl na podstawie: Wikimedia Commons; Krystian Chariza i zespół | 225 |
| 257 | Rozpad imperium mongolskiego | https://zpe.gov.pl/b/PH3BXhtus | CC BY-SA 3.0 | Contentplus .pl | 373 |
| 258 | Rozszerzanie Unii Europejskiej na Wschód | https://zpe.gov.pl/b/P11fDNtD6 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1317 |
| 259 | Rozwój gospodarczy Królestwa Polskiego w latach 1821‑1850 | https://zpe.gov.pl/b/PJs23c8ZC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o., Stentor | 246 |
| 260 | Rozwój handlu w Europie w XVI - XVII wieku. Centra gospodarcze kontynentu | https://zpe.gov.pl/b/PP3zAbq47 | CC BY-SA 3.0 | Contentplus.pl | 70 |
| 261 | Rywalizacja Anglii i Hiszpanii w XVI w. | https://zpe.gov.pl/b/P4heqHxT5 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 747 |
| 262 | Rzeczpospolita Obojga Narodów – ludność i terytorium | https://zpe.gov.pl/b/PmKshWnsf | CC BY-SA 3.0 | Contentplus.sp. z o.o. | 343 |
| 263 | Rzeczpospolita i jej sąsiedzi w pierwszej połowie XVIII w. – podsumowanie | https://zpe.gov.pl/b/P1HTxtMd5 | CC BY-SA 3.0; CC BY-SA 4.0 | Adrian Grycuk, Wikimedia Commons; Contentplus.pl sp. z o.o.; Maciej Szczepańczyk, Wikimedia Commons | 187 |
| 264 | Rzym – czas podbojów | https://zpe.gov.pl/b/P170Rja6e | CC BY 3.0; CC BY-SA 2.5 | Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o., Dariusz Bufnal.; Krystian Chariza i zespół. | 601 |
| 265 | Rzym – od założenia miasta do powstania republiki | https://zpe.gov.pl/b/P9R8w70uP | CC BY 3.0 | Contentplus.pl sp. z o.o.; Talmoryair, Wikimedia Commons | 105 |
| 266 | Rzym – początki | https://zpe.gov.pl/b/P1rrhkK0x | CC BY-SA 3.0 | Krystian Chariza i zespół | 154 |
| 267 | Rząd fachowców i pierwsze reformy gospodarcze | https://zpe.gov.pl/b/P1809PWyp | CC BY 3.0 | Contentplus.pl sp. z o.o. | 138 |
| 268 | Rząd polski na uchodźstwie | https://zpe.gov.pl/b/P10VTPXao | CC BY 3.0; CC BY 4.0 | Contentplus.pl sp. z o.o.; Mariusz Kubik | 127 |
| 269 | Rządy Kazimierza Odnowiciela | https://zpe.gov.pl/b/PUV49qPml | CC BY-SA 3.0 | Contentplus .pl | 159 |
| 270 | Rządy sanacji | https://zpe.gov.pl/b/P340wT3Y6 | CC BY 3.0 | Contentplus.pl sp. z o.o. | 64 |
| 271 | Rządy trzech w majestacie prawa. Dzieje II triumwiratu | https://zpe.gov.pl/b/Prvy1ZTdk | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 112 |
| 272 | Salamina i Plateje | https://zpe.gov.pl/b/P19kgInXj | CC BY-SA 3.0; CC BY-SA 4.0 | AnatolyPm, Wikimedia Commons; Gts-tg, Wikimedia Commons; MatthiasKabel, Wikimedia Commons; World Imaging , Wikimedia Commons | 441 |
| 273 | Skazani na klęskę. Przebieg insurekcji kościuszkowskiej | https://zpe.gov.pl/b/P158HHk0V | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. | 434 |
| 274 | Skutki II wojny światowej | https://zpe.gov.pl/b/P1B0XAslV | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn.; a. nn., domena publiczna. | 320 |
| 275 | Skutki I wojny światowej | https://zpe.gov.pl/b/P4vgVQrKv | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 148 |
| 276 | Skutki wojny | https://zpe.gov.pl/b/P10KZbOZg | CC BY-SA 3.0 | Contentplus.sp. z o.o., Wikimedia Commons na podstawie grafiki autorstwa TheShadowed z angielskiej Wikipedii; Flagi: domena publiczna, Wikimedia Commons ; Contentplus.sp. z o.o. | 330 |
| 277 | Socrealizm | https://zpe.gov.pl/b/PJKvwrCK9 | CC0 | online-skills | 199 |
| 278 | Sposoby upamiętnienia zbrodni okupantów niemieckiego i sowieckiego oraz heroizmu Polaków | https://zpe.gov.pl/b/PB2CkMk48 | CC BY 3.0; CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Adrian Grycuk; Adrian Grycuk, Wikimedia Commons; Cezary Piwowarski, Wikimedia Commons; Happa, Wikimedia Commons; Mateusz Opasiński, Wikimedia Commons; Palkin, Wikimedia Commons; PawełMM, Wikimedia Commons; Tomasz Wójcik, Wikimedia Commons; Wikimedia Commons; Zu, Wikimedia Commons; dostępny w internecie: stylove-24.pl; dostępny w internecie: warszawa.naszemiasto.pl | 1016 |
| 279 | Społeczeństwo Polski dzielnicowej | https://zpe.gov.pl/b/P1DjUQrhR | CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus .pl sp. z o.o.; RaNo, Wikimedia Commons | 186 |
| 280 | Społeczeństwo rzymskie | https://zpe.gov.pl/b/P5gezdpk6 | CC BY-SA 3.0 | Contentplus .pl, na podstawie www.imperiumromanum.edu.pl/spoleczenstwo/ | 988 |
| 281 | Sprawa polska na konferencji wersalskiej | https://zpe.gov.pl/b/P1Ai8aUcU | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 81 |
| 282 | Stalinizm w kulturze | https://zpe.gov.pl/b/P18LV4XL5 | CC BY-SA 2.0; CC BY-SA 4.0 | Uwe Brodrecht, Wikimedia Commons; Viktar Palstsiuk, Wikimedia Commons; Wikimedia Commons | 347 |
| 283 | Stany Zjednoczone na przełomie XIX i XX wieku. Udział w ekspansji kolonialnej | https://zpe.gov.pl/b/P5SVVnhk5 | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Krystian Chariza i zespół | 798 |
| 284 | Stany Zjednoczone – rozwój i problemy w latach 1787–1853 | https://zpe.gov.pl/b/PZU4mGPqs | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1909 |
| 285 | Stosunki państw europejskich z Dalekim Wschodem w czasach nowożytnych (do XIX w.) | https://zpe.gov.pl/b/P138Wdnrk | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 197 |
| 286 | Stosunki wewnętrzne w Królestwie Polskim i na Litwie. Unia lubelska | https://zpe.gov.pl/b/PlEDnCoAo | CC BY-SA 3.0 | Grafika: Contenplus.pl | 742 |
| 287 | Strajki sierpniowe | https://zpe.gov.pl/b/P16oIqeO9 | CC BY-SA 3.0 | fot. Krzysztof Korczyński, Wikimedia Commons | 485 |
| 288 | System totalitarny w ZSRS | https://zpe.gov.pl/b/PB2xykDbd | CC BY 3.0; CC BY 4.0; CC BY-SA 3.0 | Aldo Ardetti; Contentplus.pl sp. z o.o.; DIMSFIKAS; Krystian Chariza i zespół; Learnetic SA; Wikimedia Commons | 254 |
| 289 | Sytuacja międzynarodowa Polski przed wybuchem II wojny światowej | https://zpe.gov.pl/b/P13KsnUCK | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 98 |
| 290 | Szlachta Rzeczypospolitej Obojga Narodów: stan podzielony walkami o władzę czy monolit bohatersko strzegący granic ojczyzny? – wypracowanie | https://zpe.gov.pl/b/PUQvIpTvt | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Maciej Szczepańczyk, Wikimedia Commons | 61 |
| 291 | Sztuka i architektura średniowiecza | https://zpe.gov.pl/b/P1AaVTVVz | CC BY-SA 3.0 | Bischöfliche Pressestelle Hildesheim , Wikimedia Commons; Blatand, Wikimedia Commons; Contentplus.pl; Diliff, Wikimedia Commons; Frank Vincentz, Wikimedia Commons; Kolossos, Wikimedia Commons; MichalPL | 741 |
| 292 | Tańczący kongres – nowy ład europejski po wojnach napoleońskich | https://zpe.gov.pl/b/PyhCmUPzZ | CC BY-SA 3.0 | Contentplus.pl | 683 |
| 293 | Terytorium i ludność Rzeczypospolitej Obojga Narodów | https://zpe.gov.pl/b/PhPTIOVno | CC BY-SA 3.0 | Contentplus.pl | 846 |
| 294 | Testament Bolesława Krzywoustego. Przyczyny rozbicia dzielnicowego | https://zpe.gov.pl/b/PY656b83C | CC BY-SA 3.0 | Contentplus .pl sp. z o.o., Stentor; Contentplus.pl | 629 |
| 295 | Transformacja gospodarcza i ustrojowa. Początki III RP | https://zpe.gov.pl/b/POw9TTmma | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Mariusz Kubik | 145 |
| 296 | Tron dziedziczny czy elekcyjny – co byłoby większym gwarantem ciągłości RP w czasach XVII‑wiecznego kryzysu? – wypracowanie | https://zpe.gov.pl/b/PJtNX3AtM | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie M.O; wikipedia.org | 149 |
| 297 | Trudne dziedzictwo. Polityka zagraniczna Kazimierza Wielkiego | https://zpe.gov.pl/b/PctzCWZE3 | CC BY-SA 3.0 | Contentplus .pl; Contentplus .pl sp. z o.o. | 230 |
| 298 | Trudny rok 1938 | https://zpe.gov.pl/b/PfvBp4oVK | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 4909 |
| 299 | Trzeci Świat w świecie dwubiegunowym | https://zpe.gov.pl/b/PhGbBcxKt | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 475 |
| 300 | Turcja po I wojnie światowej | https://zpe.gov.pl/b/P1E6a3Wwx | CC BY-SA 3.0 | Contentplus.sp. z o.o. | 118 |
| 301 | Twarde warunki. Traktat wersalski i traktaty z sojusznikami Niemiec | https://zpe.gov.pl/b/PQ44tTDl9 | CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o. | 643 |
| 302 | Tęsknota za siłą. Zjednoczenie Niemiec | https://zpe.gov.pl/b/PmV0KKpRx | CC BY 3.0; CC BY 4.0 | Contentplus.pl sp. z o.o.; Learnetic S.A. | 114 |
| 303 | Układ w Krewie | https://zpe.gov.pl/b/PrYTltZiw | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 332 |
| 304 | Umarł król, niech żyje lud. Proklamowanie Republiki Francuskiej i wojna z wrogami ojczyzny | https://zpe.gov.pl/b/Pe4HfCrp3 | CC BY-SA 3.0 | Ilustracja w tle: domena publiczna, Wikimedia Commons . Źródło mapy: ContentPlus.sp.z o.o. | 543 |
| 305 | Unia polsko‑saska. Wojna o sukcesję polską | https://zpe.gov.pl/b/PJN7FHRtC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 338 |
| 306 | Upadek dynastii Karolingów | https://zpe.gov.pl/b/PenctK72s | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o.; Contentplus.sp. z o.o., Stentor | 700 |
| 307 | Urzędy republikańskie | https://zpe.gov.pl/b/POzXRGE3B | CC BY-SA 3.0 | Contentplus .pl na podstawie Cursus honorum - Ultimate Latin Cultural Study Guide | 1267 |
| 308 | Uwarunkowania geograficzne starożytnej Grecji | https://zpe.gov.pl/b/PDCX5X8XI | CC BY-SA 3.0 | Getoryk | 766 |
| 309 | Uwarunkowania współpracy niemiecko‑sowieckiej w latach 1939‑1941 i jej konsekwencje dla państw i narodów Europy Środkowej - wypracowanie | https://zpe.gov.pl/b/PsL9CiNhq | CC BY-SA 3.0 | Alokasta, Wikimedia Commons | 87 |
| 310 | Uwłaszczenie chłopów pod zaborami | https://zpe.gov.pl/b/P151PNumz | CC BY-SA 3.0; CC0 | Biblioteka Narodowa, Wikimedia Commons; Contentplus.pl sp. z o.o. na podstawie: Encyklopedia historii gospodarczej Polski do 1945 roku , pod red. A. Mączaka, t. 2, Warszawa 1981, s. 199 | 1263 |
| 311 | Uznajemy, potwierdzamy i przyrzekamy. Przywileje szlacheckie | https://zpe.gov.pl/b/PHKCgkru3 | CC BY-SA 3.0 | Contentplus.pl na podstawie fotografii przywilei z wikipedia.org | 749 |
| 312 | U zarania nowoczesności. Węgiel, stal i elektryczność zmieniają świat, XIX–XX w. | https://zpe.gov.pl/b/Pq16ytslJ | CC BY-SA 3.0 | Contentplus.pl | 2093 |
| 313 | Walka o kształt polityczny państwa polskiego. Konstytucja marcowa | https://zpe.gov.pl/b/PrrmtuH2b | CC BY 3.0 | Contentplus.pl sp. z o.o. | 175 |
| 314 | Walka o prawa obywatelskie w Ameryce | https://zpe.gov.pl/b/PR0CPhBs8 | CC BY-SA 3.0 | dostępny w internecie: readingthepictures.org | 86 |
| 315 | Walka o wpływy nad Bałtykiem i Inflanty | https://zpe.gov.pl/b/P68ZdFYBt | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Atlas historyczny od starożytności do współczesności , Nowa Era, Warszawa 2019, s. 54-55 | 384 |
| 316 | Walka o zjednoczenie kraju. Władysław Łokietek | https://zpe.gov.pl/b/PgLeOuxft | CC BY-SA 3.0 | Contentplus .pl sp. z o.o., Stentor | 142 |
| 317 | Walki diadochów i rozpad imperium Aleksandra | https://zpe.gov.pl/b/PwdGCRof9 | CC BY-SA 3.0 | Contentplus .pl | 454 |
| 318 | Walki na Bałkanach i w Afryce Północnej | https://zpe.gov.pl/b/PMjP2dfuj | CC BY-SA 3.0 | Contentplus.pl sp. z o.o., Stentor | 373 |
| 319 | Walki o władzę. Upadek senioratu | https://zpe.gov.pl/b/P1G6UmPaP | CC BY-SA 3.0 | Contentplus .pl | 130 |
| 320 | Walki z Austrią, Prusami i Rosją. Wielkie Cesarstwo | https://zpe.gov.pl/b/Pa0NgDn5W | CC BY-SA 3.0 | Contentplus.pl | 60 |
| 321 | We własnych sprawach sami sobą rządzimy - administracja lokalna w Polsce XIV‑XV w. | https://zpe.gov.pl/b/PPNKc8jia | CC BY-SA 3.0 | Contentplus.pl | 302 |
| 322 | Wiek XVI - powtórzenie | https://zpe.gov.pl/b/Po2XHzUZ0 | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 367 |
| 323 | Wielcy reformatorzy | https://zpe.gov.pl/b/P1EBdHkLw | CC BY 3.0; CC BY 4.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 61 |
| 324 | Wielka kolonizacja | https://zpe.gov.pl/b/PnyX8DMV0 | CC BY-SA 3.0 | Contentplus .pl | 211 |
| 325 | Wielka wojna północna i jej następstwa | https://zpe.gov.pl/b/P34q9gQ0K | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o. na podstawie Historia sztuki wojennej do roku 1939 , pod red. P.A. Rotmistrowa, Warszawa 1967, s. 147 | 148 |
| 326 | Wielka wojna z zakonem | https://zpe.gov.pl/b/P1D2zvtp1 | CC BY-SA 3.0 | Contentplus.pl | 290 |
| 327 | Wielka zmiana. Chrystianizacja Europy | https://zpe.gov.pl/b/P335kx7XK | CC BY 2.0; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; David Rowan , Birmingham Museum and Art Gallery; Erik Christensen; Karl Baron; Lykke124; Michael Fiegle; Nkoke; Ondřej Žváček , Czechy; Sebastian Wallroth; a. nn.; a.nn. | 1336 |
| 328 | Wielkie Cesarstwo i Europa Napoleona | https://zpe.gov.pl/b/P10brgBdb | CC BY-SA 3.0 | Contentplus.pl | 885 |
| 329 | Wieś w średniowieczu | https://zpe.gov.pl/b/PrhKwVnzi | CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Christopher Walker; Flore Alleman; Izvora; Kapacytron; Lestat | 184 |
| 330 | Wiosna Ludów na ziemiach polskich. Na fali europejskiego buntu | https://zpe.gov.pl/b/PtaweMJOv | CC BY 2.5; CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o.; Sailko, Wikimedia Commons | 462 |
| 331 | Wiosna Ludów w monarchii Habsburgów. Rewolucja w Wiedniu i powstanie węgierskie | https://zpe.gov.pl/b/PN8PtOVuw | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Netzach, Wikimedia Commons | 69 |
| 332 | Wojenne plany Stalina. Ostatnie dni pokoju | https://zpe.gov.pl/b/P1H8lAAZx | CC BY-SA 3.0 | Bundesarchiv, Bild 101I-013-0068-33A / Höllenthal, Wikimedia Commons; Bundesarchiv, Bild 183-R69173, Wikimedia Commons | 181 |
| 333 | Wojna Greków o niepodległość | https://zpe.gov.pl/b/PIWlhlb0t | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1738 |
| 334 | Wojna domowa w Hiszpanii. Zapowiedź światowego konfliktu | https://zpe.gov.pl/b/P7975OAGb | CC BY-SA 3.0 | Bundesarchiv, Bild, Wikimedia Commons; Papamanila | 119 |
| 335 | Wojna europejska (trzydziestoletnia) z udziałem Francji. Pokój westfalski | https://zpe.gov.pl/b/P1HaawMsO | CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Tebdi, Wikimedia Commons | 188 |
| 336 | Wojna niemiecko–sowiecka | https://zpe.gov.pl/b/P6MD28Nze | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn. | 272 |
| 337 | Wojna polsko‑bolszewicka | https://zpe.gov.pl/b/P15XoGu55 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 187 |
| 338 | Wojna polsko‑bolszewicka | https://zpe.gov.pl/b/PNHwFbUkk | CC BY 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; Leonard Winterowski; a. nn. | 370 |
| 339 | Wojna poza Europą | https://zpe.gov.pl/b/PlYAxcuWD | CC BY 3.0; CC BY-SA 3.0 | Bundesarchiv; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół | 180 |
| 340 | Wojna stuletnia i jej skutki | https://zpe.gov.pl/b/PKPWAf6aL | CC BY-SA 3.0 | Contentplus .pl sp. z o.o.; Contentplus.sp. z o.o. | 935 |
| 341 | Wojna trzydziestoletnia. Działania wojenne w latach 1624–1635 | https://zpe.gov.pl/b/P2xJMn6Z | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 208 |
| 342 | Wojna trzynastoletnia z zakonem krzyżackim | https://zpe.gov.pl/b/PYuzD6Zlj | CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o. | 1052 |
| 343 | Wojna wietnamska | https://zpe.gov.pl/b/P1CP2s4L4 | CC BY-SA 3.0 | Contentplus.pl | 141 |
| 344 | Wojna wszystkich ze wszystkimi: mandaty brytyjski i francuski na Bliskim Wschodzie. | https://zpe.gov.pl/b/PVa9hwiT | CC BY-SA 3.0 | Contentplus.pl | 105 |
| 345 | Wojna w Korei | https://zpe.gov.pl/b/PT8OmLJOc | CC BY-SA 3.0 | Contentplus.pl; Contentplus.pl sp. z o.o. | 473 |
| 346 | Wojna w obronie Konstytucji 3 maja | https://zpe.gov.pl/b/PF5GviBe1 | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Krystian Chariza i zespół oraz Wikimedia Commons; Contentplus.sp. z o.o. na podstawie Tadeusz Korzon, Polona, 1894 | 624 |
| 347 | Wojna ze Szwecją w Inflantach i Prusach | https://zpe.gov.pl/b/PywBMdEJV | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 858 |
| 348 | Wojna ze Szwedami o wyzwolenie Rzeczypospolitej | https://zpe.gov.pl/b/P5tSg9uR0 | CC BY-SA 3.0 | Contentplus.pl | 720 |
| 349 | Wojna ze Związkiem Sowieckim – Plan Barbarossa | https://zpe.gov.pl/b/Pn2ik4kyk | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 363 |
| 350 | Wojna z Austrią i powiększenie Księstwa | https://zpe.gov.pl/b/PtaI4Hy1t | CC BY-SA 3.0 | Contentplus.pl | 300 |
| 351 | Wojna z Austrią, wyprawa moskiewska i upadek Księstwa Warszawskiego | https://zpe.gov.pl/b/P9UPss7Uf | CC BY-SA 3.0 | Contentplus.pl | 3145 |
| 352 | Wojna z Rosją o Ukrainę | https://zpe.gov.pl/b/PV3jt7KoG | CC BY-SA 2.5 | Adam Kersten, Hoodinski, Wikimedia Commons | 221 |
| 353 | Wojny Bolesława Chrobrego z Cesarstwem | https://zpe.gov.pl/b/Pe35iFtzw | CC BY-SA 3.0 | Contentplus .pl | 207 |
| 354 | Wojny Greków z Persami | https://zpe.gov.pl/b/PR2BtTffk | CC BY-SA 3.0 | Contentplus.pl sp. z o.o., Stentor | 176 |
| 355 | Wojny Stefana Batorego z Moskwą | https://zpe.gov.pl/b/P10IaeiHc | CC BY-SA 3.0 | Contentplus.pl | 830 |
| 356 | Wojny hugenockie we Francji | https://zpe.gov.pl/b/P1DrM3ETa | CC BY-SA 3.0 | Contentplus.pl | 91 |
| 357 | Wojny punickie | https://zpe.gov.pl/b/P1fH53wPW | CC BY-SA 3.0 | Contentplus .sp. z o.o. na podstawie bible-history.com | 1374 |
| 358 | Wojny w byłej Jugosławii | https://zpe.gov.pl/b/PGzpQD32z | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 790 |
| 359 | Wojny z Moskwą i walki o koronę carów | https://zpe.gov.pl/b/PLKoG1xPC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 340 |
| 360 | Wojny z Moskwą w pierwszej połowie XVII wieku. Wielka Smuta | https://zpe.gov.pl/b/PytTPZh4U | CC BY-SA 3.0 | Englishsquare .pl sp. z o.o. | 961 |
| 361 | Wpływ kryzysów naftowych na życie polityczne i gospodarcze krajów zachodnich | https://zpe.gov.pl/b/PzTJ6wEBB | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie EIA, bankier.pl | 309 |
| 362 | Współpraca koalicji antyhitlerowskiej | https://zpe.gov.pl/b/P11DsSplU | CC BY 3.0 | Contentplus .pl sp. z o.o.; a. nn. domena publiczna | 122 |
| 363 | Wybuch wojny. Kampania wrześniowa | https://zpe.gov.pl/b/P9Lq91uyE | CC BY-SA 3.0 | Contentplus sp. z o. o. na podstawie T. Jurga, Obrona Polski 1939 , Warszawa 1990, str. 540; Contentplus.pl; Contentplus.pl sp. z o.o.; Contentplus.sp. z o.o. na podstawie Cz. Brzoza, Polska w czasach niepodległości i drugiej wojny światowej (1918-1945), Wielka historia Polski , tom 9. Kraków 2001, str. 264 | 2335 |
| 364 | Wychodzimy z wojny. Koniec działań wojennych na pozostałych frontach I wojny światowej | https://zpe.gov.pl/b/PVvwCppQX | CC BY-SA 3.0 | Contentplus.pl | 140 |
| 365 | Wyprawa Magellana. Znaczenie odkryć geograficznych | https://zpe.gov.pl/b/P18i4S8CZ | CC BY-SA 3.0 | Contentplus sp. z o. o. | 323 |
| 366 | Wyprawa Napoleona na Rosję i jej skutki | https://zpe.gov.pl/b/P9UPO0oBd | CC BY-SA 3.0 | Contentplus.pl | 1368 |
| 367 | Wyprawa na Moskwę i jej skutki | https://zpe.gov.pl/b/PPV536hBU | CC BY-SA 3.0 | Contentplus.pl | 1983 |
| 368 | Wyprawy krzyżowe | https://zpe.gov.pl/b/PCVREPH5T | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. | 2991 |
| 369 | Wyprawy morskie Portugalczyków | https://zpe.gov.pl/b/P4BEadvJC | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 215 |
| 370 | Wyścig kolonialny | https://zpe.gov.pl/b/PKenJYGlO | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 531 |
| 371 | W cieniu walki o sukcesję - od Ludwika Andegaweńskiego do Jadwigi | https://zpe.gov.pl/b/PGrDHoY5w | CC BY-SA 3.0 | Contentplus.sp. z o.o. | 1483 |
| 372 | W imię zysku | https://zpe.gov.pl/b/Ptrweh55D | CC BY-SA 3.0 | Contentplus .pl | 889 |
| 373 | W kraju i za granicą. Rzeczpospolita po I rozbiorze | https://zpe.gov.pl/b/PLIAC73Og | CC BY-SA 3.0 | — | 1102 |
| 374 | W kraju nad Nilem. Egipt faraonów | https://zpe.gov.pl/b/PcCNx1NrN | CC BY-SA 3.0 | Contentplus .pl | 520 |
| 375 | W obopólnym interesie - układ w Krewie | https://zpe.gov.pl/b/P1y1epiZn | CC BY-SA 3.0 | Contentplus.pl | 62 |
| 376 | W przededniu pożaru. Problem kozacki i wojsko zaporoskie w I poł. XVII w. | https://zpe.gov.pl/b/P6xQgK54e | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 63 |
| 377 | W przededniu rewolucji. Francja Ludwika XVI | https://zpe.gov.pl/b/PMIB0x68q | CC BY-SA 3.0 | Contentplus.sp. z o.o. | 2016 |
| 378 | W świecie wasali i seniorów. Rozwój feudalizmu i systemu lennego | https://zpe.gov.pl/b/Pqj1hKd2C | CC BY-SA 3.0 | Contentplus .pl sp. z o.o. na podstawie old.mac.pl | 287 |
| 379 | Władza i władcy we wczesnym średniowieczu | https://zpe.gov.pl/b/PikULUPBG | CC BY 3.0 | Contentplus.pl sp. z o.o.; a.nn. | 298 |
| 380 | ZSRS w l. 1945‑1991 | https://zpe.gov.pl/b/P1C3kcqQe | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Erwin Lux; Karla Friedrich Gahlbeck; Krystian Chariza i zespół | 155 |
| 381 | Zabór pruski w latach 1815–1846 | https://zpe.gov.pl/b/PfMxJnk1N | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 629 |
| 382 | Zakony rycerskie | https://zpe.gov.pl/b/PRN5SeAMP | CC BY-SA 2.0; CC BY-SA 3.0 | David Liuzzo, Wikimedia Commons; Wikimedia Commons | 69 |
| 383 | Zbrodnia bez kary. Polscy jeńcy w ZSRS i zbrodnia katyńska | https://zpe.gov.pl/b/P6f0yhyfk | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie panstwowa.policja.pl | 227 |
| 384 | Zbrojenia nazistowskich Niemiec. Remilitaryzacja Nadrenii. | https://zpe.gov.pl/b/PpfLIAk2a | CC BY-SA 3.0 | Hans Karner, Wikimedia Commons | 918 |
| 385 | Ziemie Rzeczypospolitej po III rozbiorze | https://zpe.gov.pl/b/PHGOdvFhn | CC BY-SA 3.0 | Contentplus.pl | 212 |
| 386 | Ziemie polskie w czasach industrializacji | https://zpe.gov.pl/b/P1DuqpPpV | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1047 |
| 387 | Zjednoczenie Niemiec w 1990 roku | https://zpe.gov.pl/b/P190Olcub | CC BY-SA 2.0; CC BY-SA 3.0 | RIA Novosti archive, image #428452 / Boris Babanov, Wikimedia Commons; Wikimedia Commons | 64 |
| 388 | Zjednoczenie Włoch | https://zpe.gov.pl/b/P17DUogBS | CC BY-SA 3.0 | Contentplus.pl, Stentor; Pramzan, Wikimedia Commons | 361 |
| 389 | Zmiany granic Rzeczypospolitej w XVII w. – podsumowanie | https://zpe.gov.pl/b/P7mTM8rEV | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 791 |
| 390 | Zmiany kulturowe i społeczne po II wojnie światowej | https://zpe.gov.pl/b/PdfiIHKLT | CC BY 2.5; CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Derek Redmond , Paul Campbell; Johannes Aubele; Lothar Wolleh; Omroepvereniging VARA; Rich Niewirowski, Most Golden Gate Bridge , dostępny w internecie: https://pl.wikipedia.org/wiki/Golden_Gate_Bridge#/media/Plik:GoldenGateBridge-001.jpg [dostęp 20.08.2021]; RuthAS, DC-8-42 na lotnisku w Londynie , dostępny w internecie: https://pl.wikipedia.org/wiki/Douglas_DC-8#/media | 496 |
| 391 | Zmierzch dyktatur na Półwyspie Iberyjskim. „Rewolucja goździków” w Portugalii i śmierć gen. Francisca Franco w Hiszpanii | https://zpe.gov.pl/b/P13LH7Pno | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 806 |
| 392 | Zróżnicowanie cywilizacyjne Afryki przed odkryciami geograficznymi | https://zpe.gov.pl/b/PAT4I5xhE | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 81 |
| 393 | Związek Morski – imperium Ateńczyków | https://zpe.gov.pl/b/P19Bl5vKO | CC BY 3.0 | Contentplus .pl | 426 |
| 394 | Z Siedmiogrodu do Rzeczypospolitej. Panowanie Stefana Batorego | https://zpe.gov.pl/b/PoTb8Uly7 | CC BY-SA 2.0 | Dennis Jarvis from Halifax, Canada, Wikimedia Commons | 84 |
| 395 | Średniowiecze w naszym otoczeniu | https://zpe.gov.pl/b/Pvxsv5Fct | CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Andreas Praefcke , 2011; Contentplus.pl sp. z o.o.; Contentplus.pl sp. z o.o., muzyka: istockphoto.com; Katarzyna Czerwińska, 2013; Krystian Chariza i zespół; Michał Józefaciuk; Michał Koziczyński, 2010; Paolo da Reggio , 2005; Raimond Spekking; Vania Teofilo, 2006 | 676 |
| 396 | Średniowieczne miasto | https://zpe.gov.pl/b/PbbrhWG2G | CC BY 3.0; CC BY 4.0; CC BY-SA 2.5; CC BY-SA 3.0; CC BY-SA 4.0 | Fazer; Hiuppo; Jondu11; Krystian Chariza i zespół; Learnetic S.A.; Lestat; Shaqspeare | 313 |
| 397 | Środkowe wieki – epoka niedoceniana | https://zpe.gov.pl/b/P9nAJglz3 | CC BY 3.0; CC BY-SA 3.0 | Contentplus sp. z o.o.; Contentplus.pl sp. z o.o.; Contetplus.pl sp. z o.o.; PHGCOM; a. nn. | 237 |
| 398 | Świat hellenistyczny | https://zpe.gov.pl/b/P19X1rYsT | CC BY 3.0; CC BY-SA 3.0; CC BY-SA 4.0 | Contentplus.pl sp. z o.o., Stentor; Contentplus.sp. z o.o. na podstawie Kaidor, Wikimedia Commons; LivioAndronico, Wikimedia Commons; Sailko, Wikimedia Commons | 200 |
| 399 | Świat na drodze ku wojnie. Kształtowanie się przymierzy polityczno‑militarnych i wyścig zbrojeń | https://zpe.gov.pl/b/PGpoTbPHY | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie historicair, Wikimedia Commons . Dane za: A. Farmer, An Introduction to Modern European History 1890-1990 , Hodden Murray 2007, s. 71 | 255 |
| 400 | Świat na granicy „gorącej” wojny | https://zpe.gov.pl/b/PkuuChQhZ | CC BY 3.0; CC BY-SA 3.0 | Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; a. nn, Army official Korean War image archive; a. nn. | 225 |
| 401 | Świat po zakończeniu zimnej wojny. Mocarstwowa rola Stanów Zjednoczonych | https://zpe.gov.pl/b/PFM3EiAMl | CC BY 2.0; CC BY-SA 2.0 | Ed Yourdon from New York City , USA; Steve/Ruth Bosman, Wikimedia Commons | 98 |
| 402 | Świat poza Europą | https://zpe.gov.pl/b/PjlB5s3Ay | CC BY 3.0; CC BY-SA 3.0 | BabelStone; Bin im Garten , Muzeum Etnograficzne w Berlinie; Contentplus sp. z o.o.; Contentplus.pl sp. z o.o.; Krystian Chariza i zespół; PHGCOM , dostępny w internecie: wikimedia commons; Warofdreams , Victoria & Albert Museum; a. nn. | 1220 |
| 403 | „Kocioł bałkański” i wojny na Bałkanach | https://zpe.gov.pl/b/P1Fs525a1 | CC BY-SA 3.0 | ContentPlus.sp. z o.o. | 100 |
| 404 | „Krwawa niedziela” w Petersburgu i rewolucja 1905 r. | https://zpe.gov.pl/b/PwTdlbcgL | CC BY-SA 3.0; CC BY-SA 4.0 | Bundesarchiv, Bild, Wikimedia Commons; fot. SerSem, Wikimedia Commons; fot. Vladimir Andrianow, Wikimedia Commons | 71 |
| 405 | „Na zachodzie bez zmian”. Sytuacja na froncie zachodnim w latach 1915–1916 | https://zpe.gov.pl/b/Pz7WZKiAu | CC BY-SA 3.0 | Contentplus.sp. z o.o. na podstawie Wikimedia Commons | 434 |
| 406 | „Testament Krzywoustego”. Przyczyny polityczne i społeczno‑gospodarcze oraz następstwa rozbicia dzielnicowego – wypracowanie | https://zpe.gov.pl/b/PSsrUQ9QX | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. na podstawie Farary, Wikimedia Commons; Contentplus.sp. z o.o. na podstawie Kargul1965, Wikimedia Commons | 169 |
| 407 | „Ucieczka od wolności”. Kryzys gospodarki i demokracji w Europie po I wojnie światowej | https://zpe.gov.pl/b/PyNKUKcW5 | CC BY-SA 3.0 | Contentplus.pl | 388 |
| 408 | „Wojna polska” 1812 r. i okupacja Księstwa Warszawskiego | https://zpe.gov.pl/b/PKgdZCx6 | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 885 |
| 409 | „Za te pieniądze nic kupić nie można”. Gospodarka państw bloku wschodniego | https://zpe.gov.pl/b/PSdiilLjs | CC BY-SA 3.0 | Contentplus.pl sp. z o.o. | 1072 |
