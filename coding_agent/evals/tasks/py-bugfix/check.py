import sys
sys.path.insert(0, ".")
from stats import last_n, mean
assert last_n([1, 2, 3, 4], 2) == [3, 4], last_n([1, 2, 3, 4], 2)
assert last_n([1], 1) == [1]
assert mean([2, 4]) == 3.0          # must not break the neighbor
print("ok")
