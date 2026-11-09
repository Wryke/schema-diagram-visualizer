-- MySQL dump 10.13  Distrib 8.0.36, for Linux (x86_64)
-- Written by hand in the format mysqldump produces, including its usual header and footer.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!50503 SET NAMES utf8mb4 */;
SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO';

# A MySQL comment, and it's got an apostrophe.

DROP TABLE IF EXISTS `country`;
CREATE TABLE `country` (
  `country_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `country` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `last_update` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`country_id`)
) ENGINE=InnoDB AUTO_INCREMENT=110 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

LOCK TABLES `country` WRITE;
INSERT INTO `country` VALUES (1,'Cote d\'Ivoire; really','2006-02-15 04:44:00'),(2,'Land''s End','2006-02-15 04:44:00');
UNLOCK TABLES;

CREATE TABLE `city` (
  `city_id` smallint unsigned NOT NULL AUTO_INCREMENT COMMENT 'it\'s the id',
  `city` varchar(50) NOT NULL,
  `country_id` smallint unsigned NOT NULL,
  `key` varchar(20) DEFAULT NULL,
  `kind` enum('big','small') NOT NULL DEFAULT 'small',
  `flags` set('a','b','c') DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`city_id`),
  UNIQUE KEY `uq_city_key` (`key`(10)),
  KEY `idx_fk_country_id` (`country_id`) USING BTREE,
  FULLTEXT KEY `idx_city` (`city`),
  CONSTRAINT `fk_city_country` FOREIGN KEY (`country_id`) REFERENCES `country` (`country_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=601 DEFAULT CHARSET=utf8mb4;

CREATE TABLE `staff` (
  `staff_id` tinyint unsigned NOT NULL AUTO_INCREMENT,
  `city_id` smallint unsigned NOT NULL,
  `manager_id` tinyint unsigned DEFAULT NULL,
  `picture` blob,
  `salary` decimal(10,2) unsigned NOT NULL DEFAULT '0.00',
  PRIMARY KEY (`staff_id`),
  KEY `idx_manager` (`manager_id`),
  CONSTRAINT `fk_staff_city` FOREIGN KEY (`city_id`) REFERENCES `city` (`city_id`),
  CONSTRAINT `fk_staff_manager` FOREIGN KEY (`manager_id`) REFERENCES `staff` (`staff_id`) ON DELETE SET NULL,
  CONSTRAINT `chk_salary` CHECK ((`salary` < 1000000)) /*!80016 NOT ENFORCED */
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `rental` (
  `rental_id` int NOT NULL AUTO_INCREMENT,
  `staff_id` tinyint unsigned NOT NULL,
  PRIMARY KEY (`rental_id`),
  KEY (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE `rental`
  ADD KEY `idx_rental_staff` (`staff_id`),
  ADD CONSTRAINT `fk_rental_staff` FOREIGN KEY (`staff_id`) REFERENCES `staff` (`staff_id`);

/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `city_touch` BEFORE INSERT ON `city` FOR EACH ROW SET NEW.last_update=NOW() */;

DELIMITER ;;
CREATE PROCEDURE `count_cities`(OUT total INT)
BEGIN
  SELECT COUNT(*) INTO total FROM city; -- it's a count
END ;;
DELIMITER ;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
SET SQL_MODE=@OLD_SQL_MODE;
