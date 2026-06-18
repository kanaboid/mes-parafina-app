# Monitoring — Uptime Kuma + Netdata

Monitorowanie hostów MES Parafina w LAN:

| Narzędzie | Gdzie | Co robi |
|-----------|-------|---------|
| **Uptime Kuma** | oczyszczalnia-aio | Dostępność HTTP/TCP/ping, alerty, heartbeat cronów |
| **Netdata** | terminal3, terminal1, oczyszczalnia-aio | CPU, RAM, dysk, sieć, kontenery Docker |

```
oczyszczalnia-aio                    terminal3 / terminal1
  Uptime Kuma :3001  ──sprawdza──►   HTTP MES, MySQL :3306, ping
  Netdata :19999                     Netdata :19999 (metryki lokalne)
```

---

## 1. Pliki w repozytorium

| Plik | Opis |
|------|------|
| `monitoring/docker-compose.kuma.yml` | Uptime Kuma |
| `monitoring/docker-compose.netdata.yml` | Netdata (host network) |
| `monitoring/.env.example` | Szablon zmiennych |
| `scripts/monitoring-start.sh` | Uruchomienie Kuma lub Netdata |
| `scripts/monitoring-kuma-push.sh` | Ping do monitora Push |
| `scripts/mysql-replication-healthcheck.sh` | Cron: status replikacji + push |

---

## 2. Instalacja Dockera (oczyszczalnia-aio)

Ten host służył dotąd tylko jako archiwum rsync. Jeśli był tam **Docker Desktop** lub masz problemy z `permission denied` / `docker-credential-desktop` — zrób **czystą reinstalację** (sekcja 2A). Przy pierwszej instalacji wystarczy sekcja 2B.

### 2A. Czysta reinstalacja (usuń wszystko, potem od nowa)

Wykonaj na **oczyszczalnia-aio** jako użytkownik z `sudo`.

**Krok 1 — zatrzymaj usługi**

```bash
sudo systemctl stop docker docker.socket containerd 2>/dev/null || true
```

**Krok 2 — usuń pakiety (Desktop, CE i Ubuntu)**

```bash
sudo apt purge -y \
  docker-desktop docker-ce docker-ce-cli docker-ce-rootless-extras \
  docker-buildx-plugin docker-compose-plugin docker-compose-v2 docker.io \
  containerd containerd.io runc moby-engine moby-cli 2>/dev/null || true

sudo apt autoremove -y --purge
sudo apt autoclean
```

**Krok 3 — usuń repozytoria i stare pliki**

```bash
sudo rm -f /etc/apt/sources.list.d/docker*.list
sudo rm -f /usr/share/keyrings/docker*.gpg /etc/apt/keyrings/docker*.gpg 2>/dev/null || true

rm -rf ~/.docker
sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker

sudo rm -f /usr/local/bin/docker /usr/local/bin/docker-compose /usr/local/bin/com.docker.cli
sudo rm -rf /opt/docker-desktop 2>/dev/null || true
```

**Krok 4 — wyczyść powłokę (bash pamięta starą ścieżkę)**

```bash
grep -n 'docker\|Docker' ~/.bashrc ~/.profile ~/.bash_aliases 2>/dev/null
# usuń lub zakomentuj linie ze ścieżką /usr/local/bin/docker
hash -r
```

**Krok 5 — zrestartuj komputer** (najpewniej odświeża grupy i socket)

```bash
sudo reboot
```

**Krok 6 — świeża instalacja (tylko pakiety Ubuntu, bez Desktop)**

Po ponownym logowaniu:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

> Instaluj **`docker-compose-v2` LUB `docker-compose-plugin`** — **nie oba**. Po czystej reinstalacji wybierz `docker-compose-v2` (prostsze, bez repo Docker CE).

**Krok 7 — zamknij wszystkie sesje użytkownika** (grupa `docker` nie działa w starych sesjach)

```bash
# sprawdź, czy jesteś w grupie (po reboot zwykle tak)
id
# powinno być: groups=...(...,docker,...)

# jeśli nadal brak docker w id — wymuś zamknięcie sesji:
sudo loginctl terminate-user "$USER"
# zaloguj się ponownie (SSH / pulpit)
```

**Krok 8 — weryfikacja**

