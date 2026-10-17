"""dev-b question bank (era: nowożytność ok. 1490–1815). Hand-written from Polish Wikipedia extracts
(see sources.tsv); every gold answer was checked against the fetched article text. Evaluation only."""

Q = []

def add(src, typ, question, answer, accept=None, points=1):
    Q.append(dict(source_title=src, type=typ, question=question, answer=answer,
                  accept=accept or [], points=points))

I_ABCD = "Podaj literę poprawnej odpowiedzi."
I_PF = "Dla każdego zdania napisz P (prawda) albo F (fałsz). Odpowiedź podaj jako ciąg liter oddzielonych przecinkami – jedna litera dla każdego zdania, w kolejności zdań."
I_CHRONO = "Uporządkuj wydarzenia chronologicznie (od najwcześniejszego). Odpowiedz ciągiem liter, np. B, A, D, C."
I_MATCH = "Odpowiedz w formacie: 1-B, 2-A, 3-C."
I_OPEN = "Odpowiedz krótko."

# --- Traktat z Tordesillas
add("Traktat z Tordesillas", "open",
    "W którym roku władcy Portugalii i Hiszpanii podpisali traktat z Tordesillas, dzielący między te państwa sfery wpływów w Nowym Świecie? Podaj rok. " + I_OPEN,
    "1494", ["1494 r.", "1494 roku", "w 1494", "7 czerwca 1494"])

add("Traktat z Tordesillas", "abcd",
    "Zgodnie z traktatem z Tordesillas linia demarkacyjna między strefami wpływów Portugalii i Hiszpanii miała przebiegać południkowo:\n"
    "A. 100 lig na zachód od Wysp Zielonego Przylądka\n"
    "B. 370 lig na zachód od Wysp Zielonego Przylądka\n"
    "C. 370 lig na wschód od Azorów\n"
    "D. 100 lig na zachód od Wysp Kanaryjskich\n" + I_ABCD,
    "B")

# --- Vasco da Gama
add("Vasco da Gama", "abcd",
    "Do którego miasta na południowo-zachodnim wybrzeżu Indii dotarła w maju 1498 roku wyprawa Vasco da Gamy?\n"
    "A. Goa\nB. Kalikat\nC. Malakka\nD. Bombaj\n" + I_ABCD,
    "B")

add("Vasco da Gama", "pf",
    "Oceń prawdziwość zdań dotyczących Vasco da Gamy:\n"
    "1. W swoją pierwszą wyprawę do Indii Vasco da Gama wyruszył w 1497 roku z Santa Maria de Belém (obecnie dzielnica Lizbony).\n"
    "2. To Vasco da Gama nadał południowemu krańcowi Afryki nazwę Przylądek Burz.\n"
    "3. Portugalska epopeja narodowa „Luzjady” autorstwa Luísa de Camões w dużej mierze dotyczy podróży Vasco da Gamy.\n" + I_PF,
    "P, F, P", points=2)

# --- Wielkie odkrycia geograficzne
add("Wielkie odkrycia geograficzne", "chrono",
    "Poniżej wymieniono wydarzenia epoki wielkich odkryć geograficznych:\n"
    "A. wyruszenie wyprawy Ferdynanda Magellana, która jako pierwsza opłynęła Ziemię\n"
    "B. opłynięcie Przylądka Dobrej Nadziei przez Bartolomeu Diasa\n"
    "C. dotarcie Holendra Willema Janszoona do Australii\n"
    "D. dotarcie wyprawy Krzysztofa Kolumba do wybrzeży Ameryki\n" + I_CHRONO,
    "B, D, A, C", points=2)

add("Wielkie odkrycia geograficzne", "open",
    "Jak nazywano sporządzane od XIII wieku niezwykle dokładne mapy wybrzeży, zaopatrzone w pierwsze siatki kartograficzne, które miały charakter praktyczny i były kluczowe dla dalekich podróży morskich? " + I_OPEN,
    "portolany", ["portolan", "portolany (mapy portolanowe)", "mapy portolanowe"])

# --- Krzysztof Kolumb
add("Krzysztof Kolumb", "pf",
    "Oceń prawdziwość zdań dotyczących Krzysztofa Kolumba:\n"
    "1. Kolumb urodził się prawdopodobnie w Genui.\n"
    "2. Plan Kolumba dotarcia do Azji drogą zachodnią odrzucili doradcy króla Portugalii Jana II.\n"
    "3. Brat Kolumba, Bartolomeo, założył w 1496 roku na Haiti Santo Domingo – najstarsze istniejące do dziś hiszpańskie miasto w Ameryce.\n"
    "4. Kolumb zmarł w 1506 roku w Lizbonie.\n" + I_PF,
    "P, P, P, F", points=2)

