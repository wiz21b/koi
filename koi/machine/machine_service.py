from sqlalchemy import and_

from koi.datalayer.database_session import session
from koi.datalayer.RollbackDecorator import RollbackDecorator
from koi.db_mapping import OperationDefinition
from koi.machine.machine_mapping import *
from koi.server.json_decorator import ServerException, ServerErrors

class MachineService(object):
    def __init__(self):
        self._cache = None
        self._cache_by_id = None

        # Don't load the cache here because it will be loaded
        # as soon as the instance is created, and that can
        # be before the DB is actually created (this will happen
        # in the tests

    @RollbackDecorator
    def all_machines(self):
        machines = session().query(Machine.resource_id,
                                   Machine.operation_definition_id,
                                   Machine.is_active,
                                   Machine.clock_zone,
                                   OperationDefinition.short_id.label("operation_short_id"),
                                   Machine.fullname).\
            join(OperationDefinition).\
            filter(and_(
                Machine.is_active == True,
                Machine.operation_definition_id != None)).order_by(Machine.fullname).all()
        session().commit()
        return machines


    @RollbackDecorator
    def find_machine_by_id(self, machine_id):
        if self._cache_by_id == None:
            self._reset_cache()

        if machine_id in self._cache_by_id:
            return self._cache_by_id[machine_id]
        else:
            raise ServerException(ServerErrors.unknown_machine, machine_id)

    @RollbackDecorator
    def find_machines_for_operation_definition(self, operation_definition_id):
        mainlog.debug("find_machines_for_operation_definition : op def id = {}".format(operation_definition_id))

        if self._cache_by_id == None:
            self._reset_cache()

        if operation_definition_id in self._cache:
            return self._cache[operation_definition_id]
        else:
            return []


    def _reset_cache(self):
        # The check on Machine.operation_definition_id
        # is to protect from some data quality issues
        # I still have to think about what a machine without
        # an operation definition is...

        machines = session().query(Machine.machine_id,
                                   Machine.resource_id,
                                   Machine.operation_definition_id,
                                   Machine.clock_zone,
                                   Machine.fullname).filter(and_(
                                       Machine.is_active == True,
                                       Machine.operation_definition_id != None)).all()

        self._cache = dict()
        self._cache_by_id = dict()

        for m in machines:
            self._cache_by_id[m.machine_id] = m

            if m.operation_definition_id not in self._cache:
                self._cache[m.operation_definition_id] = []

            # mainlog.debug(u"machine cache, loading {} -> {}".format(m.operation_definition_id, m.fullname))
            self._cache[m.operation_definition_id].append(m)


machine_service = MachineService()
