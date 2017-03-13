from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.orm import relationship


engine = create_engine('sqlite:///:memory:', echo=True)
Session = sessionmaker(bind=engine) 
metadata = MetaData() 

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    description = Column(String)
    
    # Task for which this task is a child
    parent_id = Column(Integer, ForeignKey("Task.id"))
    
    # Task for which this task is a parent
    child_id = Column(Integer, ForeignKey("Task.id"))
    
    #       A
    # B(a,d) C(a,d)
    # E(b)  D
    
    # descr ID parent_id child_id
    # A     1  null      null
    # B     2  1         4
    # C     3  1         4
    # D     4  null      null
    # E     5  2         null
    
    # Les tasks qui precedent (parentes de) celle-ci sont celles qui l'ont pour enfant
    previous_tasks = relationship("Task",primaryjoin="Task.child_id",remote_side="Task.child_id")
    
    # Les tasks qui suivent celle-ci sont celles qui l'ont pour parent
    next_tasks = relationship("Task",remote_side=parent_id)



t = Task()
t.description = "jsdsdf"
t.save()
