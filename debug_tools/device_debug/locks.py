"""同一事件循环内，交互部署与批量截图共享设备占用。"""

import asyncio
import hashlib
import os
import weakref
from pathlib import Path

_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_BUILD_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


class DeviceProcessLock:
    """进程退出自动释放的设备文件锁；获取不阻塞事件循环。"""

    def __init__(self, root: Path, serial: str) -> None:
        self.path = root / "locks" / (hashlib.sha256(serial.encode()).hexdigest() + ".lock")
        self.stream = None

    async def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        self.stream = stream
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        try:
            while True:
                stream.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except BlockingIOError:
                    await asyncio.sleep(0.2)
                except OSError as exc:
                    if exc.errno not in (11, 13, 36):
                        raise
                    await asyncio.sleep(0.2)
        except BaseException:
            stream.close()
            self.stream = None
            raise

    def release(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def device_lock(serial: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    locks = _LOCKS.setdefault(loop, {})
    return locks.setdefault(serial, asyncio.Lock())


def build_lock(project: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    locks = _BUILD_LOCKS.setdefault(loop, {})
    return locks.setdefault(project, asyncio.Lock())