# --- Ferdynand Magellan
add("Ferdynand Magellan", "abcd",
    "Jak Ferdynand Magellan nazwał odkrytą w 1520 roku cieśninę (dziś noszącą jego imię), do której jego flota wpłynęła 1 listopada?\n"
    "A. Cieśnina Wszystkich Świętych\nB. Cieśnina Dobrej Nadziei\nC. Cieśnina Świętego Juliana\nD. Cieśnina Dziewic\n" + I_ABCD,
    "A")

add("Ferdynand Magellan", "open",
    "Na której wyspie Archipelagu Filipińskiego zginął Ferdynand Magellan 27 kwietnia 1521 roku w walce z miejscowymi mieszkańcami? " + I_OPEN,
    "Mactan", ["wyspa Mactan", "na Mactan"])

# --- Reformacja
add("Reformacja", "match",
    "Dopasuj odłam chrześcijaństwa powstały w wyniku reformacji do jego twórcy (twórców) i roku powstania.\n"
    "1. luteranizm\n2. anglikanizm\n3. kalwinizm\n4. nowożytny antytrynitaryzm\n"
    "A. Henryk VIII, 1534\nB. Jan Kalwin i Huldrych Zwingli, 1536\nC. Marcin Luter, 1517\nD. Miguel Servet i Faust Socyn, 1562\n"
    "Odpowiedz w formacie: 1-B, 2-A, 3-D, 4-C.",
    "1-C, 2-A, 3-B, 4-D", points=2)

add("Reformacja", "open",
    "Jak nazywał się związek utworzony w 1531 roku przez niemieckich książąt popierających reformację, którego celem była m.in. wspólna obrona interesów państw protestanckich? " + I_OPEN,
    "Związek szmalkaldzki", ["związek szmalkaldzki", "Liga szmalkaldzka", "liga szmalkaldzka"])

# --- Marcin Luter
add("Marcin Luter", "abcd",
    "W którym mieście Marcin Luter urodził się (1483) i zmarł (1546)?\n"
    "A. Wittenberga\nB. Erfurt\nC. Eisleben\nD. Wormacja\n" + I_ABCD,
    "C")

add("Marcin Luter", "open",
    "Do jakiego zakonu wstąpił Marcin Luter 17 lipca 1505 roku, po ślubowaniu złożonym podczas burzy pod Stotternheim? " + I_OPEN,
    "augustianów", ["augustianie", "zakon augustianów", "augustianów eremitów", "augustianie eremici"])

# --- Jan Kalwin
add("Jan Kalwin", "abcd",
    "Jak nazywa się najważniejsze dzieło Jana Kalwina, opublikowane po raz pierwszy w 1536 roku w Bazylei?\n"
    "A. Institutio religionis christianae\nB. De ecclesia\nC. Imago mundi\nD. De revolutionibus orbium coelestium\n" + I_ABCD,
    "A")

add("Jan Kalwin", "pf",
    "Oceń prawdziwość zdań dotyczących Jana Kalwina:\n"
    "1. Jan Kalwin urodził się w Noyon we francuskiej Pikardii.\n"
    "2. Do pozostania w Genewie w 1536 roku przekonał Kalwina reformator Wilhelm Farel.\n"
    "3. Lata 1538–1541, po wydaleniu z Genewy, Kalwin spędził w Zurychu.\n" + I_PF,
    "P, P, F", points=2)

# --- Sobór trydencki
add("Sobór trydencki", "open",
    "Który polski kardynał był jednym z legatów papieskich w III fazie soboru trydenckiego (1562–1563), za pontyfikatu Piusa IV? Podaj imię i nazwisko. " + I_OPEN,
    "Stanisław Hozjusz", ["Hozjusz", "kardynał Stanisław Hozjusz"])

add("Sobór trydencki", "abcd",
    "Do którego miasta w marcu 1547 roku przeniesiono obrady soboru trydenckiego (z powodu rzekomej epidemii w Trydencie)?\n"
    "A. Mantua\nB. Bolonia\nC. Rzym\nD. Wenecja\n" + I_ABCD,
    "B")

add("Sobór trydencki", "chrono",
    "Poniżej wymieniono wydarzenia związane z soborem trydenckim:\n"
    "A. zapowiedź soboru bullą Pawła III „Laetare Ierusalem”\n"
    "B. przeniesienie obrad soboru do Bolonii\n"
    "C. zatwierdzenie dekretów soboru przez papieża Piusa IV\n"
    "D. zwołanie przez Pawła III soboru do Mantui\n" + I_CHRONO,
    "D, A, B, C", points=2)

# --- Hołd pruski 1525
add("Hołd pruski 1525", "open",
    "Kto złożył hołd lenny królowi Zygmuntowi I Staremu na rynku krakowskim 10 kwietnia 1525 roku? Podaj imię i nazwisko (nazwę rodu). " + I_OPEN,
    "Albrecht Hohenzollern", ["Albrecht", "książę Albrecht", "Albrecht Hohenzollern-Ansbach"])

