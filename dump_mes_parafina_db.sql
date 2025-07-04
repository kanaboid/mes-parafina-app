-- MySQL dump 10.13  Distrib 8.0.42, for Win64 (x86_64)
--
-- Host: 10.142.237.217    Database: mes_parafina_db
-- ------------------------------------------------------
-- Server version	8.0.42-0ubuntu0.22.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alarmy`
--

DROP TABLE IF EXISTS `alarmy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alarmy` (
  `id` int NOT NULL AUTO_INCREMENT,
  `typ_alarmu` enum('TEMPERATURA','CISNIENIE','POZIOM','SYSTEM') COLLATE utf8mb4_unicode_ci NOT NULL,
  `nazwa_sprzetu` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `wartosc` decimal(10,2) NOT NULL,
  `limit_przekroczenia` decimal(10,2) NOT NULL,
  `czas_wystapienia` datetime NOT NULL,
  `status_alarmu` enum('AKTYWNY','POTWIERDZONY','ZAKONCZONY') COLLATE utf8mb4_unicode_ci DEFAULT 'AKTYWNY',
  `czas_potwierdzenia` datetime DEFAULT NULL,
  `czas_zakonczenia` datetime DEFAULT NULL,
  `komentarz` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=281 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `historia_pomiarow`
--

DROP TABLE IF EXISTS `historia_pomiarow`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `historia_pomiarow` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_sprzetu` int NOT NULL,
  `temperatura` decimal(5,2) DEFAULT NULL,
  `cisnienie` decimal(5,2) DEFAULT NULL,
  `czas_pomiaru` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_historia_sprzet_czas` (`id_sprzetu`,`czas_pomiaru`),
  CONSTRAINT `historia_pomiarow_ibfk_1` FOREIGN KEY (`id_sprzetu`) REFERENCES `sprzet` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=15345 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `log_uzyte_segmenty`
--

DROP TABLE IF EXISTS `log_uzyte_segmenty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `log_uzyte_segmenty` (
  `id_operacji_log` int NOT NULL,
  `id_segmentu` int NOT NULL,
  PRIMARY KEY (`id_operacji_log`,`id_segmentu`),
  KEY `id_segmentu` (`id_segmentu`),
  CONSTRAINT `log_uzyte_segmenty_ibfk_1` FOREIGN KEY (`id_operacji_log`) REFERENCES `operacje_log` (`id`) ON DELETE CASCADE,
  CONSTRAINT `log_uzyte_segmenty_ibfk_2` FOREIGN KEY (`id_segmentu`) REFERENCES `segmenty` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Zapisuje, które segmenty były używane w danej operacji z logu';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `operacje_log`
--

DROP TABLE IF EXISTS `operacje_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operacje_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `typ_operacji` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Np. TRANSFER, DODANIE_ZIEMI, FILTRACJA_KOŁO',
  `id_partii_surowca` int DEFAULT NULL,
  `id_sprzetu_zrodlowego` int DEFAULT NULL,
  `id_sprzetu_docelowego` int DEFAULT NULL,
  `czas_rozpoczecia` datetime NOT NULL,
  `czas_zakonczenia` datetime DEFAULT NULL,
  `ilosc_kg` decimal(10,2) DEFAULT NULL,
  `opis` text COLLATE utf8mb4_unicode_ci,
  `status_operacji` enum('aktywna','zakonczona','przerwana') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'aktywna',
  `punkt_startowy` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `punkt_docelowy` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `id_partii_surowca` (`id_partii_surowca`),
  KEY `id_sprzetu_zrodlowego` (`id_sprzetu_zrodlowego`),
  KEY `id_sprzetu_docelowego` (`id_sprzetu_docelowego`),
  CONSTRAINT `operacje_log_ibfk_1` FOREIGN KEY (`id_partii_surowca`) REFERENCES `partie_surowca` (`id`) ON DELETE SET NULL,
  CONSTRAINT `operacje_log_ibfk_2` FOREIGN KEY (`id_sprzetu_zrodlowego`) REFERENCES `sprzet` (`id`) ON DELETE SET NULL,
  CONSTRAINT `operacje_log_ibfk_3` FOREIGN KEY (`id_sprzetu_docelowego`) REFERENCES `sprzet` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log wszystkich zdarzeń i operacji w procesie';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `operator_temperatures`
--

DROP TABLE IF EXISTS `operator_temperatures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operator_temperatures` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_sprzetu` int NOT NULL,
  `temperatura` decimal(5,2) NOT NULL,
  `czas_ustawienia` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `id_sprzetu` (`id_sprzetu`),
  CONSTRAINT `operator_temperatures_ibfk_1` FOREIGN KEY (`id_sprzetu`) REFERENCES `sprzet` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=134 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `partie_statusy`
--

DROP TABLE IF EXISTS `partie_statusy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `partie_statusy` (
  `id_partii` int NOT NULL,
  `id_statusu` int NOT NULL,
  `data_nadania` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_partii`,`id_statusu`),
  KEY `id_statusu` (`id_statusu`),
  CONSTRAINT `partie_statusy_ibfk_1` FOREIGN KEY (`id_partii`) REFERENCES `partie_surowca` (`id`) ON DELETE CASCADE,
  CONSTRAINT `partie_statusy_ibfk_2` FOREIGN KEY (`id_statusu`) REFERENCES `statusy` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Przypisuje wiele statusów do jednej partii';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `partie_surowca`
