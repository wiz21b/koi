# This came from
# https://gist.github.com/mgrandi/0cf9e603135eda176534

# for NAME and DISPLAY_NAME, the '%s' is replaced whatever you pass to <service.exe> --install NAMEHERE, so you can
# register the same exe multiple times with different names and configuration files
NAME = '%s' # what the name of the service is, used in command line things like "sc"
DISPLAY_NAME = 'Koi Service - %s' # display name of the service, this is what you see in the "Services" window
MODULE_NAME = 'koi.server.service' # python file containing the actual service code
CLASS_NAME = 'Handler' # class name of the service, since it doesn't extend anything, all it needs are certain methods
DESCRIPTION = 'Koi web server service' # description of the service, seen in the Service Properties window
AUTO_START = True # does the service auto start?

# does the service respond to session changes? Setting this to True and implemnting SessionChanged(sessionId, eventType)
# is the only way to respond to things like Shutdown. See 
# https://msdn.microsoft.com/en-us/library/windows/desktop/ms683241%28v=vs.85%29.aspx for the event types
SESSION_CHANGES = False 