add("Hołd pruski 1525", "abcd",
    "Na mocy którego traktatu, zawartego dwa dni przed hołdem pruskim (8 kwietnia 1525 roku), Prusy Zakonne zostały przekształcone w świeckie Księstwo Pruskie, lenno Królestwa Polskiego?\n"
    "A. traktatu toruńskiego\nB. traktatu krakowskiego\nC. traktatu welawskiego\nD. traktatu kaliskiego\n" + I_ABCD,
    "B")

# --- Unia lubelska
add("Unia lubelska", "pf",
    "Oceń prawdziwość zdań dotyczących unii lubelskiej z 1569 roku:\n"
    "1. Unia lubelska była unią realną, w odróżnieniu od wcześniejszych unii personalnych.\n"
    "2. Wspólny sejm walny Rzeczypospolitej miał obradować w Krakowie.\n"
    "3. Zachowano odrębne wojsko polskie i litewskie.\n"
    "4. Na mocy postanowień unii wcielono do Korony Prusy Królewskie.\n" + I_PF,
    "P, F, P, P", points=2)

# --- Konfederacja warszawska (1573)
add("Konfederacja warszawska (1573)", "abcd",
    "Który z wymienionych duchownych, biskup krakowski i podkanclerzy koronny, podpisał akt konfederacji warszawskiej z 1573 roku (mimo sprzeciwu większości episkopatu)?\n"
    "A. Stanisław Karnkowski\nB. Jakub Uchański\nC. Franciszek Krasiński\nD. Stanisław Hozjusz\n" + I_ABCD,
    "C")

add("Konfederacja warszawska (1573)", "open",
    "Na jakim sejmie (podaj rodzaj sejmu) podjęto 28 stycznia 1573 roku uchwałę znaną jako konfederacja warszawska, gwarantującą szlachcie swobodę wyznania? " + I_OPEN,
    "konwokacyjnym", ["sejm konwokacyjny", "sejmie konwokacyjnym", "konwokacyjny", "na sejmie konwokacyjnym"])

# --- Artykuły henrykowskie
add("Artykuły henrykowskie", "pf",
    "Oceń prawdziwość zdań dotyczących artykułów henrykowskich:\n"
    "1. Nakazywały królowi zwoływanie sejmu walnego co dwa lata na okres 6 tygodni.\n"
    "2. Zobowiązywały króla do stałego utrzymywania przy sobie rady złożonej z szesnastu senatorów rezydentów.\n"
    "3. Pozwalały królowi na używanie tytułu dziedzicznego.\n"
    "4. W ostatnim artykule zezwalały na wypowiedzenie królowi posłuszeństwa w razie złamania przez niego zobowiązań.\n" + I_PF,
    "P, P, F, P", points=2)

# --- Wolna elekcja
add("Wolna elekcja", "open",
    "W jakiej wsi pod Warszawą odbyła się w 1573 roku pierwsza wolna elekcja? " + I_OPEN,
    "Kamion", ["we wsi Kamion", "Kamionie", "w Kamionie", "wieś Kamion"])

# --- Henryk III Walezy
add("Henryk III Walezy", "abcd",
    "Kto koronował Henryka Walezego na króla Polski 21 lutego 1574 roku w katedrze wawelskiej?\n"
    "A. biskup kujawski Stanisław Karnkowski\nB. prymas Jakub Uchański\nC. biskup krakowski Franciszek Krasiński\nD. marszałek wielki koronny Jan Firlej\n" + I_ABCD,
    "B")

add("Henryk III Walezy", "chrono",
    "Poniżej wymieniono wydarzenia z życia Henryka Walezego:\n"
    "A. koronacja na króla Polski w katedrze wawelskiej\n"
    "B. koronacja w Reims na króla Francji\n"
    "C. potajemna ucieczka z Wawelu\n"
    "D. przekroczenie granicy Polski w Międzyrzeczu po dwumiesięcznej podróży z Francji\n" + I_CHRONO,
    "D, A, C, B", points=2)

# --- Stefan Batory
add("Stefan Batory", "open",
    "Jak nazywał się sąd utworzony w 1578 roku za zgodą Stefana Batorego, który stał się najwyższym sądem apelacyjnym dla Korony Królestwa Polskiego? " + I_OPEN,
    "Trybunał Koronny", ["Trybunał Koronny", "trybunał koronny", "Trybunał Główny Koronny"])



# --- Unia brzeska
add("Unia brzeska", "abcd",
    "Jak nazywano przeciwników unii brzeskiej (1596) wśród wyznawców prawosławia w Rzeczypospolitej?\n"
    "A. unici\nB. arianie\nC. dysydenci\nD. dyzunici\n" + I_ABCD,
    "D")