```bash
which docker                    # /usr/bin/docker
docker compose version
ls -la /var/run/docker.sock     # root docker, prawa srw-rw----
docker ps                       # bez sudo, bez permission denied
```

**Krok 9 — Kuma**

```bash
cd ~/mes-parafina-app
./scripts/monitoring-start.sh kuma
```

---

### 2B. Pierwsza instalacja (bez reinstalacji)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Wyloguj się / zrestartuj, potem `docker ps`. Szczegóły problemów: sekcja 7.

---

## Dwa pliki `.env` — nie pomyl

| Plik | Host | Zawartość |
|------|------|-----------|
| **`~/mes-parafina-app/.env`** | terminal3, terminal1 | Hasła MySQL, `SECRET_KEY`, **`UPTIME_KUMA_*_PUSH_URL`** |
| **`~/mes-parafina-app/monitoring/.env`** | oczyszczalnia-aio (+ Netdata) | `KUMA_PORT`, `MONITORING_HOSTNAME`, Netdata Cloud |

Skrypty `backup-mes.sh` i `mysql-replication-healthcheck.sh` czytają **tylko główny** `.env`.

---

## 3. Uptime Kuma (oczyszczalnia-aio)

```bash
cd ~/mes-parafina-app
git pull
cp monitoring/.env.example monitoring/.env
# w monitoring/.env: MONITORING_HOSTNAME=oczyszczalnia-aio

chmod +x scripts/monitoring-start.sh scripts/monitoring-kuma-push.sh
./scripts/monitoring-start.sh kuma
```

Panel: **http://oczyszczalnia-aio:3001/** — przy pierwszym wejściu utwórz konto admina.

Firewall (tylko LAN):

```bash
sudo ufw allow from 192.168.0.0/16 to any port 3001 proto tcp
# dostosuj podsieć do swojej sieci
```

### Monitory do utworzenia w panelu Kuma

| Nazwa | Typ | Cel | Interwał |
|-------|-----|-----|----------|
| MES produkcja | HTTP(s) | `http://terminal3/` | 60 s |
| MES standby | HTTP(s) | `http://terminal1/` | 300 s |
| MySQL PRIMARY | Port TCP | `terminal3:3306` | 60 s |
| MySQL REPLICA | Port TCP | `terminal1:3306` | 60 s |
| Ping terminal3 | Ping | `terminal3` | 60 s |
| Ping terminal1 | Ping | `terminal1` | 60 s |
| Ping oczyszczalnia-aio | Ping | `oczyszczalnia-aio` | 300 s |
| Backup MES | **Push** | URL z panelu (patrz niżej) | oczekiwany ping co 1 h |
| Replikacja MySQL | **Push** | URL z panelu | oczekiwany ping co 5 min |

**Push — backup (terminal3):**

1. W Kuma: Add Monitor → typ **Push**.
2. Heartbeat Interval: **3600** s (1 h), Grace Period: **600** s.
3. Skopiuj **Push URL** do **głównego** `~/mes-parafina-app/.env` na **terminal3** (nie do `monitoring/.env`).

> **Ważne:** URL **musi być w cudzysłowach** — znak `&` w `.env` bez cudzysłowów psuje wartość przy `source .env`.

```env
UPTIME_KUMA_BACKUP_PUSH_URL="http://oczyszczalnia-aio:3001/api/push/TWOJ_TOKEN"
```

Test ręczny (od razu, bez czekania na cron):

```bash
cd ~/mes-parafina-app
chmod +x scripts/monitoring-kuma-test.sh
./scripts/monitoring-kuma-test.sh backup
```

`backup-mes.sh` wyśle ping automatycznie po udanym backupie (cron co 1 h).

**Push — replikacja (terminal1):**

1. Nowy monitor Push, interwał **300** s, grace **120** s.
2. W **głównym** `~/mes-parafina-app/.env` na **terminal1** (w cudzysłowach):

```env
UPTIME_KUMA_REPLICATION_PUSH_URL="http://oczyszczalnia-aio:3001/api/push/TWOJ_TOKEN"
```

Test:

```bash
./scripts/monitoring-kuma-test.sh replication
```

Cron na terminal1 (bez tego **nie będzie** heartbeat co 5 min):

```cron
*/5 * * * * /home/terminal1/mes-parafina-app/scripts/mysql-replication-healthcheck.sh >> /home/terminal1/mes-replication-health.log 2>&1
```

