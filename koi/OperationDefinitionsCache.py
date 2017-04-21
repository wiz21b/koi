from datetime import date
from sqlalchemy import event
from koi.Configurator import mainlog
from koi.dao import dao
from koi.db_mapping import OperationDefinition, OperationDefinitionPeriod


class OperationDefinitionCache(object):
    def __init__(self):
        self._opdefs = None
        self._opdefs_periods = dict()
        self._current_day = date.today()
        self._cache_needs_refresh = False

        event.listen(OperationDefinition, 'after_insert', self._reload_on_sqla_event)
        event.listen(OperationDefinition, 'after_update', self._reload_on_sqla_event)
        event.listen(OperationDefinition, 'after_delete', self._reload_on_sqla_event)

        event.listen(OperationDefinitionPeriod, 'after_insert', self._reload_on_sqla_event)
        event.listen(OperationDefinitionPeriod, 'after_update', self._reload_on_sqla_event)
        event.listen(OperationDefinitionPeriod, 'after_delete', self._reload_on_sqla_event)

    def _reload_on_sqla_event(self, mapper, connection, target):
        # Pay attention ! This is a method called by SQLA's events system.
        # So you shall not play with the session here... (esp. no commit)
        # Moreover, according to my tests, after an insert, trying to load
        # an object won't work. That is if you insert A, then qurying for A
        # here won't work... So I revert to a delayed refresh.

        self._cache_needs_refresh = True

    def all_on_order_part(self, commit=True):
        if not self._opdefs:
            self._opdefs =  dao.operation_definition_dao.all_on_order_part( commit)
            for opdef in self._opdefs:
                self._opdefs_periods[opdef.operation_definition_id] = opdef.periods

        return self._opdefs

    def refresh(self):
        self.set_on_day( self._current_day)

    def set_on_day(self, d, commit=True):
        self._cache = dict()
        self._cost_cache = dict()
        self._imputable_cache = dict()

        for op in self.all_on_order_part(commit=commit):
            self._cache[op.operation_definition_id] = op

            cost_on_date = 0
            for p in self._opdefs_periods[op.operation_definition_id]:
                if (not p.end_date and d >= p.start_date) or \
                    (p.end_date and p.start_date <= d <= p.end_date):
                    cost_on_date = p.cost
                    break

            self._cost_cache[op.operation_definition_id] = cost_on_date
            self._imputable_cache[op.operation_definition_id] = op.imputable

        if not self._cache:
            mainlog.debug("set_on_day : refreshed cache on {}, but not op def was found".format(d))
        else:
            mainlog.debug("set_on_day : refreshed cache on {}, {} op def were found".format(d, len(self._cache)))
            mainlog.debug("set_on_day : opdef id's in cache are {}".format([k for k in self._cache.keys()]))

        self._cache_needs_refresh = False

    def _refresh_if_needed(self):
        if  self._cache_needs_refresh:
            self.set_on_day(self._current_day, commit=False)

    def opdef_by_id(self,identifier):
        # I allow to return none because at any point in time
        # someone can delete an operation and thus the GUI
        # might be de-synchronized from this cache.

        self._refresh_if_needed()
        if identifier in self._cache:
            return self._cache[identifier]
        else:
            return None

    def cost_by_id(self,identifier):
        self._refresh_if_needed()
        if identifier in self._cost_cache:
            return self._cost_cache[identifier]
        else:
            return 0

    def imputable_by_id(self,identifier):
        self._refresh_if_needed()
        if identifier in self._imputable_cache:
            # mainlog.debug("OperationDefinitionCache.imputable_by_id {} => {}".format(identifier, self._imputable_cache[identifier]))
            return self._imputable_cache[identifier]
        else:
            return False


operation_definition_cache = OperationDefinitionCache()
