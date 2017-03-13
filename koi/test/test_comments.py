import unittest
from unittest import skip
import logging

import datetime
from datetime import date
import hashlib
from collections import OrderedDict
from sqlalchemy.sql.expression import desc

from koi.test.test_base import TestBase
from koi.db_mapping import *
from koi.datalayer.quality import Comment, QualityEvent, CommentLocation
from koi.dao import *
from koi.Configurator import mainlog

class TestComments(TestBase):


    def test_insert_and_delete(self):

        qe = QualityEvent()
        qe.when = datetime.now()
        qe.who_id = self.employee_id
        session().add(qe)

        # location = CommentLocation()
        # location.quality_event = qe
        # session().add(location)

        session().flush() # necessary to get the id's

        c = Comment()
        c.text = "zulu"
        c.creation = datetime.now()
        c.who_id = self.employee_id
        c.location_id = qe.location.comment_location_id
        session().add(c)

        c2 = Comment()
        c2.text = "zulu2"
        c2.creation = datetime.now() + timedelta(1)
        c2.who_id = self.employee_id
        c2.location_id = qe.location.comment_location_id
        session().add(c2)

        session().commit()

        self.assertEqual("zulu",qe.comments[0].text,"Relationship through association table")
        self.assertEqual("zulu2",qe.comments[1].text,"Relationship through association table")

        session().delete(qe)
        session().commit()

        self.assertEqual(0, session().query(CommentLocation).count(), "CommentLocation should be cascade-deleted")
        self.assertEqual(0, session().query(Comment).count(), "Comment should be cascade-deleted")


if __name__ == '__main__':
    unittest.main()
