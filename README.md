Discord Logger
==============

Discord logger is a simple logging bot and web application for recording
and documenting the messages on the Discord WebSocket API.  This is
useful for the development of third-party Discord clients, as an
official API for Discord has not yet been released.


Requirements
------------

* MySQL database
* Python 3
  - [pymysql](http://www.pymysql.org/) (can be installed with `pip
    install pymysql`)
  - [discord.py](https://github.com/Rapptz/discord.py) >= 0.8.0 (can be
    installed with `pip install discord.py`)
* Webserver with PHP 5 (for the web app)


Configuration
-------------

See [db/schema.sql](db/schema.sql) for a description of the database setup,
[logger/config-example](logger/config-example) for the configuration of the
Discord bot and the analysis program, and finally
[web/.htaccess-example](web/.htaccess-example) for the web application.
