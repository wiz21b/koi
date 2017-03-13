from datetime import date
from sqlalchemy.sql import select,func,and_,or_

from Logging import mainlog,init_logging
from Configurator import init_i18n,load_configuration,configuration,resource_dir
init_logging()
init_i18n()
load_configuration()

from db_mapping import metadata
from datalayer.database_session import init_db_session

from datalayer.database_session import session
from db_mapping import FilterQuery


init_db_session(configuration.database_url, metadata, False or configuration.echo_query)

from dao import dao

def alter_structure():

    session().connection().execute("""CREATE TABLE horse.filter_queries (
        filter_query_id SERIAL NOT NULL,
        name VARCHAR NOT NULL,
        query VARCHAR NOT NULL,
        shared BOOLEAN NOT NULL,
        owner_id INTEGER NOT NULL,
        PRIMARY KEY (filter_query_id),
        CONSTRAINT fq_by_name UNIQUE (name, owner_id),
        FOREIGN KEY(owner_id) REFERENCES horse.employees (employee_id))""")

    session().connection().execute("GRANT ALL ON horse.filter_queries TO horse_clt ;")

    session().commit()

def alter_data():

    # Allow the migration script to be run several times
    session().query(FilterQuery).delete()

    owner_id = dao.employee_dao.find_by_login("dd").employee_id

    fq = FilterQuery()
    fq.name = "Finies ce mois"
    fq.query = "CompletionDate in CurrentMonth"
    fq.shared = True
    fq.owner_id = owner_id

    dao.filters_dao.save(fq)

    fq = FilterQuery()
    fq.name = u"Finies mois passe"
    fq.query = "CompletionDate in MonthBefore"
    fq.shared = True
    fq.owner_id = owner_id

    dao.filters_dao.save(fq)

    fq = FilterQuery()
    fq.name = "En production"
    fq.query = "Status = ready_for_production"
    fq.shared = True
    fq.owner_id = owner_id

    dao.filters_dao.save(fq)

    fq = FilterQuery()
    fq.name = "Devis"
    fq.query = "Status = preorder"
    fq.shared = True
    fq.owner_id = owner_id

    dao.filters_dao.save(fq)

    fq = FilterQuery()
    fq.name = "Dormantes"
    fq.query = "Status = production_paused"
    fq.shared = True
    fq.owner_id = owner_id

    dao.filters_dao.save(fq)

alter_structure()
alter_data()
