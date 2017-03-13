class Task:
    
    # A task where the workflow ends
    EndTask = 1
    
    # A task that will run its children in sequence
    SequenceTask = 2
    
    # A task that will run its children in parallel
    ParallelTask = 2
    
    def __init__(self,name,type,children):
        self.name = name
        self.type = type
        
    # What to do once this task is executed
    # A task can lock progress if it says it is its own successor
    # If a task has several 'next' it means those next's will be executed in parallel
    def next(self):
        pass
    
    # What this task really does on its own
    def execute(self):
        pass
                    

class Executor:
    def __init__(self):
        self.executeList = []
    
    def execute(self,task):
        
        newTasks = []
        
        # Execute all the task in the sequence list
        for t in self.executeList:
            t.execute()            
            newTasks.append(t.next())
            
        self.executeList = newTasks
        
        