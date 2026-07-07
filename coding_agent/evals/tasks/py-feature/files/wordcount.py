import sys


def count_words(path):
    with open(path) as f:
        return len(f.read().split())


if __name__ == "__main__":
    print(count_words(sys.argv[1]))
