-- Tabela do śledzenia sesji wytapiania w urządzeniach typu 'apollo'
CREATE TABLE apollo_sesje (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_sprzetu INT NOT NULL,
    typ_surowca VARCHAR(255) NOT NULL,
    status_sesji ENUM('aktywna', 'zakonczona') NOT NULL DEFAULT 'aktywna',
    czas_rozpoczecia DATETIME NOT NULL,
    czas_zakonczenia DATETIME NULL,
    rozpoczeta_przez VARCHAR(255),
    uwagi TEXT,
    FOREIGN KEY (id_sprzetu) REFERENCES sprzet(id)
);

-- Tabela do logowania wszystkich zdarzeń w ramach jednej sesji
CREATE TABLE apollo_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_sesji INT NOT NULL,
    typ_zdarzenia ENUM('DODANIE_SUROWCA', 'TRANSFER_WYJSCIOWY', 'KOREKTA_RECZNA') NOT NULL,
    waga_kg DECIMAL(10, 2) NOT NULL,
    czas_zdarzenia DATETIME NOT NULL,
    id_operacji_log INT NULL, -- Powiązanie z głównym logiem operacji w przypadku transferu
    operator VARCHAR(255),
    uwagi TEXT,
    FOREIGN KEY (id_sesji) REFERENCES apollo_sesje(id),
    FOREIGN KEY (id_operacji_log) REFERENCES operacje_log(id)
); 