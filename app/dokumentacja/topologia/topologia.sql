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
-- Table structure for table `segmenty`
--

DROP TABLE IF EXISTS `segmenty`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `segmenty` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nazwa_segmentu` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=240 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Definiuje fizyczne połączenia (krawędzie grafu)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `segmenty`
--

LOCK TABLES `segmenty` WRITE;
/*!40000 ALTER TABLE `segmenty` DISABLE KEYS */;
INSERT INTO `segmenty` VALUES (1,'SEGM_R3_OUT_DO_W_R2_R3',6,NULL,NULL,1,1),(2,'SEGM_W_R2_R3_DO_W_R1_R2',NULL,1,NULL,2,2),(3,'SEGM_W_R1_R2_DO_W_R1_FZ',NULL,2,NULL,3,3),(4,'SEGM_R5_OUT_DO_W_R4_R5',10,NULL,NULL,4,4),(5,'SEGM_W_R4_R5_DO_W_R4_FZ',NULL,4,NULL,5,5),(6,'SEGM_W_R1_FZ_DO_W_FZ_IN_MAIN',NULL,3,NULL,6,6),(7,'SEGM_W_R4_FZ_DO_W_FZ_IN_MAIN',NULL,5,NULL,6,7),(8,'SEGM_W_FZ_IN_MAIN_DO_FZ_IN',NULL,6,11,NULL,8),(9,'SEGM_FZ_OUT_DO_W_FZ_OUT_MAIN',12,NULL,NULL,7,9),(10,'SEGM_W_FZ_OUT_MAIN_DO_R1_IN',NULL,7,1,NULL,10),(11,'SEGM_W_FZ_OUT_MAIN_DO_R2_IN',NULL,7,3,NULL,11),(12,'SEGM_W_FZ_OUT_MAIN_DO_R3_IN',NULL,7,5,NULL,12),(13,'SEGM_W_FZ_OUT_MAIN_DO_R4_IN',NULL,7,7,NULL,13),(14,'SEGM_W_FZ_OUT_MAIN_DO_R5_IN',NULL,7,9,NULL,14),(15,'SEGM_FZ_IN_DO_FZ_OUT',11,NULL,12,NULL,15),(16,'SEGM_R2_OUT_DO_W_R1_R2',4,NULL,NULL,2,16),(17,'SEGM_R1_OUT_DO_W_R1_FZ',2,NULL,NULL,3,17),(18,'SEGM_R4_OUT_DO_W_R4_FZ',8,NULL,NULL,5,18),(21,'SEGM_FN_IN_DO_FN_OUT',13,NULL,14,NULL,21),(22,'SEGM_W_R3_R6_R9_W_R3_R2',NULL,13,NULL,1,30),(23,'SEGM_W_R7_R8_W_R8_R9',NULL,11,NULL,10,27),(24,'SEGM_W_R7_FN_W_R7_R8',NULL,10,NULL,9,26),(25,'SEGM_R7_OUT_W_R7_FN',24,NULL,NULL,9,22),(26,'SEGM_R8_OUT_W_R7_R8',25,NULL,NULL,10,23),(27,'SEGM_R9_OUT_W_R8_R9',26,NULL,NULL,11,24),(28,'SEGM_W_R8_R9_W_R3_R6_R9',NULL,11,NULL,13,28),(31,'SEGM_W_R3_R6_R9_W_R5_R6',NULL,13,NULL,15,29),(32,'SEGM_W_R7_FN_FN_IN',NULL,9,13,NULL,25),(33,'SEGM_R6_OUT_W_R5_R6',23,NULL,NULL,15,31),(34,'SEGM_W_R4_R5_W_R5_R6',NULL,4,NULL,15,32),(36,'SEGM_FN_OUT_DO_W_FN_OUT',14,NULL,NULL,8,33),(37,'SEGM_W_FN_OUT_MAIN_DO_R6_IN',NULL,8,16,NULL,34),(38,'SEGM_W_FN_OUT_MAIN_DO_R7_IN',NULL,8,17,NULL,35),(39,'SEGM_W_FN_OUT_MAIN_DO_R8_IN',NULL,8,18,NULL,36),(40,'SEGM_W_FN_OUT_MAIN_DO_R9_IN',NULL,8,19,NULL,37),(48,'SEGM_W_R1_FZ_DO_W_R1_R2',NULL,3,NULL,2,3),(49,'SEGM_W_R1_R2_DO_W_R2_R3',NULL,2,NULL,1,2),(50,'SEGM_W_R4_FZ_DO_W_R4_R5',NULL,5,NULL,4,5),(51,'SEGM_W_R5_R6_DO_W_R4_R5',NULL,15,NULL,4,32),(52,'SEGM_W_R2_R3_DO_W_R3_R6_R9',NULL,1,NULL,13,30),(53,'SEGM_W_R5_R6_DO_W_R3_R6_R9',NULL,15,NULL,13,29),(54,'SEGM_W_R7_FN_DO_W_R7_R8',NULL,9,NULL,10,26),(55,'SEGM_W_R7_R8_DO_W_R8_R9',NULL,10,NULL,11,27),(56,'SEGM_W_R8_R9_DO_W_R3_R6_R9',NULL,13,NULL,11,28),(57,'segm_b1b_out_w_b1b_out',27,NULL,NULL,16,38),(58,'segm_b2b_out_w_b2b_out',28,NULL,NULL,17,39),(59,'segm_b3b_out_w_b3b_out',29,NULL,NULL,18,40),(60,'segm_b4b_out_w_b4b_out',30,NULL,NULL,19,41),(61,'segm_b5b_out_w_b5b_out',31,NULL,NULL,20,42),(62,'segm_b6b_out_w_b6b_out',32,NULL,NULL,21,43),(63,'segm_b7b_out_w_b7b_out',33,NULL,NULL,22,44),(64,'segm_b8b_out_w_b8b_out',34,NULL,NULL,23,45),(65,'segm_w_b1b_in_b1b_in',NULL,24,43,NULL,46),(66,'segm_w_b2b_in_b2b_in',NULL,25,44,NULL,47),(67,'segm_w_b3b_in_b3b_in',NULL,26,45,NULL,48),(68,'segm_w_b4b_in_b4b_in',NULL,27,46,NULL,49),(69,'segm_w_b5b_in_b5b_in',NULL,28,47,NULL,50),(70,'segm_w_b6b_in_b6b_in',NULL,29,48,NULL,51),(71,'segm_w_b7b_in_b7b_in',NULL,30,49,NULL,52),(72,'segm_w_b8b_in_b8b_in',NULL,31,50,NULL,53),(73,'segm_w_b1b_out_w_b2b_out',NULL,16,NULL,17,54),(74,'segm_w_b2b_out_w_b1b_out',NULL,17,NULL,16,54),(75,'segm_w_b2b_out_w_b3b_out',NULL,17,NULL,18,55),(76,'segm_w_b3b_out_w_b2b_out',NULL,18,NULL,17,55),(77,'segm_w_b3b_out_w_b4b_out',NULL,18,NULL,19,56),(78,'segm_w_b4b_out_w_b3b_out',NULL,19,NULL,18,56),(79,'segm_w_b4b_out_w_b5b_out',NULL,19,NULL,20,57),(80,'segm_w_b5b_out_w_b4b_out',NULL,20,NULL,19,57),(81,'segm_w_b5b_out_w_b6b_out',NULL,20,NULL,21,58),(82,'segm_w_b6b_out_w_b5b_out',NULL,21,NULL,20,58),(83,'segm_w_b6b_out_w_b7b_out',NULL,21,NULL,22,59),(84,'segm_w_b7b_out_w_b6b_out',NULL,22,NULL,21,59),(85,'segm_w_b7b_out_w_b8b_out',NULL,22,NULL,23,60),(86,'segm_w_b8b_out_w_b7b_out',NULL,23,NULL,22,60),(87,'segm_w_b8b_in_w_b7b_in',NULL,31,NULL,30,61),(88,'segm_w_b7b_in_w_b8b_in',NULL,30,NULL,31,61),(89,'segm_w_b7b_in_w_b6b_in',NULL,30,NULL,29,62),(90,'segm_w_b6b_in_w_b7b_in',NULL,29,NULL,30,62),(91,'segm_w_b6b_in_w_b5b_in',NULL,29,NULL,28,63),(92,'segm_w_b5b_in_w_b6b_in',NULL,28,NULL,29,63),(93,'segm_w_b5b_in_w_b4b_in',NULL,28,NULL,27,64),(94,'segm_w_b4b_in_w_b5b_in',NULL,27,NULL,28,64),(95,'segm_w_b4b_in_w_b3b_in',NULL,27,NULL,26,65),(96,'segm_w_b3b_in_w_b4b_in',NULL,26,NULL,27,65),(97,'segm_w_b3b_in_w_b2b_in',NULL,26,NULL,25,66),(98,'segm_w_b2b_in_w_b3b_in',NULL,25,NULL,26,66),(99,'segm_w_b2b_in_w_b1b_in',NULL,25,NULL,24,67),(100,'segm_w_b1b_in_w_b2b_in',NULL,24,NULL,25,67),(101,'segm_w_b8b_out_w_p3_down',NULL,23,NULL,34,68),(102,'segm_w_p3_down_w_p3_up',NULL,34,NULL,33,69),(103,'segm_w_p3_down_w_tankowanie',NULL,34,NULL,35,70),(104,'segm_w_p3_up_w_b8b_in',NULL,33,NULL,31,71),(105,'segm_w_tankowanie_r1_in',NULL,35,1,NULL,72),(106,'segm_w_tankowanie_r2_in',NULL,35,3,NULL,73),(107,'segm_w_tankowanie_r3_in',NULL,35,5,NULL,74),(108,'segm_w_tankowanie_r4_in',NULL,35,7,NULL,75),(109,'segm_w_tankowanie_r5_in',NULL,35,9,NULL,76),(110,'segm_w_tankowanie_r6_in',NULL,35,16,NULL,77),(111,'segm_w_tankowanie_r7_in',NULL,35,17,NULL,78),(112,'segm_w_tankowanie_r8_in',NULL,35,18,NULL,79),(113,'segm_w_tankowanie_r9_in',NULL,35,19,NULL,80),(114,'segm_w_b1b_in_w_cysterna_bypass',NULL,24,NULL,32,81),(115,'segm_w_cysterna_bypass_w_b1b_out',NULL,32,NULL,16,82),(116,'segm_b9b_out_w_b9b_out',35,NULL,NULL,52,83),(117,'segm_b10b_out_w_b10b_out',36,NULL,NULL,53,84),(118,'segm_w_b9b_in_b9b_in',NULL,54,51,NULL,85),(119,'segm_w_b10b_in_b10b_in',NULL,55,52,NULL,86),(122,'segm_ap1_out_w_ap1_out',107,NULL,NULL,57,88),(123,'segm_ap2_out_w_ap2_out',109,NULL,NULL,59,90),(128,'segm_w_b9b_out_w_b10b_out',NULL,53,NULL,52,106),(129,'segm_w_b10b_in_w_b9b_in',NULL,55,NULL,54,107),(130,'SEGM_W_R3_R6_R9_W_p3_down',NULL,13,NULL,34,109),(131,'segm_w_ap2_out_w_ap1_out',NULL,59,NULL,57,110),(132,'segm_w_ap1_w_niebieska_out',NULL,57,NULL,68,111),(133,'segm_w_niebieska_out_w_cys_mauzer_out',NULL,68,NULL,69,112),(134,'segm_w_cys_mauzer_out_w_b10b_out',NULL,69,NULL,53,113),(135,'segm_w_b10b_out_w_b9b_out',NULL,53,NULL,52,114),(136,'segm_w_b9b_out_w_p2_down',NULL,52,NULL,70,115),(137,'segm_w_p2_down_w_p2_up',NULL,70,NULL,71,116),(138,'segm_w_p2_up_w_b9b_in',NULL,71,NULL,54,117),(139,'segm_w_b9b_in_w_b10b_in',NULL,54,NULL,55,118),(140,'segm_w_p2_up_w_r3_r6_r9',NULL,71,NULL,13,119),(141,'SEGM_CYSTERNA_B10b_out_w_cyst_mauzer',121,NULL,NULL,69,120),(142,'SEGM_B12c_OUT_W_B12c_OUT',84,NULL,NULL,74,121),(143,'SEGM_B11c_OUT_W_B11c_OUT',83,NULL,NULL,76,123),(144,'SEGM_B10c_OUT_W_B10c_OUT',82,NULL,NULL,78,125),(145,'SEGM_B9c_OUT_W_B9c_OUT',81,NULL,NULL,80,127),(146,'SEGM_B8c_OUT_W_B8c_OUT',80,NULL,NULL,82,129),(147,'SEGM_B7c_OUT_W_B7c_OUT',79,NULL,NULL,84,131),(148,'SEGM_B6c_OUT_W_B6c_OUT',78,NULL,NULL,86,133),(149,'SEGM_B5c_OUT_W_B5c_OUT',77,NULL,NULL,88,135),(150,'SEGM_B4c_OUT_W_B4c_OUT',76,NULL,NULL,90,137),(151,'SEGM_B3c_OUT_W_B3c_OUT',75,NULL,NULL,92,139),(152,'SEGM_B2c_OUT_W_B2c_OUT',74,NULL,NULL,94,141),(153,'SEGM_B1c_OUT_W_B1c_OUT',73,NULL,NULL,96,143),(154,'SEGM_W_B12c_IN_B12c_IN',NULL,73,69,NULL,122),(155,'SEGM_W_B11c_IN_B11c_IN',NULL,75,68,NULL,124),(156,'SEGM_W_B10c_IN_B10c_IN',NULL,77,67,NULL,126),(157,'SEGM_W_B9c_IN_B9c_IN',NULL,79,66,NULL,128),(158,'SEGM_W_B8c_IN_B8c_IN',NULL,81,65,NULL,130),(159,'SEGM_W_B7c_IN_B7c_IN',NULL,83,64,NULL,132),(160,'SEGM_W_B6c_IN_B6c_IN',NULL,85,63,NULL,134),(161,'SEGM_W_B5c_IN_B5c_IN',NULL,87,62,NULL,136),(162,'SEGM_W_B4c_IN_B4c_IN',NULL,89,61,NULL,138),(166,'SEGM_W_B12c_OUT_W_B11c_OUT',NULL,74,NULL,76,145),(167,'SEGM_W_B11c_OUT_W_B12c_OUT',NULL,76,NULL,74,145),(168,'SEGM_W_B11c_OUT_W_B10c_OUT',NULL,76,NULL,78,146),(169,'SEGM_W_B10c_OUT_W_B11c_OUT',NULL,78,NULL,76,146),(176,'SEGM_W_B7c_OUT_W_B6c_OUT',NULL,84,NULL,86,150),(177,'SEGM_W_B6c_OUT_W_B7c_OUT',NULL,86,NULL,84,150),(178,'SEGM_W_B6c_OUT_W_B5c_OUT',NULL,86,NULL,88,151),(179,'SEGM_W_B5c_OUT_W_B6c_OUT',NULL,88,NULL,86,151),(180,'SEGM_W_B5c_OUT_W_B4c_OUT',NULL,88,NULL,90,152),(181,'SEGM_W_B4c_OUT_W_B5c_OUT',NULL,90,NULL,88,152),(182,'SEGM_W_B4c_OUT_W_B3c_OUT',NULL,90,NULL,92,153),(183,'SEGM_W_B3c_OUT_W_B4c_OUT',NULL,92,NULL,90,153),(184,'SEGM_W_B3c_OUT_W_B2c_OUT',NULL,92,NULL,94,154),(185,'SEGM_W_B2c_OUT_W_B3c_OUT',NULL,94,NULL,92,154),(186,'SEGM_W_B2c_OUT_W_B1c_OUT',NULL,94,NULL,96,155),(187,'SEGM_W_B1c_OUT_W_B2c_OUT',NULL,96,NULL,94,155),(188,'SEGM_W_B12c_IN_W_B11c_IN',NULL,73,NULL,75,156),(189,'SEGM_W_B11c_IN_W_B12c_IN',NULL,75,NULL,73,156),(190,'SEGM_W_B11c_IN_W_B10c_IN',NULL,75,NULL,77,157),(191,'SEGM_W_B10c_IN_W_B11c_IN',NULL,77,NULL,75,157),(192,'SEGM_W_B10c_IN_W_B9c_IN',NULL,77,NULL,79,158),(193,'SEGM_W_B9c_IN_W_B10c_IN',NULL,79,NULL,77,158),(196,'SEGM_W_B8c_IN_W_B7c_IN',NULL,81,NULL,83,160),(197,'SEGM_W_B7c_IN_W_B8c_IN',NULL,83,NULL,81,160),(198,'SEGM_W_B7c_IN_W_B6c_IN',NULL,83,NULL,85,161),(199,'SEGM_W_B6c_IN_W_B7c_IN',NULL,85,NULL,83,161),(200,'SEGM_W_B6c_IN_W_B5c_IN',NULL,85,NULL,87,162),(201,'SEGM_W_B5c_IN_W_B6c_IN',NULL,87,NULL,85,162),(202,'SEGM_W_B5c_IN_W_B4c_IN',NULL,87,NULL,89,163),(203,'SEGM_W_B4c_IN_W_B5c_IN',NULL,89,NULL,87,163),(210,'SEGM_W_B4c_B3c_B2c_B1c_IN_W_B4c_IN',NULL,89,NULL,97,167),(211,'SEGM_W_B4c_B3c_B2c_B1c_IN_W_B2c_B1c_IN',NULL,97,NULL,98,168),(214,'SEGM_W_POMPA_B12c_W_B12c_IN',NULL,99,NULL,73,171),(217,'segm_w_b9c_w_pompa_mieszanki_down',NULL,80,NULL,100,182),(218,'segm_w_b8c_w_pompa_mieszanki_down',NULL,82,NULL,100,183),(219,'segm_w_pompa_mieszanki_down_w_pompa_mieszanki_up',NULL,100,NULL,101,177),(220,'segm_w_pompa_mieszanki_rurociag_w_pompa_mieszanki_down',NULL,102,NULL,100,176),(221,'segm_w_pompa_mieszanki_up_w_b9c_in',NULL,101,NULL,79,178),(222,'segm_w_pompa_mieszanki_up_w_b8c_in',NULL,101,NULL,81,179),(223,'segm_w_fz_fn_oczyszczalnia_w_pompa_mieszanki_up',NULL,103,NULL,101,184),(224,'segm_w_b10c_out_w_pompa_mieszanki_rurociag',NULL,78,NULL,102,185),(225,'segm_w_b7c_out_w_pompa_mieszanki_rurociag',NULL,84,NULL,102,186),(226,'segm_w_b12c_out_w_pompa_b12c',NULL,74,NULL,99,187),(227,'segm_biala_out_w_pompa_b12c',123,NULL,NULL,99,188),(228,'segm_cysterna_b12c_out_w_pompa_b12c',125,NULL,NULL,99,189),(229,'segm_w_pompa_b12c_cysterna_b12c_in',NULL,99,124,NULL,190),(230,'segm_w_b4c_b3c_b2c_b1c_in_b3c_in',NULL,97,60,NULL,191),(231,'segm_w_b2c_b1c_in_b2c_in',NULL,98,59,NULL,192),(232,'segm_w_b2c_b1c_in_b1c_in',NULL,98,58,NULL,193),(234,'segm_fn_out_w_fz_fn_oczyszczalnia',14,NULL,NULL,103,199),(235,'segm_fz_out_w_fz_fn_oczyszczalnia',12,NULL,NULL,103,200),(236,'segm_niebieska_out_w_niebieska_out',111,NULL,NULL,68,121),(237,'segm_cysterna_b1b_out_w_cysterna_bypass',119,NULL,NULL,32,122),(238,'segm_mauzer_out_w_cys_mauzer_out',113,NULL,NULL,69,124),(239,'segm_w_cysterna_bypass_cysterna_b1b_in',NULL,32,118,NULL,123);
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
  `nazwa_unikalna` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Np. R1, FZ, B1b, B7c',
  `typ_sprzetu` enum('reaktor','filtr','beczka_brudna','beczka_czysta','apollo','magazyn','cysterna','mauzer') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pojemnosc_kg` decimal(10,2) DEFAULT NULL,
  `stan_sprzetu` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Np. Pusty, W koło, Przelew, Dmuchanie filtra',
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
) ENGINE=InnoDB AUTO_INCREMENT=117 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista całego sprzętu produkcyjnego i magazynowego';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sprzet`
--

