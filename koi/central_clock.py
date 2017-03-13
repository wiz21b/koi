from datetime import datetime


class CentralClock:
    def __init__(self):
        self._now = datetime.now

    def set_now_function(self, the_now):
        assert the_now
        assert isinstance( the_now(), datetime), "expected datetime, you gave {}".format(type(the_now()))
        self._now = the_now

    def now(self):
        return self._now()

    def today(self):
        return self._now().date()


central_clock = CentralClock()
