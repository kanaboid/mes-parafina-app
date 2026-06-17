# Changelog

## [Unreleased]

### Added
- Podstrona **Operacje zbiorniki** (`/operacje-zbiorniki`): kompaktowy widok 67/33 (reaktory i beczki w zakładkach | log aktywnych operacji), bez scrolla strony w układzie ~1920×900, operacje podstawowe (przelewy, kontynuacja/zakończenie etapów, dmuchanie).
- System zmian statusów TankMix po operacjach:
  - Endpoint `POST /api/workflow/mix/<id>/start-filtration` – dedykowany flow filtracji oparty o TankMixes
  - Pathfinder wywoływany na początku startu filtracji (sprawdzenie tras i konfliktów)
  - Automatyczna aktualizacja statusu mieszaniny przy zakończeniu operacji filtracji (`zakoncz_operacje`)
  - Sekwencja statusów: FILTRACJA_PLACEK_KOLO → FILTRACJA_PRZELEW → FILTRACJA_KOLO → OCZEKUJE_NA_OCENE
  - Status FILTRACJA_WYDMUCH dla mieszanin wydmuchowych (po zakończeniu: is_wydmuch_mix=false, filtration_cycles_count += 1)
- Tabela `mix_source_mixes` – łączy mieszaniny w magazynie czystym z mieszaninami produkcyjnymi (P-)
- Status `W_MAGAZYNIE_CZYSTYM` dla mieszanin w beczkach czystych
- Walidacja transferu reaktor → beczka_czysta: tylko dla `process_status = ZATWIERDZONA`
- Prefiks C- dla mieszanin w beczkach czystych przy transferze

### Changed
- Polityka dobielania: mieszaniny wydmuchowe (`is_wydmuch_mix=True`) mogą być dobielane
- Jawne ustawianie `process_status='SUROWY'` przy tworzeniu nowych mieszanin w BatchManagementService

### Added (infrastruktura DR)
- Skrypty backupu i failover: `scripts/backup-mes.sh`, `failover-start.sh`, `failover-stop.sh`
- Replikacja MySQL terminal3 → terminal1 + skrypty `mysql-replication-*.sh`
- Dokumentacja: `docs/disaster-recovery.md`, `docs/mysql-replication.md`
- Compose overrides: `docker-compose.primary.yml`, `docker-compose.standby.yml`, `docker-compose.failover.yml`

### Added (monitoring)
- Uptime Kuma i Netdata: `monitoring/docker-compose.kuma.yml`, `monitoring/docker-compose.netdata.yml`
- Skrypty: `monitoring-start.sh`, `monitoring-kuma-push.sh`, `mysql-replication-healthcheck.sh`
- Integracja push heartbeat w `backup-mes.sh`
- Dokumentacja: `docs/monitoring.md`
