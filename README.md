# GTFS to OSM
Updating OSM data from GTFS timetables. Developed and tested on Prague GTFS data.

## Úvod
Projekt OpenStreetMap (OSM) podporuje mimo jiné i mapování zastávek a linek
veřejné dopravy. Tyto údaje jsou užitečné obzvláště v mobilních navigacích, kde
mohou pomoci například při hledání, od kterého označníku jede hledaná linka. V
rámci malých měst se stabilními linkami lze tyto údaje udržovat poměrně snadno
ručně, Praha má ale linek velké množství a často dochází k výrazným změnám
trasy, tudíž je ruční údržba velmi náročná, což je částečně dáno i neexistencí
vhodných nástrojů pro editaci tras. Proto jsme vyvinuli nástroj, který má s
aktualizací tras linek pomáhat.

## Cíle
Cílem projektu je vyvinout nástroj pro poloautomatickou editaci dat o zastávkách
a trasách linek za pomocí dat z GTFS. Projekt má 2 hlavní části:
 * párování zastávek v GTFS se zastávkami v OSM
 * párování mezizastávkových úseků v GTFS se silnicemi v OSM

V rámci párování zastávek jsme se snažili spárovat pozice zastávek v GTFS s
pozicemi zastávek v OSM a následně doplnit chybějící identifikátory zastávek do
OSM tam, kde chyběly.

Když jsme měli zastávky spárované, za pomoci dat o mezizastávkových úsecích jsme
se snažili najít trasu po silnicích v OSM takovou, která nejvíce odpovídá trase
uvedené v GTFS. Tyto trasy pak lze využít při aktualizacích tras jednotlivých
linek.

