from datetime import date
from sqlalchemy import event
from koi.Configurator import mainlog
from koi.dao import dao
from koi.db_mapping import OperationDefinition


class OperationDefinitionCache(object):
    def __init__(self):
        self._opdefs = None
        self._opdefs_periods = dict()
        self._current_day = date.today()

        event.listen(OperationDefinition, 'after_insert', self._reload)
        event.listen(OperationDefinition, 'after_update', self._reload)
        event.listen(OperationDefinition, 'after_delete', self._reload)

    def _reload(self, mapper, connection, target):
        self.set_on_day( self._current_day)

        # self._opdefs =  dao.operation_definition_dao.all_on_order_part()
        # for opdef in self._opdefs:
        #     self._opdefs_periods[opdef.operation_definition_id] = opdef.periods
        # return
        #
        # # Dependecies (periods) first, then top object (opdef),
        # # else expunge will cause problems.
        #
        # for opdef in all_opdef:
        #     self._opdefs_periods[opdef.operation_definition_id] = freeze2(opdef.periods)
        # self._opdefs = freeze2(all_opdef)
        #
        # session().commit()
        #
        # self.refresh(date.today())

    def all_on_order_part(self):
        if not self._opdefs:
            self._opdefs =  dao.operation_definition_dao.all_on_order_part()
            for opdef in self._opdefs:
                self._opdefs_periods[opdef.operation_definition_id] = opdef.periods

        return self._opdefs

    def set_on_day(self, d):
        self._cache = dict()
        self._cost_cache = dict()
        self._imputable_cache = dict()

        for op in self.all_on_order_part():
            self._cache[op.operation_definition_id] = op

            cost_on_date = 0
            for p in self._opdefs_periods[op.operation_definition_id]:
                if (not p.end_date and d >= p.start_date) or \
                    (p.end_date and p.start_date <= d <= p.end_date):
                    cost_on_date = p.cost
                    break

            self._cost_cache[op.operation_definition_id] = cost_on_date
            self._imputable_cache[op.operation_definition_id] = op.imputable

    def opdef_by_id(self,identifier):
        # I allow to return none because at any point in time
        # someone can delete an operation and thus the GUI
        # might be de-synchronized from this cache.

        if identifier in self._cache:
            return self._cache[identifier]
        else:
            return None

    def cost_by_id(self,identifier):
        if identifier in self._cost_cache:
            return self._cost_cache[identifier]
        else:
            return 0

    def imputable_by_id(self,identifier):
        if identifier in self._imputable_cache:
            # mainlog.debug("OperationDefinitionCache.imputable_by_id {} => {}".format(identifier, self._imputable_cache[identifier]))
            return self._imputable_cache[identifier]
        else:
            return False


operation_definition_cache = OperationDefinitionCache()
