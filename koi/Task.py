from datetime import datetime
import sys
if sys.version[0] == '3':
    import xmlrpc.client as xmlrpclib
else:
    import xmlrpclib


class TimeClockTask(object):
    """ A task where for which time can be tracked.
    """

    def __init__(self):
        pass

    @classmethod
    def from_hash(cls,hash):
        tct = TimeClockTask()

        tct.identifier = int(hash['identifier'])
        tct.version_id = int(hash['version_id'])
        tct.name = hash['name']
        tct.client_name = hash['client_name']
        tct.user_id = hash['preferred_user']
        tct.started = False
        tct.timetrack = []
        tct.order_id = hash['order_id']

        return tct

# Bhundu boys

class ServerConnector(object):
    def __init__(self, url):
        self.server = None
        self.server_url = server_url
        self.server_error = False # True if the last call to server failed

    def server_up(self):
        return not self.server_error


    def load_task(self, task_identifier):
        self._connect_server()
        try:
            self.server_error = False
            pass
        except Exception as e:
            self._fail_server_connection()
            raise e


    def record_pointage(self,p):
        """ Will save a pointage to the server. If anything goes wrong,
        the pointage will be saved later (we'll try again)
        """
        self._connect_server()
        try:
            self.server.recordPointage(p.task.identifier,p.user.identifier,p.start_stop,datetime.now())
            self.server_error = False
        except Exception as e:
            self._fail_server_connection()
            raise e


    def _connect_server(self):
        if not self.server:
            self.server = xmlrpclib.ServerProxy(self.server_url, verbose=True)

    def _fail_server_connection(self):
        self.server = None
        self.server_error = True


class Pointage: # TimeClockRecord
    def __init__(self,user, start_stop, task,when = datetime.now()):
        self.user = user
        self.task = task
        self.start_stop = start_stop
        self.when = when

    def to_hash(self):
        h = {}
        h['user'] = self.user.identifier
        h['task'] = self.task.identifier
        h['type'] = self.start_stop
        h['time'] = self.when
        return h

    def __repr__(self):
        return "{} {} {}".format(self.when, self.task.name, self.start_stop)


class TaskService(object):
    def __init__(self,connector):
        self.connector = connector

        # Here we store all the tasks we know about. This is a cache
        # from the database. Therefore one has to be very cautions
        # about synchronisation issues...

        self.tasks = {}

    def load_task(self,identifier):
        """ We assume the identifier is actually tied to a task, that is
        There's no such things as an identifier not linked to a Task.
        """

        t = None
        try:
            # Try to load or update the task data
            t = self.connector.load_task(identifier)

        except Exception as e:
            # Loading failed, we check our cache
            if self.tasks.has_key(identifier):
                # Give back our cache value

                # FIXME Without proper versioning, there's no guarantee
                # we're in sync with the server at this point
                # However, handling that kind of situation might be
                # useless in real world and will surely be quite
                # complicated

                return self.tasks[identifier]
            else:
                raise e

        if t is not None:
            self.tasks[identifier] = t
            return self.tasks[identifier]
        else:
            raise "Task with identifier {} doesn't exist".format(identifier)


class PointageService(object):
    def __init__(self,connector):
        self.connector = connector
        self.queue = []

    def send_later(self,p):
        self.queue.append(p)

    def save(self,p):
        """ Will save a pointage to the server. If anything goes wrong,
        the pointage will be saved later (we'll try again)
        """

        try:
            self.connector.record_pointage(p)

            # If there's anything left in the queue, we try to send it
            while len(queue) > 0:
                p = self.queue[-1] # Last one, I'll remove it only if it is successfully sent to the server
                self.connector.record_pointage(p)
                self.queue.pop()

        except Exception as e:
            self.send_later(p)
            raise e



class TaskPointage:
    def __init__(self,identifier,name,client_name,order_id, preferred_user = None):
        self.identifier = int(identifier)
        self.name = name
        self.client_name = client_name
        self.user_id = preferred_user
        self.started = False
        self.timetrack = []
        self.order_id = order_id

    def start_stop(self,user):
        if self.started:
            self.started = False
        else:
            self.started = True

        self.timetrack.append( Pointage(user, self.started, self) )

    @classmethod
    def from_hash(cls,hash):
        u = TaskPointage(hash['identifier'],hash['name'],hash['client_name'],hash['order_id'],hash['user_id'])
        #for k,v in hash.iteritems():
        #       setattr(u,k,v)
        return u

    def __repr__(self):
        return "TASK: {} {}".format(self.identifier,self.name)



class TaskSet:
    def __init__(self, server_url,logger):
        self.server_url = server_url
        self.logger = logger
        self.tasks = dict()
        self.reload()


    def export_timetracks(self):
        try:
            # For some reason, if the server proxy fails once at connection
            # it will fail forever. Therefore, in case of error, I have
            # to recreate it so that it forgets the failure.

            self.server = xmlrpclib.ServerProxy(self.server_url, verbose=True)
            for task in self.tasks.values():
                for t in task.timetrack:
                    # print "Sending pointage to server"
                    # print "task id = {}".format(t.task.identifier)
                    # print "user id = {}".format(t.user.identifier)
                    # print "datetime = {}".format(datetime.now())

                    self.server.recordPointage(t.task.identifier,t.user.identifier,1,datetime.now())
                task.timetrack = []
            #print "Finished"

        except Exception as e:
            self.logger.error(1,"Unable to contact the data server")


    def reload(self):
        tasks = None
        return

        try:
            # For some reason, if the server proxy fails once
            # it will fail forever. Therefore, in case of error, I have
            # to recreate it so that it forgets the failure.

            self.server = xmlrpclib.ServerProxy(self.server_url)
            tasks = self.server.tasksInformation()

        except Exception as e:
            self.logger.error(1,"Unable to contact the data server")

        # Make sure we don't destroy our current tasks list if the one we've
        # requested never came.

        if tasks is not None:
            for u in tasks:
                u = TaskPointage.from_hash(u)

                if u.identifier not in self.tasks:
                    self.tasks[u.identifier] = u

    def find(self,task_id):

        # Warning ! We assume all of this is atomic with respect to
        # reload()

        if self.tasks is not None:
            return self.tasks[task_id]
        else:
            return None

    def tasks_for_user(self, user_id):
        if self.tasks is not None:
            return list( filter( lambda t: t.user_id == user_id, self.tasks.values()))
        else:
            return None