# --- Zygmunt III Waza
add("Zygmunt III Waza", "abcd",
    "Pod jaką miejscowością hetman Jan Zamoyski rozbił w styczniu 1588 roku wojska arcyksięcia Maksymiliana III Habsburga, kontrkandydata Zygmunta III Wazy, i wziął go do niewoli?\n"
    "A. pod Kircholmem\nB. pod Guzowem\nC. pod Byczyną\nD. pod Lubiszewem\n" + I_ABCD,
    "C")

# --- Rokosz Zebrzydowskiego
add("Rokosz Zebrzydowskiego", "abcd",
    "W której bitwie w 1607 roku wojska królewskie Zygmunta III Wazy pokonały rokoszan Mikołaja Zebrzydowskiego?\n"
    "A. pod Byczyną\nB. pod Janowcem\nC. pod Kłuszynem\nD. pod Guzowem\n" + I_ABCD,
    "D")

# --- Bitwa pod Chocimiem (1621)
add("Bitwa pod Chocimiem (1621)", "abcd",
    "Kto dowodził armią turecką w bitwie pod Chocimiem w 1621 roku, gdy naprzeciw niej stanęła armia Rzeczypospolitej Jana Karola Chodkiewicza?\n"
    "A. sułtan Osman II\nB. wezyr Kara Mustafa\nC. sułtan Mehmed IV\nD. chan Islam III Girej\n" + I_ABCD,
    "A")

# --- Bitwa pod Beresteczkiem
add("Bitwa pod Beresteczkiem", "abcd",
    "Kto, dowodząc w zastępstwie Bohdana Chmielnickiego, wyprowadził resztki wojsk kozackich z bagien nad rzeką Płaszówką po klęsce pod Beresteczkiem (1651)?\n"
    "A. Iwan Wyhowski\nB. Tymofiej Chmielnicki\nC. Iwan Bohun\nD. Piotr Doroszenko\n" + I_ABCD,
    "C")

# --- Pokój oliwski
add("Pokój oliwski", "abcd",
    "Które z poniższych postanowień zawierał pokój oliwski z 1660 roku, kończący potop szwedzki?\n"
    "A. Rzeczpospolita odzyskała od Szwecji całe Inflanty wraz z Rygą.\n"
    "B. Szwecja uzyskała Prusy Królewskie wraz z Gdańskiem.\n"
    "C. Rzeczpospolita odzyskała województwo smoleńskie.\n"
    "D. Jan II Kazimierz zrzekł się pretensji do tronu szwedzkiego w imieniu swoim i swych następców.\n" + I_ABCD,
    "D")

# --- Bitwa pod Wiedniem
add("Bitwa pod Wiedniem", "abcd",
    "Kto dowodził armią Imperium Osmańskiego w bitwie pod Wiedniem 12 września 1683 roku?\n"
    "A. sułtan Osman II\nB. Emeryk Thököly\nC. wezyr Kara Mustafa\nD. Uzun Ibrahim, pasza Budy\n" + I_ABCD,
    "C")

# --- Liberum veto
add("Liberum veto", "abcd",
    "Który poseł jest powszechnie (choć według historyków niesłusznie) uważany za pierwszego, który zerwał sejm, używając liberum veto w 1652 roku?\n"
    "A. Władysław Wiktoryn Siciński\nB. Jan Aleksander Olizar\nC. Jerzy Sebastian Lubomirski\nD. Andrzej Maksymilian Fredro\n" + I_ABCD,
    "A")

# --- Wojna o sukcesję hiszpańską
add("Wojna o sukcesję hiszpańską", "abcd",
    "Kto w wyniku wojny o sukcesję hiszpańską (1701–1714) został następcą bezdzietnie zmarłego Karola II na tronie Hiszpanii?\n"
    "A. arcyksiążę Karol Habsburg\nB. Józef Ferdynand Bawarski\nC. delfin Ludwik\nD. Filip V z dynastii Burbonów\n" + I_ABCD,
    "D")

# --- Konfederacja barska
add("Konfederacja barska", "abcd",
    "Jakie było naczelne hasło konfederatów barskich?\n"
    "A. „Za naszą i waszą wolność”\nB. „Wolność, równość, braterstwo”\nC. „Wiara i wolność”\nD. „Bóg, Honor, Ojczyzna”\n" + I_ABCD,
    "C")

# --- Komisja Edukacji Narodowej
add("Komisja Edukacji Narodowej", "abcd",
    "Kto był pierwszym prezesem Komisji Edukacji Narodowej (usuniętym z tego stanowiska w 1776 roku z powodu nadużyć finansowych)?\n"
    "A. Hugo Kołłątaj\nB. Adam Kazimierz Czartoryski\nC. Grzegorz Piramowicz\nD. biskup wileński Ignacy Jakub Massalski\n" + I_ABCD,
    "D")

