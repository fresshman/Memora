# -*- coding: utf-8 -*-
"""单端口静态托管测试：构建 web/out 后，FastAPI 同源提供前端且不抢占 /api。

仅在已构建静态前端（web/out 存在）时生效，否则整体跳过。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app, _WEB_OUT

pytestmark = pytest.mark.skipif(
    not (_WEB_OUT / "index.html").exists(),
    reason="未构建静态前端 web/out，跳过单端口托管测试",
)

client = TestClient(app)


def test_index_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<!doctype html" in resp.text.lower() or "<html" in resp.text.lower()


def test_client_route_directory():
    resp = client.get("/qa/", follow_redirects=False)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_client_route_redirects_without_slash():
    resp = client.get("/qa", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"].endswith("/qa/")


def test_api_routes_take_precedence_over_static_mount():
    # /api 必须先于根静态挂载命中；粘贴解析 + 脱敏不依赖模型
    resp = client.post("/api/conversations/paste",
                       json={"text": "甲：你好"})
    assert resp.status_code == 200
    assert "session_id" in resp.json()


def test_unknown_path_404():
    resp = client.get("/definitely-not-a-page-xyz/")
    assert resp.status_code == 404
