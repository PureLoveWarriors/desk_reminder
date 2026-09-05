"""Database first-run sample seeding."""
import tempfile
import unittest
from pathlib import Path

from app.core.db import SAMPLE_TITLES, Database


class SeedSampleTasksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "reminder.db")

    def tearDown(self):
        self.db.conn.close()
        self._tmp.cleanup()

    def test_empty_db_gets_three_samples(self):
        created = self.db.seed_sample_tasks()
        self.assertEqual([t.title for t in created], list(SAMPLE_TITLES))
        self.assertEqual(len(SAMPLE_TITLES), 3)
        todo = [t.title for t in self.db.list_tasks(done=False)]
        self.assertEqual(todo, list(SAMPLE_TITLES))

    def test_existing_tasks_are_not_replaced(self):
        self.db.add_task("我自己的任务")
        self.assertEqual(self.db.seed_sample_tasks(), [])
        titles = [t.title for t in self.db.list_tasks()]
        self.assertEqual(titles, ["我自己的任务"])


if __name__ == "__main__":
    unittest.main()
