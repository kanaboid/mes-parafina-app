-- MySQL dump 10.13  Distrib 8.0.42, for Win64 (x86_64)
--
-- Host: 10.200.184.217    Database: mes_parafina_db
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
) ENGINE=InnoDB AUTO_INCREMENT=122 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Punkty wejściowe/wyjściowe na sprzęcie (reaktorach, filtrach)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `porty_sprzetu`
--

LOCK TABLES `porty_sprzetu` WRITE;
/*!40000 ALTER TABLE `porty_sprzetu` DISABLE KEYS */;
INSERT INTO `porty_sprzetu` VALUES (1,1,'R1_IN','IN'),(2,1,'R1_OUT','OUT'),(3,2,'R2_IN','IN'),(4,2,'R2_OUT','OUT'),(5,3,'R3_IN','IN'),(6,3,'R3_OUT','OUT'),(7,4,'R4_IN','IN'),(8,4,'R4_OUT','OUT'),(9,5,'R5_IN','IN'),(10,5,'R5_OUT','OUT'),(11,6,'FZ_IN','IN'),(12,6,'FZ_OUT','OUT'),(13,7,'FN_IN','IN'),(14,7,'FN_OUT','OUT'),(16,10,'R6_IN','IN'),(17,11,'R7_IN','IN'),(18,12,'R8_IN','IN'),(19,13,'R9_IN','IN'),(23,10,'R6_OUT','OUT'),(24,11,'R7_OUT','OUT'),(25,12,'R8_OUT','OUT'),(26,13,'R9_OUT','OUT'),(27,8,'B1b_OUT','OUT'),(28,18,'B2b_OUT','OUT'),(29,19,'B3b_OUT','OUT'),(30,20,'B4b_OUT','OUT'),(31,21,'B5b_OUT','OUT'),(32,22,'B6b_OUT','OUT'),(33,23,'B7b_OUT','OUT'),(34,24,'B8b_OUT','OUT'),(35,25,'B9b_OUT','OUT'),(36,26,'B10b_OUT','OUT'),(43,8,'B1b_IN','IN'),(44,18,'B2b_IN','IN'),(45,19,'B3b_IN','IN'),(46,20,'B4b_IN','IN'),(47,21,'B5b_IN','IN'),(48,22,'B6b_IN','IN'),(49,23,'B7b_IN','IN'),(50,24,'B8b_IN','IN'),(51,25,'B9b_IN','IN'),(52,26,'B10b_IN','IN'),(58,9,'B1c_IN','IN'),(59,28,'B2c_IN','IN'),(60,29,'B3c_IN','IN'),(61,30,'B4c_IN','IN'),(62,31,'B5c_IN','IN'),(63,32,'B6c_IN','IN'),(64,33,'B7c_IN','IN'),(65,34,'B8c_IN','IN'),(66,35,'B9c_IN','IN'),(67,36,'B10c_IN','IN'),(68,37,'B11c_IN','IN'),(69,38,'B12c_IN','IN'),(73,9,'B1c_OUT','OUT'),(74,28,'B2c_OUT','OUT'),(75,29,'B3c_OUT','OUT'),(76,30,'B4c_OUT','OUT'),(77,31,'B5c_OUT','OUT'),(78,32,'B6c_OUT','OUT'),(79,33,'B7c_OUT','OUT'),(80,34,'B8c_OUT','OUT'),(81,35,'B9c_OUT','OUT'),(82,36,'B10c_OUT','OUT'),(83,37,'B11c_OUT','OUT'),(84,38,'B12c_OUT','OUT'),(106,107,'AP1_IN','IN'),(107,107,'AP1_OUT','OUT'),(108,108,'AP2_IN','IN'),(109,108,'AP2_OUT','OUT'),(110,109,'NIEBIESKI_IN','IN'),(111,109,'NIEBIESKI_OUT','OUT'),(112,111,'MAUZER_IN','IN'),(113,111,'MAUZER_OUT','OUT'),(114,112,'B10b_mag_IN','IN'),(115,112,'B10b_mag_OUT','OUT'),(116,113,'B9b_mag_IN','IN'),(117,113,'B9b_mag_OUT','OUT'),(118,110,'CYSTERNA_B1b_IN','IN'),(119,110,'CYSTERNA_B1b_OUT','OUT'),(120,114,'CYSTERNA_B10b_IN','IN'),(121,114,'CYSTERNA_B10b_OUT','OUT');
/*!40000 ALTER TABLE `porty_sprzetu` ENABLE KEYS */;
UNLOCK TABLES;

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
) ENGINE=InnoDB AUTO_INCREMENT=142 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Definiuje fizyczne połączenia (krawędzie grafu)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `segmenty`
--

