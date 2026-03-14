# Changelog

## [Unreleased]

### Added
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