# --- Konfederacja targowicka
add("Konfederacja targowicka", "abcd",
    "Kto był marszałkiem konfederacji koronnej w konfederacji targowickiej (1792)?\n"
    "A. Stanisław Szczęsny Potocki\nB. Franciszek Ksawery Branicki\nC. Seweryn Rzewuski\nD. Szymon Marcin Kossakowski\n" + I_ABCD,
    "A")

# --- Bitwa pod Racławicami
add("Bitwa pod Racławicami", "abcd",
    "Kto dowodził wojskami rosyjskimi, z którymi 4 kwietnia 1794 roku starły się pod Racławicami wojska Tadeusza Kościuszki?\n"
    "A. Aleksander Suworow\nB. Nikołaj Repnin\nC. generał major Aleksander Tormasow\nD. Iwan Fersen\n" + I_ABCD,
    "C")

# --- Legiony Polskie we Włoszech
add("Legiony Polskie we Włoszech", "abcd",
    "Dokąd Napoleon wysłał część Legionów Polskich po pokoju w Lunéville (1801), gdzie miały tłumić powstanie czarnoskórych niewolników?\n"
    "A. na Korsykę\nB. na wyspę Hispaniola/San Domingo (obecnie Haiti)\nC. do Egiptu\nD. na Sycylię\n" + I_ABCD,
    "B")

# --- Księstwo Warszawskie
add("Księstwo Warszawskie", "abcd",
    "Z którym państwem Księstwo Warszawskie (1807–1815) było związane unią personalną?\n"
    "A. z Cesarstwem Francuskim\nB. z Królestwem Prus\nC. z Królestwem Westfalii\nD. z Królestwem Saksonii\n" + I_ABCD,
    "D")

# --- Inwazja na Rosję (1812)
add("Inwazja na Rosję (1812)", "abcd",
    "Jak Napoleon oficjalnie nazwał kampanię przeciwko Rosji rozpoczętą w czerwcu 1812 roku przekroczeniem Niemna?\n"
    "A. drugą wojną polską\nB. wojną ojczyźnianą\nC. wyprawą moskiewską\nD. wojną o blokadę kontynentalną\n" + I_ABCD,
    "A")

# --- Mikołaj Kopernik
add("Mikołaj Kopernik", "abcd",
    "W którym mieście zmarł Mikołaj Kopernik w maju 1543 roku?\n"
    "A. w Toruniu\nB. w Krakowie\nC. we Fromborku\nD. w Lidzbarku Warmińskim\n" + I_ABCD,
    "C")

# ===================== PF =====================
add("Traktaty welawsko-bydgoskie", "pf",
    "Oceń prawdziwość zdań dotyczących traktatów welawsko-bydgoskich z 1657 roku:\n"
    "1. Po wymarciu męskiej linii Hohenzollernów Prusy Książęce miały przypaść Szwecji.\n"
    "2. Fryderyk Wilhelm i jego potomkowie w linii męskiej uzyskali suwerenność w Prusach Książęcych.\n"
    "3. Elektor otrzymał w lenno ziemię lęborsko-bytowską.\n"
    "4. Traktaty zaaprobował Sejm w 1658 roku, a potwierdził je później pokój oliwski.\n" + I_PF,
    "F, P, P, P", points=2)

add("Jan III Sobieski", "pf",
    "Oceń prawdziwość zdań dotyczących Jana III Sobieskiego:\n"
    "1. Urodził się na zamku w Olesku.\n"
    "2. Zmarł w Żółkwi.\n"
    "3. Tytuł Fidei Defensor (obrońcy wiary) nadał mu w 1684 roku papież Klemens X.\n"
    "4. Był prawnukiem hetmana wielkiego koronnego Stanisława Żółkiewskiego.\n" + I_PF,
    "P, F, F, P", points=2)

add("II rozbiór Polski", "pf",
    "Oceń prawdziwość zdań dotyczących II rozbioru Polski:\n"
    "1. II rozbioru dokonały wspólnie Prusy, Rosja i Austria.\n"
    "2. Traktat podziałowy między Katarzyną II a Fryderykiem Wilhelmem II podpisano 23 stycznia 1793 roku.\n"
    "3. Traktat z Rosją, w którym Rzeczpospolita zrzekła się m.in. województw mińskiego, kijowskiego, bracławskiego i podolskiego, podpisała deputacja sejmu grodzieńskiego.\n"
    "4. W II rozbiorze Rosja zagarnęła m.in. Gdańsk i Toruń.\n" + I_PF,
    "F, P, P, F", points=2)