--

DROP TABLE IF EXISTS `partie_surowca`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `partie_surowca` (
  `id` int NOT NULL AUTO_INCREMENT,
  `unikalny_kod` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Identyfikator partii, np. T10-20231027-1430-APOLLO',
  `typ_surowca` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `zrodlo_pochodzenia` enum('apollo','cysterna') COLLATE utf8mb4_unicode_ci NOT NULL,
  `waga_poczatkowa_kg` decimal(10,2) NOT NULL,
  `waga_aktualna_kg` decimal(10,2) DEFAULT NULL,
  `data_utworzenia` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `id_sprzetu` int DEFAULT NULL,
  `nazwa_partii` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `rodzaj_surowca` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_aktualnego_sprzetu` int DEFAULT NULL,
  `status_partii` enum('W magazynie brudnym','Surowy w reaktorze','Budowanie placka','Przelewanie','Filtrowanie','Oczekiwanie na ocenę','Do ponownej filtracji','Dobielanie','Gotowy do wysłania','W magazynie czystym') COLLATE utf8mb4_unicode_ci NOT NULL,
  `ilosc_cykli_filtracyjnych` int DEFAULT '0',
  `historia_operacji` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unikalny_kod` (`unikalny_kod`),
  UNIQUE KEY `nazwa_partii` (`nazwa_partii`),
  KEY `id_sprzetu` (`id_sprzetu`),
  CONSTRAINT `partie_surowca_ibfk_1` FOREIGN KEY (`id_sprzetu`) REFERENCES `sprzet` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Każdy wiersz to unikalna partia produkcyjna surowca';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `porty_sprzetu`
--

DROP TABLE IF EXISTS `porty_sprzetu`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `porty_sprzetu` (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_sprzetu` int NOT NULL,
  `nazwa_portu` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `typ_portu` enum('IN','OUT') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_portu` (`nazwa_portu`),
  KEY `id_sprzetu` (`id_sprzetu`),
  CONSTRAINT `porty_sprzetu_ibfk_1` FOREIGN KEY (`id_sprzetu`) REFERENCES `sprzet` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Punkty wejściowe/wyjściowe na sprzęcie (reaktorach, filtrach)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `segmenty`
--

DROP TABLE IF EXISTS `segmenty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `segmenty` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_segmentu` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `id_portu_startowego` int DEFAULT NULL,
  `id_wezla_startowego` int DEFAULT NULL,
  `id_portu_koncowego` int DEFAULT NULL,
  `id_wezla_koncowego` int DEFAULT NULL,
  `id_zaworu` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_segmentu` (`nazwa_segmentu`),
  KEY `id_portu_startowego` (`id_portu_startowego`),
  KEY `id_wezla_startowego` (`id_wezla_startowego`),
  KEY `id_portu_koncowego` (`id_portu_koncowego`),
  KEY `id_wezla_koncowego` (`id_wezla_koncowego`),
  KEY `id_zaworu` (`id_zaworu`),
  CONSTRAINT `segmenty_ibfk_1` FOREIGN KEY (`id_portu_startowego`) REFERENCES `porty_sprzetu` (`id`),
  CONSTRAINT `segmenty_ibfk_2` FOREIGN KEY (`id_wezla_startowego`) REFERENCES `wezly_rurociagu` (`id`),
  CONSTRAINT `segmenty_ibfk_3` FOREIGN KEY (`id_portu_koncowego`) REFERENCES `porty_sprzetu` (`id`),
  CONSTRAINT `segmenty_ibfk_4` FOREIGN KEY (`id_wezla_koncowego`) REFERENCES `wezly_rurociagu` (`id`),
  CONSTRAINT `segmenty_ibfk_5` FOREIGN KEY (`id_zaworu`) REFERENCES `zawory` (`id`),
  CONSTRAINT `chk_end` CHECK (((`id_portu_koncowego` is not null) or (`id_wezla_koncowego` is not null))),
  CONSTRAINT `chk_start` CHECK (((`id_portu_startowego` is not null) or (`id_wezla_startowego` is not null)))
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Definiuje fizyczne połączenia (krawędzie grafu)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sprzet`
--

DROP TABLE IF EXISTS `sprzet`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sprzet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_unikalna` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Np. R1, FZ, B1b, B7c',
  `typ_sprzetu` enum('reaktor','filtr','beczka_brudna','beczka_czysta','apollo') COLLATE utf8mb4_unicode_ci NOT NULL,
  `pojemnosc_kg` decimal(10,2) DEFAULT NULL,
  `stan_sprzetu` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Np. Pusty, W koło, Przelew, Dmuchanie filtra',
  `temperatura_aktualna` decimal(5,2) DEFAULT NULL,
  `cisnienie_aktualne` decimal(5,2) DEFAULT NULL,
  `poziom_aktualny_procent` decimal(5,2) DEFAULT NULL,
  `ostatnia_aktualizacja` datetime DEFAULT NULL,
  `temperatura_max` decimal(5,2) DEFAULT '120.00',
  `cisnienie_max` decimal(5,2) DEFAULT '6.00',
  `id_partii_surowca` int DEFAULT NULL,
  `temperatura_docelowa` decimal(5,2) DEFAULT NULL COMMENT 'Temperatura zadana przez operatora',
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_unikalna` (`nazwa_unikalna`)
) ENGINE=InnoDB AUTO_INCREMENT=70 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista całego sprzętu produkcyjnego i magazynowego';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `statusy`
--

DROP TABLE IF EXISTS `statusy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `statusy` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_statusu` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Np. Surowy, Filtrowany, Dobielony, Wydmuch',
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_statusu` (`nazwa_statusu`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Słownik możliwych statusów partii surowca';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wezly_rurociagu`
--

DROP TABLE IF EXISTS `wezly_rurociagu`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wezly_rurociagu` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_wezla` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_wezla` (`nazwa_wezla`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Punkty łączeniowe w rurociągu (trójniki, kolektory)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `zawory`
--

DROP TABLE IF EXISTS `zawory`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `zawory` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_zaworu` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stan` enum('OTWARTY','ZAMKNIETY') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ZAMKNIETY',
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_zaworu` (`nazwa_zaworu`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista zaworów sterujących przepływem';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'mes_parafina_db'
--

--
-- Dumping routines for database 'mes_parafina_db'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-04 12:16:58
