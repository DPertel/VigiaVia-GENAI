import json
from app.core import KB, parse_json, refusal, answer
from app.main import app
from fastapi.testclient import TestClient

def test_documents_have_traceable_sources():
    assert len(KB.docs) >= 10
    assert all(d.get("url") and d.get("id") and d.get("licenca") for d in KB.docs)
    assert len(set(d["id"] for d in KB.docs)) == len(KB.docs)

def test_retrieval_returns_scores():
    rows = KB.search("Qual o mAP@0,5 do detector YOLO26n?")
    assert len(rows) == 3
    assert all(0 <= d["score"] <= 1 for d in rows)

def test_refusal_is_json_compliant():
    result = refusal("agente")
    assert json.loads(json.dumps(result))["recusa"]

def test_unparseable_json_rejected():
    assert parse_json("isso não é json") == {}

def test_no_model_call_when_no_docs_pass_threshold(monkeypatch):
    monkeypatch.setattr("app.core.generate", lambda _: (_ for _ in ()).throw(AssertionError("não chamar")))
    result = answer("assunto inexistente", "agente", threshold=1.1)
    assert result["recusa"]

def test_api_health_and_search():
    client = TestClient(app)
    assert client.get("/health").json()["trechos"] >= 10
    assert len(client.get("/api/buscar", params={"q":"buraco"}).json()["resultados"]) == 3

def test_api_invalid_mode():
    client = TestClient(app)
    assert client.post("/api/perguntar", json={"pergunta":"O que é?", "configuracao":"desconhecido"}).status_code == 400