add("Ludwik XIV", "pf",
    "Oceń prawdziwość zdań dotyczących Ludwika XIV:\n"
    "1. Ludwik XIV został koronowany na króla Francji w katedrze w Reims.\n"
    "2. W 1685 roku Ludwik XIV wydał edykt nantejski, gwarantujący równouprawnienie innowierców.\n"
    "3. Za panowania Ludwika XIV, w 1666 roku, założono Akademię Nauk.\n"
    "4. Do czasu osiągnięcia przez Ludwika 13. roku życia rządy sprawowali jego matka Anna Austriaczka i kardynał Richelieu.\n" + I_PF,
    "P, F, P, F", points=2)

add("Konstytucja 3 maja", "pf",
    "Oceń prawdziwość zdań dotyczących Konstytucji 3 maja:\n"
    "1. Konstytucja utrzymała zasadę wolnej elekcji.\n"
    "2. Konstytucja formalnie zniosła liberum veto.\n"
    "3. Głównym autorem tekstu Konstytucji był Hugo Kołłątaj.\n"
    "4. Konstytucja przestała być obowiązującym aktem prawnym 23 listopada 1793 roku, gdy sejm grodzieński uznał Sejm Czteroletni za niebyły.\n" + I_PF,
    "F, P, F, P", points=2)

add("Pokój w Tylży", "pf",
    "Oceń prawdziwość zdań dotyczących pokoju w Tylży (1807):\n"
    "1. Utworzone na mocy traktatu Wolne Miasto Gdańsk miało pozostawać pod protektoratem Cesarstwa Francuskiego.\n"
    "2. Prusy zachowały wszystkie ziemie zagarnięte w II i III rozbiorze Polski.\n"
    "3. Rozmowy Napoleona z carem Aleksandrem I prowadzono na tratwie zacumowanej pośrodku nurtu Niemna.\n"
    "4. Imperium Rosyjskie przystąpiło do blokady kontynentalnej skierowanej przeciwko Wielkiej Brytanii.\n" + I_PF,
    "F, F, P, P", points=2)

add("Deklaracja niepodległości Stanów Zjednoczonych", "pf",
    "Oceń prawdziwość zdań dotyczących Deklaracji niepodległości Stanów Zjednoczonych:\n"
    "1. Do autorów Deklaracji (tzw. Komitetu Pięciu) należeli m.in. Thomas Jefferson i Benjamin Franklin.\n"
    "2. Deklarację ogłoszono 4 lipca 1776 roku w Filadelfii podczas II Kongresu Kontynentalnego.\n"
    "3. Największy wpływ na treść Deklaracji miały poglądy Monteskiusza.\n"
    "4. Pierwszą część dokumentu stanowią podpisy przedstawicieli 13 kolonii.\n" + I_PF,
    "P, P, F, F", points=2)

add("Sejm niemy", "pf",
    "Oceń prawdziwość zdań dotyczących sejmu niemego:\n"
    "1. Sejm niemy odbył się za panowania króla Augusta II Mocnego.\n"
    "2. Sejm niemy obradował przez sześć tygodni.\n"
    "3. Sejm niemy zwiększył władzę hetmanów.\n"
    "4. W wyniku sejmu niemego wojska rosyjskie pozostały w Rzeczypospolitej na stałe, bez zobowiązania do ich wyprowadzenia.\n" + I_PF,
    "P, F, F, F", points=2)

add("Rozejm andruszowski", "pf",
    "Oceń prawdziwość zdań dotyczących rozejmu andruszowskiego (1667):\n"
    "1. Na mocy rozejmu Rzeczpospolita utraciła na rzecz Rosji Inflanty Polskie.\n"
    "2. Wielkie Księstwo Litewskie zrezygnowało z województwa smoleńskiego.\n"
    "3. Zaporoże zostało uznane za kondominium Polski i Rosji.\n" + I_PF,
    "F, P, P", points=2)

# ===================== CHRONO =====================
add("Powstanie Chmielnickiego", "chrono",
    "Poniżej wymieniono wydarzenia związane z powstaniem Chmielnickiego:\n"
    "A. zawarcie ugody zborowskiej\n"
    "B. zawarcie przez Chmielnickiego w Perejasławiu unii o włączeniu lewobrzeżnej Ukrainy do Rosji\n"
    "C. bitwa pod Korsuniem\n"
    "D. zawarcie porozumienia w Białej Cerkwi, po bitwie pod Beresteczkiem\n" + I_CHRONO,
    "C, A, D, B", points=2)

add("Potop szwedzki", "chrono",
    "Poniżej wymieniono wydarzenia potopu szwedzkiego:\n"
    "A. śluby lwowskie Jana Kazimierza\n"
    "B. zerwanie unii z Koroną przez Janusza Radziwiłła w Kiejdanach\n"
    "C. kapitulacja pospolitego ruszenia wielkopolskiego pod Ujściem\n"
    "D. zawiązanie konfederacji tyszowieckiej\n" + I_CHRONO,
    "C, B, D, A", points=2)

