# mes-parafina-app

Aplikacja MES do zarządzania produkcją parafiny.

## Dokumentacja operacyjna

- [Odtwarzanie awaryjne (backup, failover)](docs/disaster-recovery.md)
- [Replikacja MySQL terminal3 → terminal1](docs/mysql-replication.md)

## Szybki start (Docker)

```bash
# utwórz .env (patrz docs/disaster-recovery.md)
docker compose up -d
docker compose exec web alembic upgrade head
```

Aplikacja domyślnie: `http://localhost:8080` (port w `docker-compose.yml`).
