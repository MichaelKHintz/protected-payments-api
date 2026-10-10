"""Uvicorn's h11 HTTP protocol, extended to hand the verified client certificate to the app.

Uvicorn verifies the client certificate during the TLS handshake (ssl_cert_reqs=CERT_REQUIRED)
but doesn't put it in the ASGI scope, so the app can't tell *which* service is calling.
This subclass adds it as scope["extensions"]["tls"]["peer_cert"] for every request on the connection.
"""
from uvicorn.protocols.http.h11_impl import H11Protocol


class ClientCertH11Protocol(H11Protocol):
    def connection_made(self, transport):
        super().connection_made(transport)
        ssl_object = transport.get_extra_info("ssl_object")
        peer_cert = ssl_object.getpeercert() if ssl_object is not None else None
        inner_app = self.app

        async def app_with_peer_cert(scope, receive, send):
            scope.setdefault("extensions", {})["tls"] = {"peer_cert": peer_cert}
            await inner_app(scope, receive, send)

        self.app = app_with_peer_cert
