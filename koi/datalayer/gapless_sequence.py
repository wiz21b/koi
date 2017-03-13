""" The gapless sequence is a column populated by a regular sequence
with additional contraintes ensuring that the value in the columns
are a sequence without any gap.

This is important when making accounting documents, those must be numbered
in monotonic sequences. Since it's tied to accounting, we take extra
care to really ensure the gapless nature of the sequences.

The constraints are enforce by more elaborated PL/SQL code.
The gapless sequences are also stored in a regular table.
"""
from sqlalchemy import String, Integer, Table, Column
from sqlalchemy.sql import expression
from sqlalchemy.ext.compiler import compiles

from koi.datalayer.database_session import session
from koi.datalayer.sqla_mapping_base import metadata, DATABASE_SCHEMA

# Will store each sequence with its name its current value.
gapless_seq_table = Table('gapless_seq', metadata,
                          Column('gseq_name',String,primary_key=True),
                          Column('gseq_value',Integer,nullable=False))


# See http://docs.sqlalchemy.org/en/rel_0_8/core/compiler.html

# We basically define a "ClauseElement" that is a simple call
# to our PostgresFunction. We need a ClauseElement because it's
# well embedded into the SQLA framework. For example, it can
# be called in a "select" statement, which is rather nice.

class gaplessseq(expression.ColumnElement):
    type = Integer()
    name = "gaplessseq"
    def __init__(self,seqname):
        self.seqname = seqname

@compiles(gaplessseq)
def default_gaplessseq(element, compiler, **kw):
    return "{}.gseq_nextval('{}')".format(DATABASE_SCHEMA, element.seqname)

@compiles(gaplessseq, 'postgresql')
def pg_gaplessseq(element, compiler, **kw):
    return "{}.gseq_nextval('{}')".format(DATABASE_SCHEMA, element.seqname)

def current_gaplessseq_value(name):
    return session().query(gapless_seq_table.columns['gseq_value']).filter(gapless_seq_table.columns['gseq_name'] == name).scalar()



