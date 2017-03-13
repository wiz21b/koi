class DataException(Exception):

    IMPROPER_STATE_TRANSITION = 1
    TOO_MANY_RESULTS = 2
    CRITERIA_IS_EMPTY = 3
    CRITERIA_IS_TOO_SHORT = 4
    CRITERIA_IS_TOO_LONG = 7
    CANNOT_DELETE_WHEN_OPERATIONS_PRESENT = 5
    INVALID_PK = 6
    

    def __init__(self,msg,code=None):
        if type(msg) == int and code is None:
            self.code = msg
            msg = ""
        else:
            self.code = code

        super(DataException,self).__init__(msg)