LOCK TABLES `segmenty` WRITE;
/*!40000 ALTER TABLE `segmenty` DISABLE KEYS */;
INSERT INTO `segmenty` VALUES (1,'SEGM_R3_OUT_DO_W_R2_R3',6,NULL,NULL,1,1),(2,'SEGM_W_R2_R3_DO_W_R1_R2',NULL,1,NULL,2,2),(3,'SEGM_W_R1_R2_DO_W_R1_FZ',NULL,2,NULL,3,3),(4,'SEGM_R5_OUT_DO_W_R4_R5',10,NULL,NULL,4,4),(5,'SEGM_W_R4_R5_DO_W_R4_FZ',NULL,4,NULL,5,5),(6,'SEGM_W_R1_FZ_DO_W_FZ_IN_MAIN',NULL,3,NULL,6,6),(7,'SEGM_W_R4_FZ_DO_W_FZ_IN_MAIN',NULL,5,NULL,6,7),(8,'SEGM_W_FZ_IN_MAIN_DO_FZ_IN',NULL,6,11,NULL,8),(9,'SEGM_FZ_OUT_DO_W_FZ_OUT_MAIN',12,NULL,NULL,7,9),(10,'SEGM_W_FZ_OUT_MAIN_DO_R1_IN',NULL,7,1,NULL,10),(11,'SEGM_W_FZ_OUT_MAIN_DO_R2_IN',NULL,7,3,NULL,11),(12,'SEGM_W_FZ_OUT_MAIN_DO_R3_IN',NULL,7,5,NULL,12),(13,'SEGM_W_FZ_OUT_MAIN_DO_R4_IN',NULL,7,7,NULL,13),(14,'SEGM_W_FZ_OUT_MAIN_DO_R5_IN',NULL,7,9,NULL,14),(15,'SEGM_FZ_IN_DO_FZ_OUT',11,NULL,12,NULL,15),(16,'SEGM_R2_OUT_DO_W_R1_R2',4,NULL,NULL,2,16),(17,'SEGM_R1_OUT_DO_W_R1_FZ',2,NULL,NULL,3,17),(18,'SEGM_R4_OUT_DO_W_R4_FZ',8,NULL,NULL,5,18),(21,'SEGM_FN_IN_DO_FN_OUT',13,NULL,14,NULL,21),(22,'SEGM_W_R3_R6_R9_W_R3_R2',NULL,13,NULL,1,30),(23,'SEGM_W_R7_R8_W_R8_R9',NULL,11,NULL,10,27),(24,'SEGM_W_R7_FN_W_R7_R8',NULL,10,NULL,9,26),(25,'SEGM_R7_OUT_W_R7_FN',24,NULL,NULL,9,22),(26,'SEGM_R8_OUT_W_R7_R8',25,NULL,NULL,10,23),(27,'SEGM_R9_OUT_W_R8_R9',26,NULL,NULL,11,24),(28,'SEGM_W_R8_R9_W_R3_R6_R9',NULL,11,NULL,13,28),(31,'SEGM_W_R3_R6_R9_W_R5_R6',NULL,13,NULL,15,29),(32,'SEGM_W_R7_FN_FN_IN',NULL,9,13,NULL,25),(33,'SEGM_R6_OUT_W_R5_R6',23,NULL,NULL,15,31),(34,'SEGM_W_R4_R5_W_R5_R6',NULL,4,NULL,15,32),(36,'SEGM_FN_OUT_DO_W_FN_OUT',14,NULL,NULL,8,33),(37,'SEGM_W_FN_OUT_MAIN_DO_R6_IN',NULL,8,16,NULL,34),(38,'SEGM_W_FN_OUT_MAIN_DO_R7_IN',NULL,8,17,NULL,35),(39,'SEGM_W_FN_OUT_MAIN_DO_R8_IN',NULL,8,18,NULL,36),(40,'SEGM_W_FN_OUT_MAIN_DO_R9_IN',NULL,8,19,NULL,37),(48,'SEGM_W_R1_FZ_DO_W_R1_R2',NULL,3,NULL,2,3),(49,'SEGM_W_R1_R2_DO_W_R2_R3',NULL,2,NULL,1,2),(50,'SEGM_W_R4_FZ_DO_W_R4_R5',NULL,5,NULL,4,5),(51,'SEGM_W_R5_R6_DO_W_R4_R5',NULL,15,NULL,4,32),(52,'SEGM_W_R2_R3_DO_W_R3_R6_R9',NULL,1,NULL,13,30),(53,'SEGM_W_R5_R6_DO_W_R3_R6_R9',NULL,15,NULL,13,29),(54,'SEGM_W_R7_FN_DO_W_R7_R8',NULL,9,NULL,10,26),(55,'SEGM_W_R7_R8_DO_W_R8_R9',NULL,10,NULL,11,27),(56,'SEGM_W_R8_R9_DO_W_R3_R6_R9',NULL,13,NULL,11,28),(57,'segm_b1b_out_w_b1b_out',27,NULL,NULL,16,38),(58,'segm_b2b_out_w_b2b_out',28,NULL,NULL,17,39),(59,'segm_b3b_out_w_b3b_out',29,NULL,NULL,18,40),(60,'segm_b4b_out_w_b4b_out',30,NULL,NULL,19,41),(61,'segm_b5b_out_w_b5b_out',31,NULL,NULL,20,42),(62,'segm_b6b_out_w_b6b_out',32,NULL,NULL,21,43),(63,'segm_b7b_out_w_b7b_out',33,NULL,NULL,22,44),(64,'segm_b8b_out_w_b8b_out',34,NULL,NULL,23,45),(65,'segm_w_b1b_in_b1b_in',NULL,24,43,NULL,46),(66,'segm_w_b2b_in_b2b_in',NULL,25,44,NULL,47),(67,'segm_w_b3b_in_b3b_in',NULL,26,45,NULL,48),(68,'segm_w_b4b_in_b4b_in',NULL,27,46,NULL,49),(69,'segm_w_b5b_in_b5b_in',NULL,28,47,NULL,50),(70,'segm_w_b6b_in_b6b_in',NULL,29,48,NULL,51),(71,'segm_w_b7b_in_b7b_in',NULL,30,49,NULL,52),(72,'segm_w_b8b_in_b8b_in',NULL,31,50,NULL,53),(73,'segm_w_b1b_out_w_b2b_out',NULL,16,NULL,17,54),(74,'segm_w_b2b_out_w_b1b_out',NULL,17,NULL,16,54),(75,'segm_w_b2b_out_w_b3b_out',NULL,17,NULL,18,55),(76,'segm_w_b3b_out_w_b2b_out',NULL,18,NULL,17,55),(77,'segm_w_b3b_out_w_b4b_out',NULL,18,NULL,19,56),(78,'segm_w_b4b_out_w_b3b_out',NULL,19,NULL,18,56),(79,'segm_w_b4b_out_w_b5b_out',NULL,19,NULL,20,57),(80,'segm_w_b5b_out_w_b4b_out',NULL,20,NULL,19,57),(81,'segm_w_b5b_out_w_b6b_out',NULL,20,NULL,21,58),(82,'segm_w_b6b_out_w_b5b_out',NULL,21,NULL,20,58),(83,'segm_w_b6b_out_w_b7b_out',NULL,21,NULL,22,59),(84,'segm_w_b7b_out_w_b6b_out',NULL,22,NULL,21,59),(85,'segm_w_b7b_out_w_b8b_out',NULL,22,NULL,23,60),(86,'segm_w_b8b_out_w_b7b_out',NULL,23,NULL,22,60),(87,'segm_w_b8b_in_w_b7b_in',NULL,31,NULL,30,61),(88,'segm_w_b7b_in_w_b8b_in',NULL,30,NULL,31,61),(89,'segm_w_b7b_in_w_b6b_in',NULL,30,NULL,29,62),(90,'segm_w_b6b_in_w_b7b_in',NULL,29,NULL,30,62),(91,'segm_w_b6b_in_w_b5b_in',NULL,29,NULL,28,63),(92,'segm_w_b5b_in_w_b6b_in',NULL,28,NULL,29,63),(93,'segm_w_b5b_in_w_b4b_in',NULL,28,NULL,27,64),(94,'segm_w_b4b_in_w_b5b_in',NULL,27,NULL,28,64),(95,'segm_w_b4b_in_w_b3b_in',NULL,27,NULL,26,65),(96,'segm_w_b3b_in_w_b4b_in',NULL,26,NULL,27,65),(97,'segm_w_b3b_in_w_b2b_in',NULL,26,NULL,25,66),(98,'segm_w_b2b_in_w_b3b_in',NULL,25,NULL,26,66),(99,'segm_w_b2b_in_w_b1b_in',NULL,25,NULL,24,67),(100,'segm_w_b1b_in_w_b2b_in',NULL,24,NULL,25,67),(101,'segm_w_b8b_out_w_p3_down',NULL,23,NULL,34,68),(102,'segm_w_p3_down_w_p3_up',NULL,34,NULL,33,69),(103,'segm_w_p3_down_w_tankowanie',NULL,34,NULL,35,70),(104,'segm_w_p3_up_w_b8b_in',NULL,33,NULL,31,71),(105,'segm_w_tankowanie_r1_in',NULL,35,1,NULL,72),(106,'segm_w_tankowanie_r2_in',NULL,35,3,NULL,73),(107,'segm_w_tankowanie_r3_in',NULL,35,5,NULL,74),(108,'segm_w_tankowanie_r4_in',NULL,35,7,NULL,75),(109,'segm_w_tankowanie_r5_in',NULL,35,9,NULL,76),(110,'segm_w_tankowanie_r6_in',NULL,35,16,NULL,77),(111,'segm_w_tankowanie_r7_in',NULL,35,17,NULL,78),(112,'segm_w_tankowanie_r8_in',NULL,35,18,NULL,79),(113,'segm_w_tankowanie_r9_in',NULL,35,19,NULL,80),(114,'segm_w_b1b_in_w_cysterna_bypass',NULL,24,NULL,32,81),(115,'segm_w_cysterna_bypass_w_b1b_out',NULL,32,NULL,16,82),(116,'segm_b9b_out_w_b9b_out',35,NULL,NULL,52,83),(117,'segm_b10b_out_w_b10b_out',36,NULL,NULL,53,84),(118,'segm_w_b9b_in_b9b_in',NULL,54,51,NULL,85),(119,'segm_w_b10b_in_b10b_in',NULL,55,52,NULL,86),(122,'segm_ap1_out_w_ap1_out',107,NULL,NULL,57,88),(123,'segm_ap2_out_w_ap2_out',109,NULL,NULL,59,90),(128,'segm_w_b9b_out_w_b10b_out',NULL,53,NULL,52,106),(129,'segm_w_b10b_in_w_b9b_in',NULL,55,NULL,54,107),(130,'SEGM_W_R3_R6_R9_W_p3_down',NULL,13,NULL,34,109),(131,'segm_w_ap2_out_w_ap1_out',NULL,59,NULL,57,110),(132,'segm_w_ap1_w_niebieska_out',NULL,57,NULL,68,111),(133,'segm_w_niebieska_out_w_cys_mauzer_out',NULL,68,NULL,69,112),(134,'segm_w_cys_mauzer_out_w_b10b_out',NULL,69,NULL,53,113),(135,'segm_w_b10b_out_w_b9b_out',NULL,53,NULL,52,114),(136,'segm_w_b9b_out_w_p2_down',NULL,52,NULL,70,115),(137,'segm_w_p2_down_w_p2_up',NULL,70,NULL,71,116),(138,'segm_w_p2_up_w_b9b_in',NULL,71,NULL,54,117),(139,'segm_w_b9b_in_w_b10b_in',NULL,54,NULL,55,118),(140,'segm_w_p2_up_w_r3_r6_r9',NULL,71,NULL,13,119),(141,'SEGM_CYSTERNA_B10b_out_w_cyst_mauzer',121,NULL,NULL,69,120);
/*!40000 ALTER TABLE `segmenty` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sprzet`
--

DROP TABLE IF EXISTS `sprzet`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sprzet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_unikalna` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Np. R1, FZ, B1b, B7c',
  `typ_sprzetu` enum('reaktor','filtr','beczka_brudna','beczka_czysta','apollo','magazyn','cysterna','mauzer') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=115 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista całego sprzętu produkcyjnego i magazynowego';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sprzet`
--

LOCK TABLES `sprzet` WRITE;
/*!40000 ALTER TABLE `sprzet` DISABLE KEYS */;
INSERT INTO `sprzet` VALUES (1,'R1','reaktor',9000.00,'Pusty',507.91,1.66,NULL,'2025-07-17 23:59:50',60.00,6.00,NULL,60.00),(2,'R2','reaktor',9000.00,'Zatankowany',507.90,2.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(3,'R3','reaktor',9000.00,'Zatankowany (surowy)',507.89,1.56,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(4,'R4','reaktor',9000.00,'Zatankowany',507.89,0.33,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(5,'R5','reaktor',9000.00,'Zatankowany (surowy)',507.88,1.70,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(6,'FZ','filtr',NULL,'W transferze',60.00,4.72,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(7,'FN','filtr',NULL,'W transferze',60.00,4.50,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(8,'B1b','beczka_brudna',10000.00,'Pełna',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(9,'B1c','beczka_czysta',10000.00,'Pusta',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(10,'R6','reaktor',NULL,'Pusty',507.87,0.06,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(11,'R7','reaktor',NULL,'Zatankowany',507.86,1.15,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(12,'R8','reaktor',NULL,'Zatankowany',507.85,0.18,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(13,'R9','reaktor',NULL,'Zatankowany',507.31,0.16,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,60.00),(14,'Apollo1','apollo',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(18,'B2b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(19,'B3b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(20,'B4b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(21,'B5b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(22,'B6b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(23,'B7b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(24,'B8b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(25,'B9b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(26,'B10b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(27,'Apollo2','apollo',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(28,'B2c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(29,'B3c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(30,'B4c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(31,'B5c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(32,'B6c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(33,'B7c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(34,'B8c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(35,'B9c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(36,'B10c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(37,'B11c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(38,'B12c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(39,'cysterna','',NULL,NULL,50.00,NULL,NULL,'2025-07-03 21:52:37',120.00,6.00,NULL,50.00),(107,'AP1','apollo',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(108,'AP2','apollo',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(109,'NIEBIESKI','beczka_brudna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(110,'CYSTERNA_B1b','cysterna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(111,'MAUZER','mauzer',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(112,'B10b_mag','beczka_brudna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(113,'B9b_mag','beczka_brudna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL),(114,'CYSTERNA_B10b','cysterna',25000.00,'Gotowy',60.00,0.00,NULL,'2025-07-17 23:59:50',120.00,6.00,NULL,NULL);
/*!40000 ALTER TABLE `sprzet` ENABLE KEYS */;
UNLOCK TABLES;

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
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Punkty łączeniowe w rurociągu (trójniki, kolektory)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `wezly_rurociagu`
--

LOCK TABLES `wezly_rurociagu` WRITE;
/*!40000 ALTER TABLE `wezly_rurociagu` DISABLE KEYS */;
INSERT INTO `wezly_rurociagu` VALUES (66,'w_ap_main'),(57,'w_ap1_out'),(59,'w_ap2_out'),(55,'w_b10b_in'),(53,'w_b10b_out'),(24,'w_b1b_in'),(16,'w_b1b_out'),(25,'w_b2b_in'),(17,'w_b2b_out'),(26,'w_b3b_in'),(18,'w_b3b_out'),(27,'w_b4b_in'),(19,'w_b4b_out'),(28,'w_b5b_in'),(20,'w_b5b_out'),(29,'w_b6b_in'),(21,'w_b6b_out'),(30,'w_b7b_in'),(22,'w_b7b_out'),(31,'w_b8b_in'),(23,'w_b8b_out'),(54,'w_b9b_in'),(52,'w_b9b_out'),(69,'w_cys_mauzer_out'),(32,'w_cysterna_bypass'),(65,'w_dolna_magistrala'),(14,'W_FN_IN_MAIN'),(8,'W_FN_OUT_MAIN'),(6,'W_FZ_IN_MAIN'),(7,'W_FZ_OUT_MAIN'),(67,'w_mag_main'),(68,'w_niebieska_out'),(70,'w_p2_down'),(71,'w_p2_up'),(34,'w_p3_down'),(33,'w_p3_up'),(3,'W_R1_FZ'),(2,'W_R1_R2'),(1,'W_R2_R3'),(13,'W_R3_R6_R9'),(5,'W_R4_FZ'),(4,'W_R4_R5'),(15,'W_R5_R6'),(9,'W_R7_FN'),(10,'W_R7_R8'),(11,'W_R8_R9'),(35,'w_tankowanie');
/*!40000 ALTER TABLE `wezly_rurociagu` ENABLE KEYS */;
UNLOCK TABLES;

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
) ENGINE=InnoDB AUTO_INCREMENT=121 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista zaworów sterujących przepływem';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `zawory`
--

LOCK TABLES `zawory` WRITE;
/*!40000 ALTER TABLE `zawory` DISABLE KEYS */;
INSERT INTO `zawory` VALUES (1,'V_R3_OUT_W_R2_R3','ZAMKNIETY'),(2,'V_W_R2_R3_W_R1_R2','ZAMKNIETY'),(3,'V_W_R1_R2_W_R1_FZ','ZAMKNIETY'),(4,'V_R5_OUT_W_R4_R5','ZAMKNIETY'),(5,'V_W_R4_R5_W_R4_FZ','ZAMKNIETY'),(6,'V_W_R1_FZ_W_FZ_IN','ZAMKNIETY'),(7,'V_W_R4_FZ_W_FZ_IN','ZAMKNIETY'),(8,'V_W_FZ_IN_FZ_IN','ZAMKNIETY'),(9,'V_FZ_OUT_W_FZ_OUT','ZAMKNIETY'),(10,'V_W_FZ_OUT_R1_IN','ZAMKNIETY'),(11,'V_W_FZ_OUT_R2_IN','ZAMKNIETY'),(12,'V_W_FZ_OUT_R3_IN','ZAMKNIETY'),(13,'V_W_FZ_OUT_R4_IN','ZAMKNIETY'),(14,'V_W_FZ_OUT_R5_IN','ZAMKNIETY'),(15,'V_FZ_IN_FZ_OUT','ZAMKNIETY'),(16,'V_R2_OUT_W_R1_R2','ZAMKNIETY'),(17,'V_R1_OUT_W_R1_FZ','ZAMKNIETY'),(18,'V_R4_OUT_W_R4_FZ','ZAMKNIETY'),(21,'V_FN_IN_FN_OUT','ZAMKNIETY'),(22,'V_R7_OUT_W_R7_FN','ZAMKNIETY'),(23,'V_R8_OUT_W_R7_R8','ZAMKNIETY'),(24,'V_R9_OUT_W_R8_R9','ZAMKNIETY'),(25,'V_W_R7_FN_FN_IN','ZAMKNIETY'),(26,'V_W_R7_FN_W_R7_R8','ZAMKNIETY'),(27,'V_W_R7_R8_W_R8_R9','ZAMKNIETY'),(28,'V_W_R8_R9_W_R3_R6_R9','ZAMKNIETY'),(29,'V_W_R3_R6_R9_W_R5_R6','ZAMKNIETY'),(30,'V_W_R3_R6_R9_W_R3_R2','ZAMKNIETY'),(31,'V_R6_OUT_W_R5_R6','ZAMKNIETY'),(32,'V_W_R4_R5_W_R5_R6','ZAMKNIETY'),(33,'V_FN_OUT_DO_W_FN_OUT','ZAMKNIETY'),(34,'V_W_FN_OUT_MAIN_DO_R6_IN','ZAMKNIETY'),(35,'V_W_FN_OUT_MAIN_DO_R7_IN','ZAMKNIETY'),(36,'V_W_FN_OUT_MAIN_DO_R8_IN','ZAMKNIETY'),(37,'V_W_FN_OUT_MAIN_DO_R9_IN','ZAMKNIETY'),(38,'v_b1b_out_w_b1b_out','ZAMKNIETY'),(39,'v_b2b_out_w_b2b_out','ZAMKNIETY'),(40,'v_b3b_out_w_b3b_out','ZAMKNIETY'),(41,'v_b4b_out_w_b4b_out','ZAMKNIETY'),(42,'v_b5b_out_w_b5b_out','ZAMKNIETY'),(43,'v_b6b_out_w_b6b_out','ZAMKNIETY'),(44,'v_b7b_out_w_b7b_out','ZAMKNIETY'),(45,'v_b8b_out_w_b8b_out','ZAMKNIETY'),(46,'v_w_b1b_in_b1b_in','ZAMKNIETY'),(47,'v_w_b2b_in_b2b_in','ZAMKNIETY'),(48,'v_w_b3b_in_b3b_in','ZAMKNIETY'),(49,'v_w_b4b_in_b4b_in','ZAMKNIETY'),(50,'v_w_b5b_in_b5b_in','ZAMKNIETY'),(51,'v_w_b6b_in_b6b_in','ZAMKNIETY'),(52,'v_w_b7b_in_b7b_in','ZAMKNIETY'),(53,'v_w_b8b_in_b8b_in','ZAMKNIETY'),(54,'v_w_b1b_out_w_b2b_out','ZAMKNIETY'),(55,'v_w_b2b_out_w_b3b_out','ZAMKNIETY'),(56,'v_w_b3b_out_w_b4b_out','ZAMKNIETY'),(57,'v_w_b4b_out_w_b5b_out','ZAMKNIETY'),(58,'v_w_b5b_out_w_b6b_out','ZAMKNIETY'),(59,'v_w_b6b_out_w_b7b_out','ZAMKNIETY'),(60,'v_w_b7b_out_w_b8b_out','ZAMKNIETY'),(61,'v_w_b8b_in_w_b7b_in','ZAMKNIETY'),(62,'v_w_b7b_in_w_b6b_in','ZAMKNIETY'),(63,'v_w_b6b_in_w_b5b_in','ZAMKNIETY'),(64,'v_w_b5b_in_w_b4b_in','ZAMKNIETY'),(65,'v_w_b4b_in_w_b3b_in','ZAMKNIETY'),(66,'v_w_b3b_in_w_b2b_in','ZAMKNIETY'),(67,'v_w_b2b_in_w_b1b_in','ZAMKNIETY'),(68,'v_w_b8b_out_w_p3_down','ZAMKNIETY'),(69,'v_w_p3_down_w_p3_up','ZAMKNIETY'),(70,'v_w_p3_down_w_tankowanie','ZAMKNIETY'),(71,'v_w_p3_up_w_b8b_in','ZAMKNIETY'),(72,'v_w_tankowanie_r1_in','ZAMKNIETY'),(73,'v_w_tankowanie_r2_in','ZAMKNIETY'),(74,'v_w_tankowanie_r3_in','ZAMKNIETY'),(75,'v_w_tankowanie_r4_in','ZAMKNIETY'),(76,'v_w_tankowanie_r5_in','ZAMKNIETY'),(77,'v_w_tankowanie_r6_in','ZAMKNIETY'),(78,'v_w_tankowanie_r7_in','ZAMKNIETY'),(79,'v_w_tankowanie_r8_in','ZAMKNIETY'),(80,'v_w_tankowanie_r9_in','ZAMKNIETY'),(81,'v_w_b1b_in_w_cysterna_bypass','ZAMKNIETY'),(82,'v_w_cysterna_bypass_w_b1b_out','ZAMKNIETY'),(83,'v_b9b_out_w_b9b_out','ZAMKNIETY'),(84,'v_b10b_out_w_b10b_out','ZAMKNIETY'),(85,'v_w_b9b_in_b9b_in','ZAMKNIETY'),(86,'v_w_b10b_in_b10b_in','ZAMKNIETY'),(87,'v_ap1_in_w_ap1_in','ZAMKNIETY'),(88,'v_w_ap1_out_ap1_out','ZAMKNIETY'),(89,'v_ap2_in_w_ap2_in','ZAMKNIETY'),(90,'v_w_ap2_out_ap2_out','ZAMKNIETY'),(91,'v_niebieski_w_niebieski_main','ZAMKNIETY'),(92,'v_mauzer_w_mauzer_main','ZAMKNIETY'),(93,'v_b10b_mag_w_b10b_mag_main','ZAMKNIETY'),(94,'v_b9b_mag_w_b9b_mag_main','ZAMKNIETY'),(95,'v_cysterna_b1b_w_cysterna_b1b_main','ZAMKNIETY'),(96,'v_w_b8b_out_w_dolna_magistrala','ZAMKNIETY'),(97,'v_w_dolna_magistrala_w_ap_main','ZAMKNIETY'),(98,'v_w_dolna_magistrala_w_mag_main','ZAMKNIETY'),(99,'v_w_ap_main_w_ap1_in','ZAMKNIETY'),(100,'v_w_ap_main_w_ap2_in','ZAMKNIETY'),(101,'v_w_mag_main_w_niebieski_main','ZAMKNIETY'),(102,'v_w_mag_main_w_mauzer_main','ZAMKNIETY'),(103,'v_w_mag_main_w_b10b_mag_main','ZAMKNIETY'),(104,'v_w_mag_main_w_b9b_mag_main','ZAMKNIETY'),(105,'v_w_b8b_out_w_b9b_out','ZAMKNIETY'),(106,'v_w_b9b_out_w_b10b_out','ZAMKNIETY'),(107,'v_w_b10b_in_w_b9b_in','ZAMKNIETY'),(108,'v_w_cysterna_bypass_w_cysterna_b1b_main','ZAMKNIETY'),(109,'v_W_R3_R6_R9_W_p3_down','ZAMKNIETY'),(110,'v_w_ap2_out_w_ap1_out','ZAMKNIETY'),(111,'v_w_ap1_w_niebieska_out','ZAMKNIETY'),(112,'v_w_niebieska_out_w_cys_mauzer_out','ZAMKNIETY'),(113,'v_w_cys_mauzer_out_w_b10b_out','ZAMKNIETY'),(114,'v_w_b10b_out_w_b9b_out','ZAMKNIETY'),(115,'v_w_b9b_out_w_p2_down','ZAMKNIETY'),(116,'v_w_p2_down_w_p2_up','ZAMKNIETY'),(117,'v_w_p2_up_w_b9b_in','ZAMKNIETY'),(118,'v_w_b9b_in_w_b10b_in','ZAMKNIETY'),(119,'v_w_p2_up_w_r3_r6_r9','ZAMKNIETY'),(120,'V_CYSTERNA_B10b_out_w_cyst_mauzer','ZAMKNIETY');
/*!40000 ALTER TABLE `zawory` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-18  0:00:50