add("III wojna północna", "chrono",
    "Poniżej wymieniono wydarzenia III wojny północnej (wielkiej wojny północnej):\n"
    "A. zawiązanie przez zwolenników Augusta II konfederacji sandomierskiej\n"
    "B. podpisanie przez Saksonię pokoju w Altranstädt\n"
    "C. zwycięstwo Karola XII nad Rosjanami pod Narwą\n"
    "D. pokonanie armii polsko-saskiej przez Szwedów pod Kliszowem\n" + I_CHRONO,
    "C, D, A, B", points=2)

add("Insurekcja kościuszkowska", "chrono",
    "Poniżej wymieniono wydarzenia insurekcji kościuszkowskiej:\n"
    "A. bitwa pod Maciejowicami\n"
    "B. bitwa pod Szczekocinami\n"
    "C. wydanie przez Kościuszkę uniwersału połanieckiego\n"
    "D. wybuch insurekcji warszawskiej pod wodzą Jana Kilińskiego\n" + I_CHRONO,
    "D, C, B, A", points=2)

add("Stanisław August Poniatowski", "chrono",
    "Poniżej wymieniono wydarzenia z czasów panowania Stanisława Augusta Poniatowskiego:\n"
    "A. powołanie Komisji Edukacji Narodowej\n"
    "B. założenie przez króla Szkoły Rycerskiej\n"
    "C. rozpoczęcie organizowania przez króla „obiadów czwartkowych”\n"
    "D. zawiązanie konfederacji barskiej\n" + I_CHRONO,
    "B, D, C, A", points=2)

add("Księstwo Warszawskie", "chrono",
    "Poniżej wymieniono wydarzenia związane z powstaniem i dziejami Księstwa Warszawskiego:\n"
    "A. utworzenie tymczasowego rządu ogólnokrajowego – Komisji Rządzącej\n"
    "B. zawarcie pokoju w Schönbrunnie, na mocy którego Księstwo powiększyło się o ziemie zaboru austriackiego\n"
    "C. zajęcie Warszawy przez armię francuską\n"
    "D. rozbicie armii pruskiej w bitwach pod Jeną i Auerstedt\n" + I_CHRONO,
    "D, C, A, B", points=2)

add("Konfederacja barska", "chrono",
    "Poniżej wymieniono wydarzenia poprzedzające i rozpoczynające konfederację barską:\n"
    "A. zawiązanie przez posła Nikołaja Repnina konfederacji różnowierczych: słuckiej i toruńskiej\n"
    "B. podpisanie przez Rzeczpospolitą traktatu wieczystej przyjaźni z Rosją\n"
    "C. porwanie przez Repnina przywódców konfederacji radomskiej, m.in. biskupa Kajetana Sołtyka\n"
    "D. zawiązanie konfederacji generalnej w Barze\n" + I_CHRONO,
    "A, C, B, D", points=2)

add("Rewolucja francuska", "chrono",
    "Poniżej wymieniono wydarzenia rewolucji francuskiej:\n"
    "A. przewrót termidoriański i stracenie Robespierre’a\n"
    "B. marsz kobiet na Wersal\n"
    "C. rozpoczęcie procesu Ludwika XVI przed Konwentem\n"
    "D. zamach stanu Napoleona Bonapartego (18 brumaire’a)\n" + I_CHRONO,
    "B, C, A, D", points=2)

# ===================== MATCH =====================
add("Wojna trzydziestoletnia", "match",
    "Dopasuj okres wojny trzydziestoletniej (według tradycyjnej periodyzacji) do lat jego trwania.\n"
    "1. 1618–1624\n2. 1624–1630\n3. 1630–1636\n4. 1636–1648\n"
    "A. okres szwedzki\nB. okres francusko-szwedzki\nC. okres czesko-palatynacki\nD. okres duński\n"
    "Odpowiedz w formacie: 1-B, 2-A, 3-D, 4-C.",
    "1-C, 2-D, 3-A, 4-B", points=2)

add("Bitwa pod Kłuszynem", "match",
    "Dopasuj postać do roli, jaką odegrała w bitwie pod Kłuszynem (4 lipca 1610).\n"
    "1. Stanisław Żółkiewski\n2. Dymitr Szujski\n3. Jakub Pontusson De la Gardie\n4. Grzegorz (Hrehory) Wałujew\n"
    "A. kniaź dowodzący armią moskiewską\n"
    "B. hetman polny koronny, dowódca wojsk polskich\n"
    "C. dowódca zablokowanej w Carowym Zamieściu armii, która skapitulowała po bitwie\n"
    "D. dowódca posiłków szwedzkich (wojsk cudzoziemskich)\n"
    "Odpowiedz w formacie: 1-C, 2-A, 3-D, 4-B.",
    "1-B, 2-A, 3-D, 4-C", points=2)

