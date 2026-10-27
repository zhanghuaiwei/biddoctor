"""embed 桩：块向量化（智谱 embedding-3, dimensions=1024）见 02 §5——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


# TODO(M1) handler 编排职责（向量化见 02 §5）：
#   1. 取未向量化 doc_blocks 分批调 embedding（tier=light 通道，llm_calls 记账 purpose=embed）；
#   2. 写回 embedding 列（pgvector，EMBED_DIM=1024）→ document.embedding_status=done；
#   3. 空文档（无块）→ SKIPPED；仅 bid 文档必须向量就绪（对照检索前置）。
def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:embed")
