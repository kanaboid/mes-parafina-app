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

## 2. Uptime Kuma (oczyszczalnia-aio)

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
3. Skopiuj URL Push do `.env` na **terminal3**:

```env
UPTIME_KUMA_BACKUP_PUSH_URL=http://oczyszczalnia-aio:3001/api/push/TWOJ_TOKEN?status=up&msg=ok&ping=
```

`backup-mes.sh` wyśle ping automatycznie po udanym backupie.

**Push — replikacja (terminal1):**

1. Nowy monitor Push, interwał **300** s, grace **120** s.
2. W `.env` na **terminal1**:

```env
UPTIME_KUMA_REPLICATION_PUSH_URL=http://oczyszczalnia-aio:3001/api/push/TWOJ_TOKEN?status=up&msg=ok&ping=
```

Cron na terminal1:

```cron
*/5 * * * * /home/terminal1/mes-parafina-app/scripts/mysql-replication-healthcheck.sh >> /home/terminal1/mes-replication-health.log 2>&1
```

### Powiadomienia

W Kuma: **Settings → Notifications** — e-mail, Telegram lub inny kanał. Przypisz do wszystkich monitorów.

Stary `monitor-primary.sh` możesz **wyłączyć z crona** — te same checki robi Kuma z alertami.

---

## 3. Netdata (wszystkie hosty)

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

## 4. Podsumowanie cronów

| Host | Zadanie | Cron |
|------|---------|------|
| terminal3 | backup + push Kuma | `0 * * * * .../backup-mes.sh` |
| terminal1 | healthcheck replikacji | `*/5 * * * * .../mysql-replication-healthcheck.sh` |
| terminal1 | start DB @reboot | `@reboot .../mysql-replication-start-db.sh` |
| oczyszczalnia-aio | Kuma @reboot | `@reboot sleep 60 && .../monitoring-start.sh kuma` |

---

## 5. Uprawnienia skryptów (bezpieczeństwo)

Zostaw **+x** tylko na skryptach wołanych z crona:

- terminal3: `backup-mes.sh`, `monitoring-kuma-push.sh` (wołany z backupu)
- terminal1: `mysql-replication-healthcheck.sh`, `mysql-replication-start-db.sh`
- oczyszczalnia-aio: `monitoring-start.sh`

Reszta: `chmod -x` i uruchamianie przez `bash scripts/...`.

---

## 6. Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Kuma nie widzi terminal3 | Ping z oczyszczalnia-aio; DNS/hosts; firewall |
| Push backup — fałszywy alarm | Sprawdź cron backupu; `UPTIME_KUMA_BACKUP_PUSH_URL` w `.env` terminal3 |
| Replikacja Push — alert | `./scripts/mysql-replication-status.sh`; napraw replikację |
| Netdata pusty Docker | Uprawnienia do `/var/run/docker.sock`; restart kontenera |
| Brak miejsca na dysku | Netdata → Disk; wyczyść stare backupy (`KEEP_DAYS`) |

Powiązane: [disaster-recovery.md](disaster-recovery.md), [mysql-replication.md](mysql-replication.md)