add("Sejm Czteroletni", "match",
    "Dopasuj stronnictwo działające w czasie Sejmu Czteroletniego do postaci, która mu przewodziła lub wokół której się skupiało.\n"
    "1. stronnictwo dworskie (królewskie)\n2. stronnictwo magnacko-republikanckie\n3. stronnictwo hetmańskie\n4. radykalna frakcja Stronnictwa Patriotycznego\n"
    "A. Franciszek Ksawery Branicki\nB. Hugo Kołłątaj\nC. Stanisław Szczęsny Potocki\nD. Stanisław August Poniatowski\n"
    "Odpowiedz w formacie: 1-B, 2-A, 3-C, 4-D.",
    "1-D, 2-C, 3-A, 4-B", points=2)

add("III rozbiór Polski", "match",
    "Dopasuj państwo zaborcze do ziem, które zajęło w III rozbiorze Polski (1795).\n"
    "1. Austria\n2. Prusy\n3. Rosja\n"
    "A. ziemie na wschód od Niemna i Bugu\n"
    "B. Lubelszczyzna, reszta Małopolski z Krakowem, Chełmszczyzna\n"
    "C. część Mazowsza z Warszawą, część Podlasia, Suwalszczyzna i Kowieńszczyzna\n"
    "Odpowiedz w formacie: 1-A, 2-B, 3-C.",
    "1-B, 2-C, 3-A", points=2)

add("Rewolucja francuska", "match",
    "Dopasuj datę do wydarzenia rewolucji francuskiej.\n"
    "1. 20 czerwca 1789\n2. 14 lipca 1789\n3. 26 sierpnia 1789\n4. 17 stycznia 1793\n"
    "A. skazanie Ludwika XVI na karę śmierci\n"
    "B. przyjęcie przez Konstytuantę Deklaracji praw człowieka i obywatela\n"
    "C. zdobycie Bastylii\n"
    "D. przysięga deputowanych Stanów Generalnych w sali do gry w piłkę\n"
    "Odpowiedz w formacie: 1-B, 2-A, 3-C, 4-D.",
    "1-D, 2-C, 3-B, 4-A", points=2)

add("Pokój westfalski", "match",
    "Dopasuj państwo do tego, co uzyskało na mocy pokoju westfalskiego (1648).\n"
    "1. Królestwo Szwecji\n2. margrabia-elektor Brandenburgii\n3. Królestwo Francji\n4. Związek Szwajcarski\n"
    "A. Pomorze Przednie, wyspę Rugię i arcybiskupstwo Bremy\n"
    "B. Górną i Dolną Alzację oraz tzw. trzy biskupstwa (Metz, Toul, Verdun)\n"
    "C. uznanie niepodległości i pełnej suwerenności przez Święte Cesarstwo Rzymskie\n"
    "D. Pomorze Tylne, biskupstwo kamieńskie i arcybiskupstwo magdeburskie\n"
    "Odpowiedz w formacie: 1-B, 2-C, 3-D, 4-A.",
    "1-A, 2-D, 3-B, 4-C", points=2)

# ===================== OPEN =====================
add("I rozbiór Polski", "open",
    "Który poseł – obok Samuela Korsaka i Stanisława Bohuszewicza – protestował na Sejmie Rozbiorowym w 1773 roku przeciwko ratyfikacji traktatów I rozbioru Polski? Podaj imię i nazwisko. " + I_OPEN,
    "Tadeusz Reytan", ["Reytan", "Rejtan", "Tadeusz Rejtan"])

add("Wojna polsko-rosyjska (1792)", "open",
    "Jakie odznaczenie – najwyższe polskie odznaczenie wojenne – ustanowił król Stanisław August Poniatowski 22 czerwca 1792 roku dla uczczenia zwycięstwa pod Zieleńcami? " + I_OPEN,
    "Order Virtuti Militari", ["Virtuti Militari", "order Virtuti Militari", "Krzyż Virtuti Militari"])

add("Wojna trzydziestoletnia", "open",
    "Jak nazywa się wydarzenie z 23 maja 1618 roku, gdy na zamku na Hradczanach protestanccy delegaci czescy wyrzucili przez okno katolickich przedstawicieli cesarskich, co stało się bezpośrednią przyczyną wojny trzydziestoletniej? " + I_OPEN,
    "defenestracja praska", ["defenestracja", "druga defenestracja praska", "II defenestracja praska"])

add("Kodeks Napoleona", "open",
    "Pod jaką nazwą uchwalono 21 marca 1804 roku zbiór przepisów prawa cywilnego, przemianowany w 1807 roku na Kodeks Napoleona? " + I_OPEN,
    "Kodeks cywilny Francuzów", ["Code civil des Français", "Kodeks cywilny", "Code civil"])