LOCK TABLES `sprzet` WRITE;
/*!40000 ALTER TABLE `sprzet` DISABLE KEYS */;
INSERT INTO `sprzet` VALUES (1,'R1','reaktor',9000.00,'Pusty',685.50,0.97,NULL,'2025-07-18 21:08:20',60.00,6.00,NULL,60.00),(2,'R2','reaktor',9000.00,'Zatankowany',685.49,1.13,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(3,'R3','reaktor',9000.00,'Zatankowany (surowy)',685.48,1.21,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(4,'R4','reaktor',9000.00,'Zatankowany',685.47,0.42,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(5,'R5','reaktor',9000.00,'Zatankowany (surowy)',685.47,0.76,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(6,'FZ','filtr',NULL,'W transferze',60.00,4.19,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(7,'FN','filtr',NULL,'W transferze',60.00,4.77,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(8,'B1b','beczka_brudna',10000.00,'Pełna',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(9,'B1c','beczka_czysta',10000.00,'Pusta',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(10,'R6','reaktor',NULL,'Pusty',685.46,1.45,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(11,'R7','reaktor',NULL,'Zatankowany',685.45,0.86,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(12,'R8','reaktor',NULL,'Zatankowany',685.44,0.07,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(13,'R9','reaktor',NULL,'Zatankowany',684.90,1.57,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,60.00),(18,'B2b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(19,'B3b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(20,'B4b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(21,'B5b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(22,'B6b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(23,'B7b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(24,'B8b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(25,'B9b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(26,'B10b','beczka_brudna',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(28,'B2c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(29,'B3c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(30,'B4c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(31,'B5c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(32,'B6c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(33,'B7c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(34,'B8c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(35,'B9c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(36,'B10c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(37,'B11c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(38,'B12c','beczka_czysta',NULL,NULL,NULL,NULL,NULL,NULL,120.00,6.00,NULL,NULL),(107,'AP1','apollo',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(108,'AP2','apollo',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(109,'NIEBIESKA','beczka_brudna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(110,'CYSTERNA_B1b','cysterna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(111,'MAUZER','mauzer',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(114,'CYSTERNA_B10b','cysterna',25000.00,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(115,'BIALA','beczka_brudna',NULL,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL),(116,'CYSTERNA_B12c','cysterna',25000.00,'Gotowy',60.00,0.00,NULL,'2025-07-18 21:08:20',120.00,6.00,NULL,NULL);
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
  `nazwa_wezla` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_wezla` (`nazwa_wezla`)
) ENGINE=InnoDB AUTO_INCREMENT=138 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Punkty łączeniowe w rurociągu (trójniki, kolektory)';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `wezly_rurociagu`
--

LOCK TABLES `wezly_rurociagu` WRITE;
/*!40000 ALTER TABLE `wezly_rurociagu` DISABLE KEYS */;
INSERT INTO `wezly_rurociagu` VALUES (57,'w_ap1_out'),(59,'w_ap2_out'),(55,'w_b10b_in'),(53,'w_b10b_out'),(77,'w_b10c_in'),(78,'w_b10c_out'),(75,'w_b11c_in'),(76,'w_b11c_out'),(73,'w_b12c_in'),(74,'w_b12c_out'),(24,'w_b1b_in'),(16,'w_b1b_out'),(96,'w_b1c_out'),(25,'w_b2b_in'),(17,'w_b2b_out'),(98,'w_b2c_b1c_in'),(94,'w_b2c_out'),(26,'w_b3b_in'),(18,'w_b3b_out'),(92,'w_b3c_out'),(27,'w_b4b_in'),(19,'w_b4b_out'),(97,'w_b4c_b3c_b2c_b1c_in'),(89,'w_b4c_in'),(90,'w_b4c_out'),(28,'w_b5b_in'),(20,'w_b5b_out'),(87,'w_b5c_in'),(88,'w_b5c_out'),(29,'w_b6b_in'),(21,'w_b6b_out'),(85,'w_b6c_in'),(86,'w_b6c_out'),(30,'w_b7b_in'),(22,'w_b7b_out'),(83,'w_b7c_in'),(84,'w_b7c_out'),(31,'w_b8b_in'),(23,'w_b8b_out'),(81,'w_b8c_in'),(82,'w_b8c_out'),(54,'w_b9b_in'),(52,'w_b9b_out'),(79,'w_b9c_in'),(80,'w_b9c_out'),(69,'w_cys_mauzer_out'),(32,'w_cysterna_bypass'),(8,'W_FN_OUT_MAIN'),(103,'w_fz_fn_oczyszczalnia'),(6,'W_FZ_IN_MAIN'),(7,'W_FZ_OUT_MAIN'),(68,'w_niebieska_out'),(70,'w_p2_down'),(71,'w_p2_up'),(34,'w_p3_down'),(33,'w_p3_up'),(99,'w_pompa_b12c'),(100,'w_pompa_mieszanki_down'),(102,'w_pompa_mieszanki_rurociag'),(101,'w_pompa_mieszanki_up'),(3,'W_R1_FZ'),(2,'W_R1_R2'),(1,'W_R2_R3'),(13,'W_R3_R6_R9'),(5,'W_R4_FZ'),(4,'W_R4_R5'),(15,'W_R5_R6'),(9,'W_R7_FN'),(10,'W_R7_R8'),(11,'W_R8_R9'),(35,'w_tankowanie');
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
  `nazwa_zaworu` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `stan` enum('OTWARTY','ZAMKNIETY') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ZAMKNIETY',
  PRIMARY KEY (`id`),
  UNIQUE KEY `nazwa_zaworu` (`nazwa_zaworu`)
) ENGINE=InnoDB AUTO_INCREMENT=205 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lista zaworów sterujących przepływem';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `zawory`
--

LOCK TABLES `zawory` WRITE;
/*!40000 ALTER TABLE `zawory` DISABLE KEYS */;
INSERT INTO `zawory` VALUES (1,'V_R3_OUT_W_R2_R3','ZAMKNIETY'),(2,'V_W_R2_R3_W_R1_R2','ZAMKNIETY'),(3,'V_W_R1_R2_W_R1_FZ','ZAMKNIETY'),(4,'V_R5_OUT_W_R4_R5','ZAMKNIETY'),(5,'V_W_R4_R5_W_R4_FZ','ZAMKNIETY'),(6,'V_W_R1_FZ_W_FZ_IN','ZAMKNIETY'),(7,'V_W_R4_FZ_W_FZ_IN','ZAMKNIETY'),(8,'V_W_FZ_IN_FZ_IN','ZAMKNIETY'),(9,'V_FZ_OUT_W_FZ_OUT','ZAMKNIETY'),(10,'V_W_FZ_OUT_R1_IN','ZAMKNIETY'),(11,'V_W_FZ_OUT_R2_IN','ZAMKNIETY'),(12,'V_W_FZ_OUT_R3_IN','ZAMKNIETY'),(13,'V_W_FZ_OUT_R4_IN','ZAMKNIETY'),(14,'V_W_FZ_OUT_R5_IN','ZAMKNIETY'),(15,'V_FZ_IN_FZ_OUT','ZAMKNIETY'),(16,'V_R2_OUT_W_R1_R2','ZAMKNIETY'),(17,'V_R1_OUT_W_R1_FZ','ZAMKNIETY'),(18,'V_R4_OUT_W_R4_FZ','ZAMKNIETY'),(21,'V_FN_IN_FN_OUT','ZAMKNIETY'),(22,'V_R7_OUT_W_R7_FN','ZAMKNIETY'),(23,'V_R8_OUT_W_R7_R8','ZAMKNIETY'),(24,'V_R9_OUT_W_R8_R9','ZAMKNIETY'),(25,'V_W_R7_FN_FN_IN','ZAMKNIETY'),(26,'V_W_R7_FN_W_R7_R8','ZAMKNIETY'),(27,'V_W_R7_R8_W_R8_R9','ZAMKNIETY'),(28,'V_W_R8_R9_W_R3_R6_R9','ZAMKNIETY'),(29,'V_W_R3_R6_R9_W_R5_R6','ZAMKNIETY'),(30,'V_W_R3_R6_R9_W_R3_R2','ZAMKNIETY'),(31,'V_R6_OUT_W_R5_R6','ZAMKNIETY'),(32,'V_W_R4_R5_W_R5_R6','ZAMKNIETY'),(33,'V_FN_OUT_DO_W_FN_OUT','ZAMKNIETY'),(34,'V_W_FN_OUT_MAIN_DO_R6_IN','ZAMKNIETY'),(35,'V_W_FN_OUT_MAIN_DO_R7_IN','ZAMKNIETY'),(36,'V_W_FN_OUT_MAIN_DO_R8_IN','ZAMKNIETY'),(37,'V_W_FN_OUT_MAIN_DO_R9_IN','ZAMKNIETY'),(38,'v_b1b_out_w_b1b_out','ZAMKNIETY'),(39,'v_b2b_out_w_b2b_out','ZAMKNIETY'),(40,'v_b3b_out_w_b3b_out','ZAMKNIETY'),(41,'v_b4b_out_w_b4b_out','ZAMKNIETY'),(42,'v_b5b_out_w_b5b_out','ZAMKNIETY'),(43,'v_b6b_out_w_b6b_out','ZAMKNIETY'),(44,'v_b7b_out_w_b7b_out','ZAMKNIETY'),(45,'v_b8b_out_w_b8b_out','ZAMKNIETY'),(46,'v_w_b1b_in_b1b_in','ZAMKNIETY'),(47,'v_w_b2b_in_b2b_in','ZAMKNIETY'),(48,'v_w_b3b_in_b3b_in','ZAMKNIETY'),(49,'v_w_b4b_in_b4b_in','ZAMKNIETY'),(50,'v_w_b5b_in_b5b_in','ZAMKNIETY'),(51,'v_w_b6b_in_b6b_in','ZAMKNIETY'),(52,'v_w_b7b_in_b7b_in','ZAMKNIETY'),(53,'v_w_b8b_in_b8b_in','ZAMKNIETY'),(54,'v_w_b1b_out_w_b2b_out','ZAMKNIETY'),(55,'v_w_b2b_out_w_b3b_out','ZAMKNIETY'),(56,'v_w_b3b_out_w_b4b_out','ZAMKNIETY'),(57,'v_w_b4b_out_w_b5b_out','ZAMKNIETY'),(58,'v_w_b5b_out_w_b6b_out','ZAMKNIETY'),(59,'v_w_b6b_out_w_b7b_out','ZAMKNIETY'),(60,'v_w_b7b_out_w_b8b_out','ZAMKNIETY'),(61,'v_w_b8b_in_w_b7b_in','ZAMKNIETY'),(62,'v_w_b7b_in_w_b6b_in','ZAMKNIETY'),(63,'v_w_b6b_in_w_b5b_in','ZAMKNIETY'),(64,'v_w_b5b_in_w_b4b_in','ZAMKNIETY'),(65,'v_w_b4b_in_w_b3b_in','ZAMKNIETY'),(66,'v_w_b3b_in_w_b2b_in','ZAMKNIETY'),(67,'v_w_b2b_in_w_b1b_in','ZAMKNIETY'),(68,'v_w_b8b_out_w_p3_down','ZAMKNIETY'),(69,'v_w_p3_down_w_p3_up','ZAMKNIETY'),(70,'v_w_p3_down_w_tankowanie','ZAMKNIETY'),(71,'v_w_p3_up_w_b8b_in','ZAMKNIETY'),(72,'v_w_tankowanie_r1_in','ZAMKNIETY'),(73,'v_w_tankowanie_r2_in','ZAMKNIETY'),(74,'v_w_tankowanie_r3_in','ZAMKNIETY'),(75,'v_w_tankowanie_r4_in','ZAMKNIETY'),(76,'v_w_tankowanie_r5_in','ZAMKNIETY'),(77,'v_w_tankowanie_r6_in','ZAMKNIETY'),(78,'v_w_tankowanie_r7_in','ZAMKNIETY'),(79,'v_w_tankowanie_r8_in','ZAMKNIETY'),(80,'v_w_tankowanie_r9_in','ZAMKNIETY'),(81,'v_w_b1b_in_w_cysterna_bypass','ZAMKNIETY'),(82,'v_w_cysterna_bypass_w_b1b_out','ZAMKNIETY'),(83,'v_b9b_out_w_b9b_out','ZAMKNIETY'),(84,'v_b10b_out_w_b10b_out','ZAMKNIETY'),(85,'v_w_b9b_in_b9b_in','ZAMKNIETY'),(86,'v_w_b10b_in_b10b_in','ZAMKNIETY'),(88,'v_w_ap1_out_ap1_out','ZAMKNIETY'),(90,'v_w_ap2_out_ap2_out','ZAMKNIETY'),(106,'v_w_b9b_out_w_b10b_out','ZAMKNIETY'),(107,'v_w_b10b_in_w_b9b_in','ZAMKNIETY'),(109,'v_W_R3_R6_R9_W_p3_down','ZAMKNIETY'),(110,'v_w_ap2_out_w_ap1_out','ZAMKNIETY'),(111,'v_w_ap1_w_niebieska_out','ZAMKNIETY'),(112,'v_w_niebieska_out_w_cys_mauzer_out','ZAMKNIETY'),(113,'v_w_cys_mauzer_out_w_b10b_out','ZAMKNIETY'),(114,'v_w_b10b_out_w_b9b_out','ZAMKNIETY'),(115,'v_w_b9b_out_w_p2_down','ZAMKNIETY'),(116,'v_w_p2_down_w_p2_up','ZAMKNIETY'),(117,'v_w_p2_up_w_b9b_in','ZAMKNIETY'),(118,'v_w_b9b_in_w_b10b_in','ZAMKNIETY'),(119,'v_w_p2_up_w_r3_r6_r9','ZAMKNIETY'),(120,'V_CYSTERNA_B10b_out_w_cyst_mauzer','ZAMKNIETY'),(121,'V_B12c_OUT_W_B12c_OUT','ZAMKNIETY'),(122,'V_W_B12c_IN_B12c_IN','ZAMKNIETY'),(123,'V_B11c_OUT_W_B11c_OUT','ZAMKNIETY'),(124,'V_W_B11c_IN_B11c_IN','ZAMKNIETY'),(125,'V_B10c_OUT_W_B10c_OUT','ZAMKNIETY'),(126,'V_W_B10c_IN_B10c_IN','ZAMKNIETY'),(127,'V_B9c_OUT_W_B9c_OUT','ZAMKNIETY'),(128,'V_W_B9c_IN_B9c_IN','ZAMKNIETY'),(129,'V_B8c_OUT_W_B8c_OUT','ZAMKNIETY'),(130,'V_W_B8c_IN_B8c_IN','ZAMKNIETY'),(131,'V_B7c_OUT_W_B7c_OUT','ZAMKNIETY'),(132,'V_W_B7c_IN_B7c_IN','ZAMKNIETY'),(133,'V_B6c_OUT_W_B6c_OUT','ZAMKNIETY'),(134,'V_W_B6c_IN_B6c_IN','ZAMKNIETY'),(135,'V_B5c_OUT_W_B5c_OUT','ZAMKNIETY'),(136,'V_W_B5c_IN_B5c_IN','ZAMKNIETY'),(137,'V_B4c_OUT_W_B4c_OUT','ZAMKNIETY'),(138,'V_W_B4c_IN_B4c_IN','ZAMKNIETY'),(139,'V_B3c_OUT_W_B3c_OUT','ZAMKNIETY'),(141,'V_B2c_OUT_W_B2c_OUT','ZAMKNIETY'),(143,'V_B1c_OUT_W_B1c_OUT','ZAMKNIETY'),(145,'V_W_B12c_OUT_W_B11c_OUT','ZAMKNIETY'),(146,'V_W_B11c_OUT_W_B10c_OUT','ZAMKNIETY'),(150,'V_W_B7c_OUT_W_B6c_OUT','ZAMKNIETY'),(151,'V_W_B6c_OUT_W_B5c_OUT','ZAMKNIETY'),(152,'V_W_B5c_OUT_W_B4c_OUT','ZAMKNIETY'),(153,'V_W_B4c_OUT_W_B3c_OUT','ZAMKNIETY'),(154,'V_W_B3c_OUT_W_B2c_OUT','ZAMKNIETY'),(155,'V_W_B2c_OUT_W_B1c_OUT','ZAMKNIETY'),(156,'V_W_B12c_IN_W_B11c_IN','ZAMKNIETY'),(157,'V_W_B11c_IN_W_B10c_IN','ZAMKNIETY'),(158,'V_W_B10c_IN_W_B9c_IN','ZAMKNIETY'),(160,'V_W_B8c_IN_W_B7c_IN','ZAMKNIETY'),(161,'V_W_B7c_IN_W_B6c_IN','ZAMKNIETY'),(162,'V_W_B6c_IN_W_B5c_IN','ZAMKNIETY'),(163,'V_W_B5c_IN_W_B4c_IN','ZAMKNIETY'),(167,'V_W_B4c_B3c_B2c_B1c_IN_W_B4c_IN','ZAMKNIETY'),(168,'V_W_B4c_B3c_B2c_B1c_IN_W_B2c_B1c_IN','ZAMKNIETY'),(171,'V_W_POMPA_B12c_W_B12c_IN','ZAMKNIETY'),(176,'V_W_POMPA_MIESZANKI_RUROCIAG_W_POMPA_MIESZANKI_DOWN','ZAMKNIETY'),(177,'V_W_POMPA_MIESZANKI_DOWN_W_POMPA_MIESZANKI_UP','ZAMKNIETY'),(178,'V_W_POMPA_MIESZANKI_UP_W_B9c_IN','ZAMKNIETY'),(179,'V_W_POMPA_MIESZANKI_UP_W_B8c_IN','ZAMKNIETY'),(182,'v_w_b9c_w_pompa_mieszanki_down','ZAMKNIETY'),(183,'v_w_b8c_w_pompa_mieszanki_down','ZAMKNIETY'),(184,'v_w_fz_fn_oczyszczalnia_w_pompa_mieszanki_up','ZAMKNIETY'),(185,'v_w_b10c_out_w_pompa_mieszanki_rurociag','ZAMKNIETY'),(186,'v_w_b7c_out_w_pompa_mieszanki_rurociag','ZAMKNIETY'),(187,'v_w_b12c_out_w_pompa_b12c','ZAMKNIETY'),(188,'v_biala_out_w_pompa_b12c','ZAMKNIETY'),(189,'v_cysterna_b12c_out_w_pompa_b12c','ZAMKNIETY'),(190,'v_w_pompa_b12c_cysterna_b12c_in','ZAMKNIETY'),(191,'v_w_b4c_b3c_b2c_b1c_in_b3c_in','ZAMKNIETY'),(192,'v_w_b2c_b1c_in_b2c_in','ZAMKNIETY'),(193,'v_w_b2c_b1c_in_b1c_in','ZAMKNIETY'),(199,'v_fn_out_w_fz_fn_oczyszczalnia','ZAMKNIETY'),(200,'v_fz_out_w_fz_fn_oczyszczalnia','ZAMKNIETY');
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

-- Dump completed on 2025-07-18 21:09:33
