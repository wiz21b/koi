from koi.Configurator import mainlog

from koi.configuration.business_functions import is_task_imputable_for_admin

class PotentialTasksCache(object):

    def __init__(self,task_dao,base_date):
        self.task_dao = task_dao
        self.base_date = base_date
        self.reset()

    def reset(self):
        self.potential_tasks_cache = dict()

    def tasks_for_identifier(self,obj): # FIXME !!! rename

        """ Returns imputable task corresponding to the given obj.
        If tasks are created before being returned (that's why we say potential)
        then those are *not* added to the session """

        # Note that "None" is an appropriate value. None represents
        # unbillable tasks

        if obj not in self.potential_tasks_cache:
            # mainlog.debug("PotentialTasksCache.tasks_for_obj : cache miss on '{}'!".format(obj))

            # Pay attention ! This is only for administrators !

            self.potential_tasks_cache[obj] = list(
                filter(is_task_imputable_for_admin,
                       self.task_dao.potential_imputable_tasks_for(obj, self.base_date)))
            # self.potential_tasks_cache[obj] = self.task_dao.potential_imputable_tasks_for(obj, self.base_date) # filter(is_task_imputable_for_admin,

            # mainlog.debug("For obj : {}".format(obj))
            # for t in self.potential_tasks_cache[obj]:
            #    mainlog.debug(u"cache has : #{} {}".format(t.task_id,t))
        else:
            mainlog.debug("PotentialTasksCache.tasks_for_obj : cache hit !")

        return self.potential_tasks_cache[obj]
