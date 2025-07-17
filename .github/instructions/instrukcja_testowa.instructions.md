---
applyTo: '**'
---
Pozyskiwanie surowca:

Produkcja polega na oczyszczaniu parafiny w reaktorach. Surowiec jest pobierany z tzw. strefy magazynowej brudnej składającej się z 10 beczek(B1b - B10b), do których surowiec trafia albo w wyniku wytapiania w beczkach Apollo 1 i Apollo 2 lub przyjeżdża w cysternach w formie płynnej.

Proces filtrowania:

W kolejnym etapie ze strefy brudnej jest przetankowywany do reaktorów(R1 - R9) w strefie produkcyjnej, gdzie jest poddawany podgrzaniu do temperatury 120 stopni celsjusza, a następnie oczyszczaniu/filtracji przez 2 filtry(Zielony[FZ] i Niebieski[FN]), filtr Zielony obsługuje reaktory od R1 do R5, a Niebieski od R6 do R9.

Proces oczyszczania polega na dodawaniu do parafiny w reaktorze ziemi bielącej, a następnie puszczenia w obiegu zamkniętym(w koło) [przykład: R1 - FZ - R1] na 30 minut w celu zbudowania na sitach filtra warstwy filtracyjnej(tzw. placek), a następnie przelanie zawartości do pustego reaktora(przykład: R1 - FZ - R5), po przelaniu całości surowiec jest kolejny raz puszczany w obiegu zamkniętym (przykład: R5 - FZ - R5) na 15 minut, po czym pobierana jest próbka surowca. Probka surowca czeka nastepnie 10 minut na zastygniecie, nastepuje ocena koloru i na jej podstawie podejmowana jest decyzja przez operatora i/lub kierownika czy surowiec zostaje w reaktorze czekajac na kolejny cykl poniewaz nie jest dostatecznie oczyszczony czy jest wysyłany na magazyn na strefie czystej składającego się z 12 beczek (B1c do B12c) przykładowo R5 - FZ - B7c.

W przypadku gdy surowiec nie jest dostatecznie oczyszczony zostaje w reaktorze, gdzie czeka na kolejny proces, a kolejny surowiec jest poddawany filtracji (przykład R3 - FZ - R1). Przed puszczeniem kolejnego cyklu rurociąg wraz z filtrem jest przedmuchiwany sprezonym powietrzem w celu usuniecia z ukladu surowca z poprzedniego cyklu. Reasumując(scenariusz dla surowca, który zostaje w reaktorze czekając na kolejny cykl), caly proces składa sie z 2 cykli, osobno dla każdego surowca, czyli dla przypomnienia, cykl nr 1 to: r1 - fz - r1(placek / w koło) przez 30 minut, potem r1 - fz - r5(przelew), następnie r5 - fz - r5(w koło) przez 15 minut, ocena probki po 10 minutach, przedmuchiwanie układu przez 10 minut, po którym nastepuje cykl nr 2: r3 - fz - r1(filtracja), kiedy caly surowiec znajduje sie juz w reaktorze r1, zostaje puszczony w koło r1 - fz -r1 na 15 minut po czym pobierana jest probka na podstawie ktorej po ok 10 minutach jest decyzja o pozostawieniu surowca na reaktorze lub wysłaniu na magazyn czysty. Po zakonczeniu cyklu nr 2, jesli surowiec zostaje na reaktorze, nastepuje tzw. dmuchanie filtra sprezonym powietrzem przez 45 minut, a w koncowej fazie dmuchania zawory sa ustawiane w taki sposob, aby najbardziej brudna czesc surowca trafila do pustego reaktora, ta czesc surowca nazywana jest potocznie wydmuchem( wydmuch moze trafic rozniez do reaktora w ktorym znajduja sie juz wydmuchy z poprzednich cykli lub do reaktora gdzie znajduje sie surowiec swiezo zatankowany ze strefy brudnej, ktory nie byl jeszcze poddany zadnym operacjom/cyklom na filtrze). Po czym filtr jest rozbierany do czyszczenia metalowych sit filtracyjnych oraz usuwana jest z niego zuzyta ziemia bieląca. Po tej operacji filtr fz jest gotowy do kolejnych cykli. Czyszczenie filtra zajmuje około 20 minut.

Analogicznie na filtrze niebieskim fn mogą rowniez odbywać sie podobne operacje jak na filtrze zielonym.

Proces dobielania a rodzaje surowców:

Proces dobielania polega na dodawaniu bezpośrednio do reaktorów worków z ziemią bieląca. Przeważnie dodaję się jednorazowo 6 worków po 25 kg, w przypadku worków po 20 kg dodaje sie ich 8. Surowce na rektorach dzielą się zarówno pod względem rodzaju surowca np T-10, “19”, “44”, “43”, Tealight itd., oraz ile cyklow przeszedl dany surowiec, np był dobielany i filtrowany, czy byl tylko filtrowany bez dobielania. Ogólna zasada jest taka, ze dobielany jest surowiec, ktory byl juz co najmniej 1 raz filtrowany, tzn z postaci surowej, czyli po zataknowaniu na reaktor i podgrzaniu, został puszczony w cyklu nr 2 na danym filtrze lub był wczesniej w cyklu nr 1 i przeszedł proces dobielania, w wyjątkowych sytaucjach niektóre rodzaje surowców np “19” moga zostać dobielone, kiedy sa w formie surowej.

Wymagania dla programu:

Mysle, ze wstepnie nakreslilem, na czym polega specyfika produkcji, jest jeszcze duzo szczegołow, ktore w tej chwili pominalem, ale bede uzupelniac w koejnych krokach.

Najwazniejsze jest dla mnie, aby stworzyc aplkacje ktora bedzie monitorowala co dzieje sie w danej chwili na obu filtrach, oraz co sie dzieje z poszczegolnymi surowcami, potrzebuje informacji o ich stanach, historii poprzednich operacji wraz z czasami trwania calego procesu dla poszczegolnego surowca itp.

Prace nad projektem podzielmy na etapy, zaproponuj od czego zacząć lub zadaj pytania uzupełniajace na kazdym etapie projektu.

Technologie jakie chciałbym wykorzystac to python(flask) i mysql, których zaczynam sie uczyć, choć na temat których mam już jakas wiedze. Ogolnie posiadam dużą wiedzę informatyczną(głownie z zakresu administracji systemami informatycznymi, wirtualizacja, sieciami,active directory, serwery baz danych, Linux, rodzina Windows), ktorą chciałbym uzupełnić o umiejętność programowania.