class DBObjectActionTypes(object):
    TO_CREATE = "TO_CREATE"
    TO_UPDATE = "TO_UPDATE"
    TO_DELETE = "TO_DELETE" # The object must be destroyed
    UNCHANGED = "UNCHANGED"
    # CLEARED   = "CLEARED"   # The fields were cleared but no object shall be detroyed (there was no object tied to the fields)
