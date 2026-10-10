# syntax=docker/dockerfile:1
#checkov:skip=CKV_DOCKER_2:Kubernetes ignores Docker HEALTHCHECK; the Deployment defines readiness and liveness probes.
# Build stage: install dependencies. Its Python minor version (3.13) must match the runtime image.
FROM python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --target /install -r requirements.txt
COPY app/ app/

# Runtime: distroless (no shell, no package manager), runs as the built-in nonroot user (65532).
FROM gcr.io/distroless/python3-debian13:nonroot@sha256:83aa8d4f74a4d7f7cf2d472054139bef71a927b76c680c0f2e1021d6b1d6d732
WORKDIR /app
COPY --from=build /install /install
COPY --from=build /src/app /app/app
ENV PYTHONPATH=/install \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 65532:65532
ENTRYPOINT ["/usr/bin/python3", "-m", "app.serve"]
