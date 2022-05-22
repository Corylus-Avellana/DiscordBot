CREATE TABLE Announce (
	ID int not null AUTO_INCREMENT,
	time BIGINT,
	channelid TEXT,
	react_msg TEXT,
	guildid TEXT,
	react_chan TEXT,
	text MEDIUMTEXT,
	threshold INT,
	PRIMARY KEY(ID)
);
