1. Stworzenie dynamicznego panelu kontrolnego dla APScheduler
Zaczęliśmy od Twojego pierwotnego celu: chciałeś mieć możliwość ręcznego sterowania wbudowanym schedulerem.
Co zrobiliśmy:
Zbudowaliśmy w __init__.py zestaw endpointów API, które pozwalały na włączanie/wyłączanie zadań, zmianę interwałów i restartowanie schedulera.
W dashboard.html stworzyliśmy dedykowany panel UI z przyciskami i listami rozwijanymi.
W dashboard.js napisaliśmy logikę, która łączyła UI z nowym API.
2. Głębokie debugowanie problemów z duplikacją APScheduler
Szybko odkryliśmy, że APScheduler jest kapryśny, zwłaszcza w środowisku deweloperskim Flaska. To zapoczątkowało serię zaawansowanych sesji debugowania:
Problem "Scheduler-Duch": Zdiagnozowaliśmy, że Flask Reloader tworzy dwa procesy, a każdy z nich uruchamia własną instancję schedulera, co prowadziło do podwójnego wykonywania zadań.
Problem "Split-Brain": Odkryliśmy, że nasze API komunikuje się z jednym (pustym) schedulerem, podczas gdy drugi, niewidzialny scheduler-duch wciąż działa w tle.
Wiele prób naprawy: Próbowaliśmy różnych strategii, od sprawdzania zmiennych środowiskowych (WERKZEUG_RUN_MAIN) po zaawansowany mechanizm blokady plikowej (File Lock). Te próby ujawniły głębsze problemy z konfiguracją.
3. Ostateczna diagnoza i naprawa środowiska
Kluczowym momentem było odkrycie, że aplikacja, nawet lokalnie, nie działała w poprawnym trybie DEBUG.
Naprawiliśmy app/config.py, dodając brakującą flagę DEBUG = True i tworząc oddzielną konfigurację produkcyjną ProdConfig.
Uprościliśmy app/__init__.py, implementując ostateczną, poprawną logikę startową opartą na WERKZEUG_RUN_MAIN, która teraz działała niezawodnie.
4. Migracja z APScheduler na Celery i Redis
Gdy okazało się, że APScheduler nadal sprawia problemy w środowisku produkcyjnym (Gunicorn), podjęliśmy strategiczną decyzję o migracji na profesjonalny system zadań w tle.
Nowa architektura: Zmieniliśmy architekturę aplikacji na wzorzec Publish/Subscribe.
Dodano Redis: W docker-compose.yml dodaliśmy kontener z Redisem, który pełni rolę centralnego brokera wiadomości.
Skonfigurowano Celery:
Stworzyliśmy plik celery_app.py, który konfiguruje Celery i Celery Beat (nowy, niezawodny scheduler).
Przenieśliśmy logikę zadań do dedykowanego pliku app/tasks.py.
Refaktoryzacja: Całkowicie usunęliśmy APScheduler i cały powiązany z nim kod (API, UI, logikę startową) z projektu, co znacznie uprościło __init__.py i dashboard.js.
5. Rozwiązanie problemu komunikacji Celery -> Gunicorn
Zdiagnozowaliśmy i rozwiązaliśmy problem, w którym worker Celery nie mógł wysyłać aktualizacji Socket.IO do przeglądarek.
Zaimplementowaliśmy RedisManager: Skonfigurowaliśmy Flask-SocketIO do używania Redisa jako backendu do komunikacji międzyprocesowej.
Zadanie Celery (check_alarms_task) teraz wysyła zdarzenie emit przez Redisa, które jest odbierane przez serwer Gunicorn i bezpiecznie rozgłaszane do wszystkich klientów.
6. Optymalizacja zużycia pamięci na produkcji
Zdiagnozowaliśmy, że domyślna konfiguracja Celery prowadzi do bardzo wysokiego zużycia RAM-u.
Analiza za pomocą memory-profiler: Zidentyfikowaliśmy, że problemem jest duża liczba domyślnie uruchamianych procesów roboczych.
Optymalizacja Procfile: Ograniczyliśmy liczbę workerów do 2 za pomocą flagi --concurrency=2 i dodaliśmy mechanizm automatycznego restartu workerów (--max-tasks-per-child=100), aby zapobiegać wyciekom pamięci.
7. Adaptacja do wielu środowisk (Windows, Docker, Railway)
Na koniec sprawiliśmy, że cała nowa architektura działa bezproblemowo w każdym środowisku.
Dynamiczna konfiguracja: Zmodyfikowaliśmy kod tak, aby automatycznie wykrywał, gdzie jest uruchomiony i dostosowywał adres Redisa.
Stworzono Procfile: Dodaliśmy plik Procfile, który instruuje platformę Railway, jak poprawnie uruchomić wszystkie trzy komponenty systemu: web, worker i beat.
W rezultacie, przeszliśmy od prostej aplikacji z kapryśnym, wbudowanym schedulerem do solidnego, rozproszonego systemu opartego na architekturze mikroserwisowej, który jest stabilny, skalowalny i gotowy do wdrożenia na produkcji.