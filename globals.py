import multiprocessing as mp

global lock


def init(rlock=None) -> None:
    global lock
    lock = mp.RLock() if not rlock else rlock
