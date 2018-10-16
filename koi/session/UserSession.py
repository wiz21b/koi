from koi.datalayer.SQLAEnum import EnumSymbol

class UserSession:
    def __init__(self):
        self.invalidate()

    def invalidate(self):
        self._active = False
        self._name = None
        self._user_id = None
        self._roles = set()
        self._login = None

    def is_active(self):
        return self._active

    @property
    def user_id(self):
        """
        :return: User id (as in the DB) of the current user.
        """
        return self._user_id

    @property
    def name(self):
        return self._name

    @property
    def login(self):
        return self._login

    def employee(self):
        return self._employee

    def open(self,employee):
        self._employee = employee
        self._name = employee.fullname
        self._user_id = employee.employee_id
        self._roles = set(employee.roles)
        self._active = True
        self._login = employee.login

    def has_any_roles(self, r):
        """ Verifies that at least one of the passed roles in the session's
        roles.

        Roles are defined in RoleType enumeration.
        """

        if isinstance(r,EnumSymbol):
            r = [r]

        # mainlog.debug("Current roles for {} (active={}) = {}".format(self._name,self._active,self._roles))
        # mainlog.debug("Checked roles = {}".format(set(r)))
        return self._active and len(set(r) & self._roles) > 0

    def __str__(self):
        return "User name: {}, roles:{}".format(self._name, self._roles)


user_session = UserSession()
