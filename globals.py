from multiprocessing import RLock


def init(rlock=None) -> None:
    global lock
    lock = RLock() if not rlock else rlock
