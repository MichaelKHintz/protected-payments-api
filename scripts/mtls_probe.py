"""Phase 2 failure-case probe. Runs inside a pod, reading this file from stdin:

  kubectl -n payments exec -i mtls-tester  -- python3 - tester <token>    < scripts/mtls_probe.py
  kubectl -n payments exec -i deploy/payments-api -- python3 - payments-api <token> < scripts/mtls_probe.py
  kubectl -n payments exec -i rogue-client -- python3 - rogue             < scripts/mtls_probe.py

Uses only the standard library, so it works in the distroless images.
"""
import json
import ssl
import sys
import urllib.error
import urllib.request

VAULT = "https://token-vault.payments.svc:8443"
TEST_PAN = "4111111111111111"


def call(label, path, body, ca=None, cert=None, key=None):
    context = ssl.create_default_context(cafile=ca) if ca else ssl._create_unverified_context()
    if cert:
        context.load_cert_chain(cert, key)
    request = urllib.request.Request(VAULT + path, data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, context=context, timeout=5) as r:
            result = f"HTTP {r.status} {r.read().decode()}"
    except urllib.error.HTTPError as e:
        result = f"HTTP {e.code} {e.read().decode()}"
    except Exception as e:  # TLS handshake failures and timeouts land here
        result = f"FAILED {type(e).__name__}: {getattr(e, 'reason', e)}"
    print(f"{label:<55} -> {result.replace(TEST_PAN, TEST_PAN[:6] + '******' + TEST_PAN[-4:])}")


mode = sys.argv[1]
token = sys.argv[2] if len(sys.argv) > 2 else "tok_" + "x" * 24

if mode == "tester":
    s = "/var/run/settlement"
    r = "/var/run/rogue"
    call("1. no client certificate", "/v1/tokenize", {"pan": TEST_PAN}, ca=f"{s}/ca.crt")
    call("2. rogue-CA cert claiming to be payments-api", "/v1/tokenize", {"pan": TEST_PAN},
         ca=f"{s}/ca.crt", cert=f"{r}/tls.crt", key=f"{r}/tls.key")
    call("3. settlement-worker tries to tokenize", "/v1/tokenize", {"pan": TEST_PAN},
         ca=f"{s}/ca.crt", cert=f"{s}/tls.crt", key=f"{s}/tls.key")
    call("4. settlement-worker detokenizes (allowed)", "/v1/detokenize", {"token": token},
         ca=f"{s}/ca.crt", cert=f"{s}/tls.crt", key=f"{s}/tls.key")
elif mode == "payments-api":
    t = "/var/run/tls"
    call("5. payments-api tries to detokenize", "/v1/detokenize", {"token": token},
         ca=f"{t}/ca.crt", cert=f"{t}/tls.crt", key=f"{t}/tls.key")
elif mode == "rogue":
    call("6. pod with no NetworkPolicy allowance", "/v1/tokenize", {"pan": TEST_PAN})
