"""LLM 链路集成测试（M1/C + M2/E 编排）——需 PostgreSQL（pgvector），无库自动跳过。

- 桩语义：LLM 未接入（NOT_IMPLEMENTED）时 extract 任务 need_review 且 llm_calls
  不落行（桩状态不记账，避免污染成本报表）；
- mock 全链路：monkeypatch _post_chat/_post_embed 后，抽取→向量化→对照→报告
  端到端跑通，断言 check_items/embedding/findings/reports 落库 + llm_calls 记账
  （留痕写入失败会被静默吞掉，本测试是唯一防线，参照 test_auth_security.py 范式）。
"""

import io
import uuid

import fitz

from app.llm.zhipu import ZhipuProvider

_EXTRACT_JSON = '{"items": [{"category": "star", "requirement": "原厂全新", ' \
    '"raw_text": "★1. 投标货物必须原厂全新，未使用过。", "ref_page": 1, ' \
    '"is_mandatory": true, "confidence": 0.95}]}'

_JUDGE_JSON = '{"verdict": "missing", "reason": "投标文件未提供原厂合格证证据", ' \
    '"bid_ref_page": 1, "bid_quote": null, "confidence": 0.7}'


def _email(client, local: str) -> tuple[str, str]:
    email = f"{local}-{uuid.uuid4().hex[:6]}@test.dev"
    code = client.post("/api/auth/email-code", json={"email": email}).json()["dev_code"]
    return email, code


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _drain_tasks(max_rounds: int = 50) -> None:
    """内联任务排空：复用 runner 的 claim SQL 与 HANDLERS（与 platform 集成测试同款）。"""
    from app.core.db import SessionLocal
    from app.worker.runner import CLAIM_SQL, HANDLERS

    for _ in range(max_rounds):
        with SessionLocal() as db:
            row = db.execute(CLAIM_SQL).mappings().first()
        if row is None:
            return
        with SessionLocal() as db:
            HANDLERS[row["type"]](dict(row), db)


def _tender_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "第一章 采购需求", fontsize=18)
    page.insert_text((72, 140), "★1. 投标货物必须原厂全新，未使用过。", fontsize=11)
    pdf = doc.tobytes()
    doc.close()
    return pdf


def _bid_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "投标函", fontsize=18)
    page.insert_text((72, 140), "我方承诺按招标要求供货，供货期 30 日。", fontsize=11)
    pdf = doc.tobytes()
    doc.close()
    return pdf


def _mock_llm(monkeypatch) -> None:
    """mock HTTP 调用点：按 user 内容分流 extract/judge；embed 返回 1024 维向量。"""

    def fake_chat(self, payload):
        user = payload["messages"][-1]["content"]
        content = _JUDGE_JSON if "废标条款" in user else _EXTRACT_JSON
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 60}}

    def fake_embed(self, payload):
        return {"data": [{"index": i, "embedding": [0.01] * 1024}
                         for i in range(len(payload["input"]))]}

    monkeypatch.setattr(ZhipuProvider, "_post_chat", fake_chat)
    monkeypatch.setattr(ZhipuProvider, "_post_embed", fake_embed)


def _make_project(client, h, monkeypatch=None) -> int:
    r = client.post("/api/projects", headers=h, json={"name": "LLM链路项目", "industry": "general"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(client, h, pid: int, role: str, pdf: bytes) -> None:
    r = client.post(
        f"/api/projects/{pid}/documents", headers=h,
        files={"file": (f"{role}.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"role": role},
    )
    assert r.status_code == 201, r.text


def test_extract_stub_need_review(client, user_token, monkeypatch):
    """桩语义：extract need_review + 桩状态不落 llm_calls（不污染成本报表）。"""
    h = _auth(user_token)
    pid = _make_project(client, h)
    _upload(client, h, pid, "tender", _tender_pdf())
    _drain_tasks()

    from app.core.db import SessionLocal
    from app.models import LlmCall, Project, Task

    with SessionLocal() as db:
        t = (
            db.query(Task)
            .filter(Task.project_id == pid, Task.type == "extract")
            .order_by(Task.id.desc())
            .first()
        )
        assert t is not None and t.status == "need_review", t.status
        assert t.error_code == "NOT_IMPLEMENTED"
        p = db.get(Project, pid)
        assert p.status == "tender_parsing"
        assert db.query(LlmCall).filter(LlmCall.project_id == pid).count() == 0


def test_full_chain_with_mocked_llm(client, user_token, monkeypatch):
    """mock LLM 后全链路：抽取落库 → 向量化 → 对照判定 → 报告 + 记账留痕。"""
    _mock_llm(monkeypatch)
    h = _auth(user_token)
    pid = _make_project(client, h)
    _upload(client, h, pid, "tender", _tender_pdf())
    _upload(client, h, pid, "bid", _bid_pdf())
    _drain_tasks()

    from app.core.db import SessionLocal
    from app.models import CheckItem, Document, LlmCall

    with SessionLocal() as db:
        items = db.query(CheckItem).filter(CheckItem.project_id == pid).all()
        assert len(items) == 1 and items[0].code == "STAR-001"
        docs = db.query(Document).filter(Document.project_id == pid).all()
        assert all(d.embedding_status == "done" for d in docs)
        extract_calls = [c for c in db.query(LlmCall).filter(LlmCall.project_id == pid).all()
                         if c.purpose == "extract"]
        assert extract_calls and extract_calls[0].prompt_tokens > 0
        assert extract_calls[0].error is None

    # 发起对照 → drain → done + 报告
    r = client.post(f"/api/projects/{pid}/compare", headers=h)
    assert r.status_code == 202, r.text
    _drain_tasks()

    from app.core.db import SessionLocal
    from app.models import Comparison, Project, Report, Task

    with SessionLocal() as db:
        cmp_ = db.query(Comparison).filter(Comparison.project_id == pid).order_by(Comparison.id.desc()).first()
        assert cmp_ is not None and cmp_.status == "done", cmp_.status
        assert cmp_.stats.get("total") == 1
        rep = db.query(Report).filter(Report.project_id == pid, Report.kind == "comparison").first()
        assert rep is not None
        p = db.get(Project, pid)
        assert p.status == "report_ready"
        t = (
            db.query(Task)
            .filter(Task.project_id == pid, Task.type == "compare")
            .order_by(Task.id.desc())
            .first()
        )
        assert t is not None and t.status == "succeeded"
        judge_calls = [c for c in db.query(LlmCall).filter(LlmCall.project_id == pid).all()
                       if c.purpose == "judge"]
        assert judge_calls, "judge 调用必须落 llm_calls 记账"

    # 用户端可见对照报告
    r = client.get(f"/api/projects/{pid}/reports", headers=h)
    kinds = [x["kind"] for x in r.json()["items"]]
    assert "comparison" in kinds
