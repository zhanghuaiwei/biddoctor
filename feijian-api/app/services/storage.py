"""存储抽象（01·D2/D7：二期换 OSS/S3 时实现同接口替换，不改业务代码）。

约定（skill: biddoctor-engineering）：新增存储后端必须实现 Storage 协议，
save() 返回 (sha256, stored_path)，路径不可猜测（内容寻址），天然幂等。
"""

import hashlib
import os
import shutil
from typing import Protocol


class Storage(Protocol):
    def save(self, data: bytes, ext: str = "pdf") -> tuple[str, str]:
        """保存内容，返回 (sha256, 存储路径)。"""
        ...

    def disk_free_mb(self) -> float: ...


class LocalStorage:
    """本地磁盘实现：sha256 前两级目录寻址防遍历（04 §5）。"""

    def __init__(self, root: str):
        self.root = root

    def save(self, data: bytes, ext: str = "pdf") -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        rel = os.path.join(sha[:2], sha[2:4], f"{sha}.{ext}")
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):  # sha 寻址天然幂等
            with open(path, "wb") as f:
                f.write(data)
        return sha, path

    def disk_free_mb(self) -> float:
        usage = shutil.disk_usage(self.root)
        return usage.free / 1024 / 1024
