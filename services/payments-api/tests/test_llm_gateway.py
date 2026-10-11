"""Phase 3: nothing card-shaped or personal leaves the environment, and the audit log stays clean."""
import json

import anthropic
import httpx2  # the Anthropic SDK's HTTP library

from app.config import Settings
from app.llm import Summarizer
from conftest import PAYMENT_BODY, FakeSummarizer, bearer

RAW_NOTES = (
    "Customer Jane called from (512) 555-0142, email jane.doe@example.com. "
    "Says card 4111 1111 1111 1111 exp 12/27 CVV 123 was charged twice for order-1001."
)
SUMMARIZE = bearer("support:summarize")


def test_prompt_is_redacted_before_it_reaches_claude(client, summarizer, caplog):
    caplog.set_level("INFO")
    r = client.post("/v1/support/summary", json={"notes": RAW_NOTES}, headers=SUMMARIZE)
    assert r.status_code == 200
    prompt = summarizer.prompts[0]
    for secret in ("4111 1111 1111 1111", "4111111111111111", "jane.doe@example.com", "555-0142", "12/27", "CVV 123"):
        assert secret not in prompt
        assert secret not in caplog.text  # the audit log holds only the redacted prompt
    assert "[CARD tok_" in prompt and "[EMAIL]" in prompt and "[PHONE]" in prompt
    record = json.loads(next(r.message for r in caplog.records if r.name == "payments-api.llm-audit"))
    assert record["outcome"] == "ok" and record["redactions"]["card"] == 1 and record["input_tokens"] == 42


def test_summary_requires_its_own_scope(client):
    r = client.post("/v1/support/summary", json={"notes": "hello"}, headers=bearer("payments:write", "payments:read"))
    assert r.status_code == 403


def test_notes_are_redacted_before_storage_and_reused(client, summarizer):
    pay = client.post("/v1/payments", json=PAYMENT_BODY, headers=bearer("payments:write")).json()
    stored = client.post(f"/v1/payments/{pay['id']}/notes", json={"text": "Card 5555 5555 5555 4444 declined"},
                         headers=bearer("payments:write")).json()
    assert "5555 5555 5555 4444" not in stored["stored_text"] and "[CARD tok_" in stored["stored_text"]
    r = client.post("/v1/support/summary", json={"payment_id": pay["id"]}, headers=SUMMARIZE)
    assert r.status_code == 200 and "ending 1111" in summarizer.prompts[0]


def test_card_numbers_in_model_output_are_masked(tmp_path):
    from conftest import ISSUER, AUDIENCE, FakeJWKS, fake_vault
    from app.auth import TokenValidator
    from app.main import create_app
    from fastapi.testclient import TestClient
    leaky = FakeSummarizer(reply="The card was 4111111111111111.")
    app = create_app(Settings(db_path=str(tmp_path / "p.db"), oauth_issuer=ISSUER, oauth_audience=AUDIENCE),
                     vault=fake_vault(), validator=TokenValidator(ISSUER, AUDIENCE, jwks_client=FakeJWKS()),
                     summarizer=leaky)
    r = TestClient(app).post("/v1/support/summary", json={"notes": "hi"}, headers=SUMMARIZE)
    assert r.json()["summary"] == "The card was [CARD]."


def test_provider_failure_is_logged_without_content(tmp_path, caplog):
    from conftest import ISSUER, AUDIENCE, FakeJWKS, fake_vault
    from app.auth import TokenValidator
    from app.main import create_app
    from fastapi.testclient import TestClient

    class Broken:
        def summarize(self, text):
            raise TimeoutError("provider timed out")

    caplog.set_level("INFO")
    app = create_app(Settings(db_path=str(tmp_path / "p.db"), oauth_issuer=ISSUER, oauth_audience=AUDIENCE),
                     vault=fake_vault(), validator=TokenValidator(ISSUER, AUDIENCE, jwks_client=FakeJWKS()),
                     summarizer=Broken())
    r = TestClient(app).post("/v1/support/summary", json={"notes": RAW_NOTES}, headers=SUMMARIZE)
    assert r.status_code == 502
    assert '"outcome": "error"' in caplog.text and "4111" not in caplog.text


def test_summarizer_sends_expected_request_shape():
    """Exercise the real Anthropic SDK against a fake Messages API endpoint."""
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get("x-api-key")
        return httpx2.Response(200, headers={"request-id": "req_123"}, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": "Summary text."}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 3},
        })

    sdk = anthropic.Anthropic(api_key="sk-test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    summary = Summarizer(Settings(), client=sdk).summarize("[CARD tok_x] charged twice")
    assert seen["path"] == "/v1/messages" and seen["key"] == "sk-test"
    assert seen["body"]["model"] == "claude-haiku-5-5" and "untrusted data" in seen["body"]["system"]
    assert seen["body"]["messages"][0]["content"].startswith("<notes>")
    assert summary.text == "Summary text." and summary.output_tokens == 3 and summary.provider_request_id == "req_123"
