-- Tworzenie tabeli typów surowca
CREATE TABLE `typy_surowca` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `opis` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa` (`nazwa`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Słownik typów surowca';

-- Wstawienie podstawowych typów surowca
INSERT INTO `typy_surowca` (`nazwa`, `opis`) VALUES
('T-10', 'Typ surowca T-10'),
('19', 'Typ surowca 19'),
('44', 'Typ surowca 44'),
('GC43', 'Typ surowca GC43'),
('GC42', 'Typ surowca GC42');
