"""存储抽象（01·D2/D7：二期换 OSS/S3 时实现同接口替换，不改业务代码）。

约定（skill: smart-bid-doctor-engineering）：新增存储后端必须实现 Storage 协议，
路径不可猜测（sha256 内容寻址），同内容写入天然幂等。
"""

import hashlib
import io
import os
import shutil
import tempfile
from typing import BinaryIO, Protocol


class Storage(Protocol):
    def save(self, data: bytes, ext: str = "pdf") -> tuple[str, str]:
        """保存字节内容，返回 (sha256, 存储路径)。"""
        ...

    def save_stream(self, stream: BinaryIO, sha256: str, ext: str = "pdf") -> str:
        """保存已流式读取并算好 sha256 的内容，返回存储路径。"""
        ...

    def disk_free_mb(self) -> float: ...


class LocalStorage:
    """本地磁盘实现：sha256 前两级目录寻址防遍历（04 §5）。"""

    def __init__(self, root: str):
        self.root = root

    def _path_for(self, sha: str, ext: str) -> str:
        rel = os.path.join(sha[:2], sha[2:4], f"{sha}.{ext}")
        return os.path.join(self.root, rel)

    def save_stream(self, stream: BinaryIO, sha256: str, ext: str = "pdf") -> str:
        """流式落盘：写同目录临时文件后原子 rename，避免半写文件被读到。"""
        path = self._path_for(sha256, ext)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):  # sha 寻址天然幂等
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
            try:
                with os.fdopen(fd, "wb") as f:
                    shutil.copyfileobj(stream, f, length=1024 * 1024)
                os.replace(tmp, path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        return path

    def save(self, data: bytes, ext: str = "pdf") -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        path = self.save_stream(io.BytesIO(data), sha, ext)
        return sha, path

    def disk_free_mb(self) -> float:
        usage = shutil.disk_usage(self.root)
        return usage.free / 1024 / 1024
