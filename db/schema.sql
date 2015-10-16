-- MySQL Database schema
CREATE DATABASE discord;

-- Table with all the data.
CREATE TABLE message (
    id INT KEY AUTO_INCREMENT,
    dir TINYINT NOT NULL,
    time TIMESTAMP NOT NULL,
    op INT,
    s INT,
    t VARCHAR(255),
    raw MEDIUMTEXT NOT NULL,
)

-- You'll need to modify these to fit your setup
CREATE USER 'logger'@'localhost' IDENTIFIED BY 'Bot password';
GRANT SELECT, INSERT ON discord.message TO 'logger'@'localhost';

CREATE USER 'web'@'localhost' IDENTIFIED BY 'Web password'
GRANT SELECT on discord.message TO 'web'@'localhost';