def make_gapless_seq_function(schema, table, seq_field, gapless_seq_name,func_base_name):

    if schema:
        table = schema + "." + table

    session().connection().execute("DROP TRIGGER IF EXISTS control_{1}_delete ON {0}".format(table, func_base_name))
    session().connection().execute("DROP TRIGGER IF EXISTS control_{1}_update ON {0}".format(table, func_base_name))
    session().connection().execute("DROP TRIGGER IF EXISTS control_{1}_insert ON {0}".format(table, func_base_name))

    session().connection().execute("COMMIT")


    session().connection().execute("DROP FUNCTION IF EXISTS {0}.check_control_{1}_gapless_sequence_insert()".format(schema, func_base_name))
    session().connection().execute("DROP FUNCTION IF EXISTS {0}.check_control_{1}_gapless_sequence_delete()".format(schema, func_base_name))
    session().connection().execute("DROP FUNCTION IF EXISTS {0}.check_control_{1}_gapless_sequence_update()".format(schema, func_base_name))

    session().connection().execute("COMMIT")

    session().connection().execute("""CREATE FUNCTION {0}.check_control_{3}_gapless_sequence_insert() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
BEGIN
    -- Call this AFTER INSERT

    IF NEW.{2} IS NULL THEN
        -- we tolerate nulls (of course they don't participate in the gapless seq.)
        RETURN NULL;
    END IF;

    -- Sequence starts on 1 (not zero)

    SELECT min({2}) INTO min_id FROM {1};
    SELECT max({2}) INTO max_id FROM {1};
    SELECT count(*) INTO cnt FROM {1} WHERE {2} IS NOT NULL;

    IF cnt > 1 AND max_id - min_id + 1 <> cnt THEN
        RAISE EXCEPTION 'Gapless sequence has been broken for {1}.{2}; (min=%%,max=%%,cnt=%%)', min_id, max_id, cnt;
    ELSE
        RETURN NEW;
    END IF;
END;
    $$ LANGUAGE plpgsql;""".format(schema, table, gapless_seq_name, func_base_name))


    session().connection().execute("""CREATE FUNCTION {0}.check_control_{3}_gapless_sequence_delete() RETURNS trigger AS $$
DECLARE
    difference NUMERIC;
    min_id NUMERIC;
    max_id NUMERIC;
    cnt NUMERIC;
    n INTEGER;
BEGIN
    -- Call this *only* AFTER DELETE
    -- Rememeber ! OLD is a standard PostgreSQL parameter denoting the row
    -- we're about to delete

    IF OLD.{2} IS NULL THEN
        -- we tolerate null value
        RETURN NULL;
    END IF;

    -- The following select is done only to lock the gseq row.
    -- The consequence of this is that all inserts will be delayed
    -- and, consequently, the following three selects (max_id,min_id,count)
    -- will be reliable. That is, they will concern the result of
    -- the DELETE statement *only* (ie not mixed with inserts).
    -- Moreover, since the UPDATE don't allow any change of
    -- accouting label, the UPDATE won't interfere with the next 3
    -- selects either.

    SELECT INTO n gseq_value FROM {0}.gapless_seq WHERE gseq_name = '{2}' FOR UPDATE;
    SELECT min({2}) INTO min_id FROM {1};
    SELECT max({2}) INTO max_id FROM {1};
    SELECT count(*) INTO cnt    FROM {1};


    IF cnt > 0 AND (max_id - min_id + 1)  <> cnt THEN
        -- Pay attention, the condition above is incomplete because it allows
        -- delete of either first row or last row

        RAISE EXCEPTION 'Gapless sequence has been broken in {1}.{2}';
    ELSE
        -- We allow a DELETE on the last order. Everything else
        -- will trigger an exception.

        IF OLD.{2} = n THEN
            UPDATE {0}.gapless_seq SET gseq_value = n - 1 WHERE gseq_name = '{2}';
            RETURN NULL;
        ELSE
            RAISE EXCEPTION 'One can only delete the last {1}.{2}';
        END IF;

    END IF;
END;
$$ LANGUAGE plpgsql;""".format(schema, table, gapless_seq_name, func_base_name))


    session().connection().execute("""CREATE FUNCTION {0}.check_control_{3}_gapless_sequence_update() RETURNS trigger AS $$
DECLARE
    cnt NUMERIC;
BEGIN
    IF (OLD.{2} IS NOT NULL) AND (NEW.{2} IS NULL OR NEW.{2} <> OLD.{2}) THEN
        RAISE EXCEPTION 'Once set, the {1}.{2} cannot be updated';
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;""".format(schema, table, gapless_seq_name, func_base_name))



    session().connection().execute("""CREATE TRIGGER control_{3}_delete
    AFTER DELETE ON {1} FOR EACH ROW EXECUTE PROCEDURE {0}.check_control_{3}_gapless_sequence_delete()""".format(schema, table, seq_field, func_base_name))

    session().connection().execute("""CREATE TRIGGER control_{3}_insert
    AFTER INSERT ON {1} FOR EACH ROW EXECUTE PROCEDURE {0}.check_control_{3}_gapless_sequence_insert()""".format(schema, table, seq_field, func_base_name))

    session().connection().execute("""CREATE TRIGGER control_{3}_update
    BEFORE UPDATE ON {1} FOR EACH ROW EXECUTE PROCEDURE {0}.check_control_{3}_gapless_sequence_update()""".format(schema, table, seq_field, func_base_name))

    session().connection().execute("DELETE FROM {}.gapless_seq WHERE gseq_name='{}'".format(schema,seq_field))
    session().connection().execute("INSERT INTO {}.gapless_seq VALUES('{}', '0')".format(schema,seq_field))

    session().connection().execute("COMMIT")