## Použité prostředky
Projekt je napsán převážně v Pythonu, při práci s geodaty hojně využívá
PostgreSQL a PostGIS. Vstupy a výstupy jsou předávány jako GeoJSON. 
Pro běh projektu předpokládáme, že uživatel má databázi `cz_osm` s importovanými
daty alespon pro Prahu pomocí nástroje
[osm-update](https://github.com/xtompok/osm-update), tedy jak spočítané
geometrie, tak syrová data v jedné databázi. Data o MHD lze získat z [pražských
opendat](http://opendata.praha.eu/dataset?q=geojson&organization=ropid),
zajímají nás *Zastávky PID - jednotlivé označníky* a *Trasy*. Tyto dva soubory
je třeba stahovat současně, jinak nebudou správně svázány.

## Popis funkce
### Párování zastávek
#### Data
Data z GTFS obsahují pro každý označník jeho jméno, identifikátor, párovací
číslo do tras, druh dopravního prostředku a pozici (a další informace, které ale
nejsou pro nás důležité). Jméno je řetězec, pod kterým zastávku obvykle známe
(např. *Palmovka*). Identifikátor je jednoznačný řetězec identifikující daný
stojan. Pro označníky je formátu `U<zast>Z<ozn>` kde `<zast>` identifikuje
zastávku (množinu označníků stejného jména) a `<ozn>` identifikuje konkrétní
označník dané zastávky. Tato identifikace je (téměř) neměnná, tudíž je vhodná
pro propojení s OSM. Párovací číslo (`ZAST_ID`) je číslo odkazované ze souboru s
mezizastávkovými úseky. Také jednoznačně identifikuje označník, ale nemá žádnou
sémantiku a mění se s každým nově vygenerovaným souborem, tudíž nemá smysl ho
používat za jiným účelem než párováním s trasami. 

V datech z OSM není úplně jednoznačné, co je to zastávka. Prakticky jsou pro nás
zajímavé dva druhy objektů - nástupiště (`public_transport=platform`) a místo
zastavení (`public_transport=stop_position`) Nástupiště udává místo na chodníku,
ze kterého se nastupuje do vozidla, místo zastavení udává pozici ve vozovce, kde
stojí čelo vozidla. Průzkumem dat z OSM jsme došli k rozhodnutí používat pouze
místa zastavení, protože nástupiště je zakresleno pouze u minima zastávek a
místo zastavení lépe odpovídá našim dalším potřebám. Mluvíme-li dále o zastávce,
je tím myšlen označník respektive místo zastavení, není-li řečeno jinak.

Data z OSM obsahují jméno zastávky, druh dopravního prostředku a pozici, některé
zastávky již měly přiřazen identifikátor, tyto jsme považovali za správně
spárované a při párování jsme je vynechávali.

#### Párovací pravidlo
Zastávky dle GTFS a dle OSM jsou často na velmi odlišných místech, nestačí nám
jednoduché hladové párování, protože často dochází k situacím, kdy se zastávky
spárují *do kříže* přes silnici, což je právě ten případ, který chceme
eliminovat. Data ukazují, že většinou jsou zastávky posunuty podél silnice na
náhodné strany, tudíž první pravidlo bylo, aby byly vektory posunu zastávek co
nejrovnoběžnější. Toto pravidlo nebere v úvahu délku vektorů, v nalezených
párováních se vyskytovaly některé špatné párování právě v důsledku nalezení
extrémě dlouhých, ale téměř rovnoběžných vektorů. Zde se sluší podotknout, že je
potřeba brát v úvahu pouze vzájemný úhel vektorů, nikoli jejich směr, protože se
vyskytují jak zastávky posunuté stejně pro oba směry, tak zastávky, které jsou
posunuty na vzájemně opačné strany. K eliminaci přehnané snahy o rovnoběžnost
jsme pravidlo upravili jako vážený součet úhlu a součtu délek vektorů, což vede
k eliminaci dlouhých hran, ale zároveň respektuje nekřížení silnice. Toto
pravidlo se ukázalo jako dostatečné. Bylo by možné ho vylepšit uvažováním
skutečného průběhu silnic, ale nebylo to potřeba. Uvedené pravidlo také na první
pohled není vhodné pro řešení rozsáhlých uzlů, ale naštěstí tyto uzly mají
většinou polohy z GTFS a z OSM blízké, tudíž zafunguje část pravidla uvažující
celkovou délku párování.

#### Postup párování
Párování zastávek zajišťuje skript `pair-stops.py`. 
Na začátku dostaneme seznam zastávek z OSM a z GTFS. Zastávky rozřadíme do tříd
ekvivalence podle jména a druhu dopravy. Vždy párujeme jen zastávky stejného
jména a druhu dopravy, protože tyto údaje jsou v obou zdrojích dat poměrně
spolehlivé. Před samotným párováním vyřadíme ty dvojice zastávek, které jsou už
dle identifikátoru napárované a pak hrubou silou porovnáme všechny permutace
zastávek z GTFS a OSM a vybereme tu s nejmenší chybou dle výše uvedeného
pravidla. Vzhledem k tomu, že zastávky jednoho jména jsou většinou nejvýše 4 (96
%), maximum je 12 a ještě se dále děli dle druhu dopravy, nemá smysl uvažovat
nad rychlejším algoritmem. Párují se pouze zastávky, které mají pro dané jméno a
druh dopravy stejný počet označníků jako míst zastavení. Pokud počty nesedí,
párování se vynechá, protože to obvykle znamená, že je potřeba nějaký ruční
zásah do OSM, při kterém je možné vyřešit i párování.

Nalezená párování se pak uloží jednak jako zastávky z OSM s doplněnými
identifikátory, jednak jako úsečky spojující napárované zastávky.

### Párování mezizastávkových úseků
#### Data a rozsah práce
ROPID dává k dispozici jednak trasy jednotlivých linek ve formě
MultiLineStringu, jednak LineStringy jednotlivých mezizastávkových úseků s
uvedením linek, které po nich projíždějí, včetně druhu dopravního prostředku.
Protože na většině sítě jezdí v jednom mezizastávkovém úseku více linek, je
efektivnější nalézt odpovídající úseky v datech OSM a pak je případně spojovat
do jednotlivých linek. Každý mezizastávkový úsek ve vstupním souboru navíc
obsahuje párovací číslo počáteční a koncové zastávky, mezi kterými vede.

V datech OSM jsou sice již některé linky zanesené, ale data nejsou dlouhodobě
udržována, tudíž jsme je nepoužívali a odpovídající trasy jsme hledali přímo v
grafu silniční sítě z OSM. Zaměřili jsme se na autobusy, protože tramvaje jsou
jednodušší instancí téhož problému a metro by pro naše potřeby vyžadovalo úpravy
stanic v mapových datech, navíc jeho trasa se příliš často nemění a má poměrně
malý rozsah, tudíž se dá udržovat ručně. 

#### Párovací pravidlo
Abychom uměli najít co nejpodobnější cestu, bylo potřeba si stanovit chybovou
funkci, která nám říká, nakolik se naše nalezená trasa liší od zadané. Lomené
čáry mezizastávkových úseků z dat ROPIDu přibližně odpovídají průběhu silnic v
OSM, ale jsou často zjednodušeny či mírně posunuty. Protože i data silniční sítě
v OSM jsou lomené čáry, stanovili jsme jako chybovou funkci součet vzdáleností
lomových bodů trasy po silnicích od trasy z dat ROPIDu. Tato metrika není
absolutní, dlouhé rovné trasy budou mít na stejné délce menší chybu než krátké
klikaté, ale v rámci porovnávání jednotlivých možných tras poslouží dobře. 

#### Od zastávky k silnici
Ačkoli v datech OSM mluvíme o místu zastavení, které by se mělo nacházet na
lomovém bodu silnice, ne vždy je tomu tak. Ve starším tagovacím schématu se
umísťoval bod zastávky na místo označníku, tudíž mimo cestu a na mnohých
zastávkách tomu tak zůstalo dodnes. Toto umístění má pro uživatele praktickou
výhodu v tom, že v mapě snadno vidí, pro který směr je daný označník určen. V
novém schématu tento problém řeší objekt nástupiště, který ale, jak jsme již
zmínili, se v Praze příliš často nevyskytuje. Pro hledání trasy je tedy potřeba
najít nejprve body na silnici odpovídající zastávkám a pak teprve hledat trasu
po silnici. Pro každou zastávku jsme spočítali vzdálenost k nejbližší silnici a
rozhlédli se, jestli na ní nalezneme lomový bod, který by byl od zastávky
vzdálen nejvýše o 5 metrů více, než je nejkratší vzdálenost. Pokud tomu tak
bylo, použili jsme tento bod jako výchozí respektive cílový. V opačném případě
jsme rozdělili úsek mezi lomovými body a vložili nový bod na průmětu zastávky do
silnice. Tento bod jsme pak použili jako výchozí / cílový.

#### Postup párování
Postupně procházíme jednotlivé mezizastávkové úseky. U každého úseku zjistíme
zastávku na začátku a na konci a k ním odpovídající body na silnici (viz výše).
Mezi těmito body pak hledáme trasu co nejpodobnější trase z dat ROPIDu. K
hledání používáme Dijkstrův algoritmus, ale místo délky hrany používáme jako
metriku vzdálenost koncového bodu od trasy z dat ROPIDu. Při prohledávání rovněž
ořezáváme neperspektivní větve, když celková odchylka je větší než kilometr, z
daného bodu dále neprohledáváme. Dijkstrův algoritmus nám nalezne cestu s
nejmenší odchylkou, tu následně uložíme jako výsledek.

## Implementace
Nebudeme zde rozepisovat detailní implementaci, nastíníme jen základní myšlenky
pro jednotlivé části. 

### Souřadnicový systém
Abychom mohli snadno počítat vzdálenosti, všechna data na začátku převedeme do
EPSG 3857, který má jako jednotku metry.

### Databáze
Pro ukládání většiny mezivýsledků používáme databázi PostgreSQL spolu s
nadstavbou PostGIS. Toto nám umožňuje snadno provazovat data ať už na základě
společných atributů, nebo geometrických vlastností. Protože při zpracování
dochází k velkému množství geometrických výpočtů a data používáme opakovaně,
ukládáme je do *materialized view*, což nám umožní snadno aktualizovat
mezivýsledky při nahrání nových dat z OSM a zároveň vytvářet indexy pro
rychlejší vyhledávání. 

Výpočet vzdáleností silnic od mezizastávkových tras z dat ROPIDu by při počítání
všech kombinací trval příliš dlouho a vedl k zbytečně velkým tabulkám. Protože
víme, že nalezená trasa po silnici bude kopírovat původní trasu v odstupu
nejvýše desítek metrů, stačí nám spočítat vzdálenost k blízkým silnicím. Kolem
tras vytvoříme buffer o velikosti 100 m a vzdálenost silnice k trase počítáme
jen z těch silnic, které se s tímto bufferem protnou. Takto je výpočet rychlý a
ukládáme pouze relevantní data.

### Hledání v grafu
Graf ukládáme jako orientovaný, protože potřebujeme reprezentovat jednosměrky a
při směrově dělených silnicích vést trasu po správné straně. Obousměrné silnice
jsou reprezentovány protisměrnými hranami.

Pro práci s grafem používáme knihovnu NetworkX.

## Výsledky
Popsané algoritmy se ukázaly být funkční a generovaly správná data. Párování
zastávek bude v nejbližších dnech promítnuto do OSM (s ruční kontrolou
správnosti pro zamezení chyb). Použití spárovaných tras pro aktualizaci
linkového vedení v OSM není tak přímočaré, vyžaduje aplikovat dělení silnic u
zastávek a na křižovatkách, kdy lomená čára reprezentující silnici pokračuje,
ale linka se odděluje, tedy je potřeba rozdělit silnici na dvě. Tyto činnosti
budou ještě vyžadovat netriviální množství práce na generování změnového souboru
pro OSM.
