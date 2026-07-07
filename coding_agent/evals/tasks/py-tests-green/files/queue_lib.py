class BoundedQueue:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = []

    def push(self, x):
        if len(self.items) > self.capacity:   # bug: allows capacity+1 items
            raise OverflowError("queue full")
        self.items.append(x)

    def pop(self):
        return self.items.pop()               # bug: LIFO, should be FIFO
