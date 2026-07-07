import unittest
from queue_lib import BoundedQueue


class TestBoundedQueue(unittest.TestCase):
    def test_fifo_order(self):
        q = BoundedQueue(3)
        q.push(1); q.push(2)
        self.assertEqual(q.pop(), 1)
        self.assertEqual(q.pop(), 2)

    def test_capacity_enforced(self):
        q = BoundedQueue(2)
        q.push(1); q.push(2)
        with self.assertRaises(OverflowError):
            q.push(3)


if __name__ == "__main__":
    unittest.main()
