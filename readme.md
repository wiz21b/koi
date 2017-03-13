This is Koï
===========

Koï is a production management system. It is aimed at mid-size manufacturing workshops.
It tracks production, quality issues, work done, orders, preorders and a few other things.
It strives to do that in a simple and flexible way, not imposing any specific workflow.
It is therefore aimed at "agile" companies. If you want strict workflow, choose SAP.

It's in production use since a few years (so, yes, it is battle tested).


Business
========

This version is the community version. For professional services, licensing issues
or other business matters, feel free to contact us at <schampailler@skynet.be>.

How to install
==============

The easy way
------------

Download the server installer from here. Run it as administrator.


The adventurer way
------------------

Koï installation require some work. It is made of a client, a server and a database.
Each of those require some level of configuration.

First, you should install the database. Koï requires Postgres 9.4 at least.
Install it and then create a user which can create tables, sequences, etc.
Like this :

    CREATE ROLE horse_adm CREATEDB CREATEUSER LOGIN PASSWORD 'horsihors';

Each client has to connect to the database. Therefore, make sure you
authorize access to Postgres from outside. The simplest way is to edit
pg_hba.conf. Refer to Postgres documentation.

Now install the server. Download it from here. The

    pip install koi-server

Koï needs python3. This will download all dependencies.

Once you have the server, you use it to initialize the database. Like this :

    python -m koi.server.cherry --create-database http://127.0.0.1/...

Running the client should be easy. Download it from here.
If you need to install the client for a company network, then it is
best to register it into the server. Do it like this :

    python -m koi.server.cherry --register-client slfjsldjf.zip

You can then download it from the server. The registration process allows
the server to inject a few configuration parameters into the client.
This will also allow the server to advertize the new version to the
otherwise installed clients, alowing those to update themselves.
That is the standard way of upgrading client in Koï : register
a new version of the client into the server.