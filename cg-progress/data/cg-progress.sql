CREATE TABLE `PCBA_Movement` (
	`serial_number`	STRING	NOT NULL	COMMENT 'prefix + 0000',
	`manufacturer`	STRING	NOT NULL,
	`type`	STRING	NOT NULL	COMMENT 'Inbound, Outbound',
	`date`	DATE	NOT NULL
);

CREATE TABLE `PCBA` (
	`prefix`	STRING	NOT NULL,
	`board`	STRING	NOT NULL
);

CREATE TABLE `PCBA_Functional_Test` (
	`serial_number`	STRING	NOT NULL	COMMENT 'prefix + 0000',
	`test_item`	INTEGER	NOT NULL,
	`measurements`	FLOAT	NULL,
	`test_datetime`	DATETIME	NOT NULL,
	`test_by`	STRING	NOT NULL	COMMENT 'oid',
	`verify_datetime`	DATETIME	NOT NULL,
	`verify_by`	STRING	NULL	COMMENT 'oid'
);

CREATE TABLE `Users` (
	`oid`	STRING	NOT NULL,
	`email`	STRING	NOT NULL,
	`name`	STRING	NOT NULL,
	`role`	STRING	NOT NULL,
	`join_datetime`	STRING	NOT NULL,
	`status`	STRING	NOT NULL	COMMENT 'Active, Resigned,  External'
);

CREATE TABLE `PCBA_Conformal_Coating` (
	`serial_number`	STRING	NOT NULL	COMMENT 'prefix + 0000',
	`point`	STRING	NOT NULL	COMMENT 'T1~4, B1~4',
	`coating_datetime`	DATETIME	NOT NULL,
	`coating_by`	STRING	NOT NULL	COMMENT 'oid',
	`verify_datetime`	DATETIME	NOT NULL,
	`verify_by`	STRING	NULL	COMMENT 'oid'
);

CREATE TABLE `PCBA_Functional_Test_Description` (
	`serial_number`	STRING	NOT NULL	COMMENT 'prefix + 0000',
	`test_item`	INTEGER	NOT NULL,
	`description`	STRING	NOT NULL,
	`min`	FLOAT	NULL,
	`max`	FLOAT	NULL,
	`unit`	STRING	NOT NULL,
	`image`	STRING	NULL	COMMENT 'image file name'
);

CREATE TABLE `PCBA_Conformal_Coating_Description` (
	`serial_number`	STRING	NOT NULL	COMMENT 'prefix + 0000',
	`point`	STRING	NOT NULL	COMMENT 'T1~4, B1~4',
	`min`	FLOAT	NOT NULL,
	`unit`	STRING	NOT NULL	COMMENT 'μm',
	`image`	STRING	NULL	COMMENT 'image file name'
);

CREATE TABLE `Part_Information` (
	`part_number`	STRING	NOT NULL	COMMENT 'C00-0000',
	`process`	STRING	NOT NULL	COMMENT 'SMD, MI, ME, FA',
	`description`	STRING	NOT NULL,
	`manufacturer`	STRING	NOT NULL,
	`mpn`	STRING	NOT NULL
);

CREATE TABLE `Part_List` (
	`part_number`	STRING	NOT NULL	COMMENT 'C00-0000',
	`prefix`	STRING	NOT NULL,
	`designator`	STRING	NOT NULL
);

CREATE TABLE `Part_Movement` (
	`part_number`	STRING	NOT NULL	COMMENT 'C00-0000',
	`manufacturer`	STRING	NOT NULL,
	`type`	DATE	NOT NULL	COMMENT 'Inbound, Outbound',
	`date`	DATE	NOT NULL
);

ALTER TABLE `PCBA_Movement` ADD CONSTRAINT `PK_PCBA_MOVEMENT` PRIMARY KEY (
	`serial_number`
);

ALTER TABLE `PCBA` ADD CONSTRAINT `PK_PCBA` PRIMARY KEY (
	`prefix`
);

ALTER TABLE `PCBA_Functional_Test` ADD CONSTRAINT `PK_PCBA_FUNCTIONAL_TEST` PRIMARY KEY (
	`serial_number`,
	`test_item`
);

ALTER TABLE `Users` ADD CONSTRAINT `PK_USERS` PRIMARY KEY (
	`oid`
);

ALTER TABLE `PCBA_Conformal_Coating` ADD CONSTRAINT `PK_PCBA_CONFORMAL_COATING` PRIMARY KEY (
	`serial_number`,
	`point`
);

ALTER TABLE `PCBA_Functional_Test_Description` ADD CONSTRAINT `PK_PCBA_FUNCTIONAL_TEST_DESCRIPTION` PRIMARY KEY (
	`serial_number`,
	`test_item`
);

ALTER TABLE `PCBA_Conformal_Coating_Description` ADD CONSTRAINT `PK_PCBA_CONFORMAL_COATING_DESCRIPTION` PRIMARY KEY (
	`serial_number`,
	`point`
);

ALTER TABLE `Part_Information` ADD CONSTRAINT `PK_PART_INFORMATION` PRIMARY KEY (
	`part_number`
);

ALTER TABLE `Part_List` ADD CONSTRAINT `PK_PART_LIST` PRIMARY KEY (
	`part_number`,
	`prefix`
);

ALTER TABLE `Part_Movement` ADD CONSTRAINT `PK_PART_MOVEMENT` PRIMARY KEY (
	`part_number`
);

ALTER TABLE `PCBA_Functional_Test_Description` ADD CONSTRAINT `FK_PCBA_Functional_Test_TO_PCBA_Functional_Test_Description_1` FOREIGN KEY (
	`serial_number`
)
REFERENCES `PCBA_Functional_Test` (
	`serial_number`
);

ALTER TABLE `PCBA_Functional_Test_Description` ADD CONSTRAINT `FK_PCBA_Functional_Test_TO_PCBA_Functional_Test_Description_2` FOREIGN KEY (
	`test_item`
)
REFERENCES `PCBA_Functional_Test` (
	`test_item`
);

ALTER TABLE `PCBA_Conformal_Coating_Description` ADD CONSTRAINT `FK_PCBA_Conformal_Coating_TO_PCBA_Conformal_Coating_Description_1` FOREIGN KEY (
	`serial_number`
)
REFERENCES `PCBA_Conformal_Coating` (
	`serial_number`
);

ALTER TABLE `PCBA_Conformal_Coating_Description` ADD CONSTRAINT `FK_PCBA_Conformal_Coating_TO_PCBA_Conformal_Coating_Description_2` FOREIGN KEY (
	`point`
)
REFERENCES `PCBA_Conformal_Coating` (
	`point`
);

ALTER TABLE `Part_List` ADD CONSTRAINT `FK_Part_Information_TO_Part_List_1` FOREIGN KEY (
	`part_number`
)
REFERENCES `Part_Information` (
	`part_number`
);

ALTER TABLE `Part_List` ADD CONSTRAINT `FK_PCBA_TO_Part_List_1` FOREIGN KEY (
	`prefix`
)
REFERENCES `PCBA` (
	`prefix`
);

ALTER TABLE `Part_Movement` ADD CONSTRAINT `FK_Part_Information_TO_Part_Movement_1` FOREIGN KEY (
	`part_number`
)
REFERENCES `Part_Information` (
	`part_number`
);

