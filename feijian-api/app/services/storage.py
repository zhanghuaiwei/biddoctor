"""本地磁盘存储（01·D2/D7）。二期换 OSS 时实现同接口替换。"""

import hashlib


class LocalStorage:
    def __init__(self, root: str):
        self.root = root

    def save(self, data: bytes, ext: str = "pdf") -> tuple[str, str]:
        """返回 (sha256, stored_path)，按 sha256 前两级目录寻址防遍历"""
        import os

        sha = hashlib.sha256(data).hexdigest()
        rel = os.path.join(sha[:2], sha[2:4], f"{sha}.{ext}")
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):  # sha 寻址天然幂等
            with open(path, "wb") as f:
                f.write(data)
        return sha, path

    def disk_free_mb(self) -> float:
        import shutil

        usage = shutil.disk_usage(self.root)
        return usage.free / 1024 / 1024
