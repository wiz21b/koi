import sys
import traceback
from sqlalchemy.exc import OperationalError
from koi.Configurator import mainlog
from koi.base_logging import log_stacktrace
from koi.datalayer.database_session import session
from koi.datalayer.data_exception import DataException

from koi.utils import SourceFunctionDecorator

class RollbackDecorator(SourceFunctionDecorator):
    """ The rollback decorator makes sure that if a DB operation
    goes wrong then the rollabck is always done. This is important
    because with SQLAlchemy, if a transaction doesn't end with
    a commit or a rollback, then no other DB operation can be
    done until a commit/rollback is successful.

    RollbackDecorator.callback_operational_error is a callback that will be
    called in case a rollback must be done (i.e. in case of something
    wrong happens). But this is called only if an OperationalError occurs
    which happens when things *really* go wrong.
    """

    callback_operational_error = None

    def __call__(self,*args,**kwargs):
        global mainlog
        global session # FIXME That's not right : how can we be sure that's the actual session that has thrown the exception ?

        try:
            r = self.call_decorated(*args,**kwargs)
            # mainlog.debug("RollbackDecorator.__call__ calling with args : {} kwargs :{}".format(args, kwargs))
            # r = super(RollbackDecorator,self).__call__(*args,**kwargs)
            # mainlog.debug("RollbackDecorator.__call__ call complete")
            return r

            # if self.instance:
            #     return self.func(self.instance,*args,**kwargs)
            # else:
            #     return self.func(*args)

        except Exception as e:

            session().rollback()

            if type(e) != DataException:
                # I assume DataException are handled properly

                mainlog.info("Rollback done because of an exception")
                mainlog.exception(str(e))
                log_stacktrace()


            if RollbackDecorator.callback_operational_error is not None and isinstance(e,OperationalError):
                f = RollbackDecorator.callback_operational_error[0]
                f(e)

            raise e

