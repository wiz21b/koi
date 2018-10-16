from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Numeric

DATABASE_SCHEMA = 'horse'
metadata = MetaData(schema=DATABASE_SCHEMA)
Base = declarative_base(metadata=metadata)
MoneyType = Numeric(precision=13, scale=4, asdecimal=True) # Scale = integer digits + precision