### Powiadomienia

W Kuma: **Settings → Notifications** — e-mail, Telegram lub inny kanał. Przypisz do wszystkich monitorów.

Stary `monitor-primary.sh` możesz **wyłączyć z crona** — te same checki robi Kuma z alertami.

---

## 4. Netdata (wszystkie hosty)

Na **każdym** hoście (terminal3, terminal1, oczyszczalnia-aio):

```bash
cd ~/mes-parafina-app
git pull
cp monitoring/.env.example monitoring/.env
```

Ustaw w `monitoring/.env` unikalną nazwę:

```env
MONITORING_HOSTNAME=terminal3    # lub terminal1, oczyszczalnia-aio
```

```bash
chmod +x scripts/monitoring-start.sh
./scripts/monitoring-start.sh netdata
```

Panel lokalny: **http://&lt;host&gt;:19999/**

Firewall (opcjonalnie, tylko z LAN):

```bash
sudo ufw allow from 192.168.0.0/16 to any port 19999 proto tcp
```

### Co obserwować w Netdata

- **Disk Space** — miejsce na backupy (`~/mes-backups`)
- **Docker** — kontenery MES (web, db, redis, celery)
- **MySQL** — jeśli widoczne w kontenerach
- **Network** — ruch replikacji / rsync

### Netdata Cloud (opcjonalnie)

Jeden panel dla wszystkich hostów bez otwierania trzech portów 19999:

1. Załóż darmowe konto na [app.netdata.cloud](https://app.netdata.cloud).
2. W `monitoring/.env` na każdym hoście uzupełnij `NETDATA_CLAIM_TOKEN` i `NETDATA_CLAIM_ROOMS` z kreatora.
3. `docker compose -f monitoring/docker-compose.netdata.yml up -d` (restart Netdata).

Bez claim tokena Netdata działa tylko lokalnie na `:19999` — to wystarczy na start.

---

## 5. Podsumowanie cronów

| Host | Zadanie | Cron |
|------|---------|------|
| terminal3 | backup + push Kuma | `0 * * * * .../backup-mes.sh` |
| terminal1 | healthcheck replikacji | `*/5 * * * * .../mysql-replication-healthcheck.sh` |
| terminal1 | start DB @reboot | `@reboot .../mysql-replication-start-db.sh` |
| oczyszczalnia-aio | Kuma @reboot | `@reboot sleep 60 && .../monitoring-start.sh kuma` |

---

## 6. Uprawnienia skryptów (bezpieczeństwo)

Zostaw **+x** tylko na skryptach wołanych z crona:

- terminal3: `backup-mes.sh` (cron; woła push przez `bash scripts/monitoring-kuma-push.sh`)
- terminal1: `mysql-replication-healthcheck.sh`, `mysql-replication-start-db.sh`
- oczyszczalnia-aio: `monitoring-start.sh`

Reszta: `chmod -x` i uruchamianie przez `bash scripts/...`.

---

## 7. Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| `permission denied` na docker.sock | `sudo usermod -aG docker $USER`, **reboot** lub `sudo loginctl terminate-user $USER`; sprawdź `id` i `ls -la /var/run/docker.sock` |
| `docker.sock: no such file` | Sekcja 2B; `sudo systemctl start docker` |
| `/usr/local/bin/docker` nie istnieje | `hash -r`; usuń alias z `.bashrc`; `which docker` → `/usr/bin/docker` |
| `docker-credential-desktop` | Sekcja 2A — czysta reinstalacja lub `printf '{}' > ~/.docker/config.json` |
| Kuma nie widzi terminal3 | Ping z oczyszczalnia-aio; DNS/hosts; firewall |
| Push — brak heartbeat | URL w **głównym** `.env`, nie `monitoring/.env`; cudzysłowy; `monitoring-kuma-test.sh`; cron; firewall na oczyszczalnia-aio |
| Replikacja Push — alert | `./scripts/mysql-replication-status.sh`; napraw replikację |
| Netdata pusty Docker | Uprawnienia do `/var/run/docker.sock`; restart kontenera |
| Brak miejsca na dysku | Netdata → Disk; wyczyść stare backupy (`KEEP_DAYS`) |

Powiązane: [disaster-recovery.md](disaster-recovery.md), [mysql-replication.md](mysql-replication.md)
