# Support agent harness image. It holds only the generic tool loop and its
# dependencies. Prompts, tools, model and policy arrive at runtime from the
# promoted agent bundle, so most agent changes don't need a new image.
FROM python:3.12-slim

RUN pip install --no-cache-dir anthropic==2.3.0 pyyaml==6.0.3

# The OpenShell supervisor replaces CMD and runs the workload as the sandbox
# user. The image only needs the harness at a path that policy.yaml makes
# readable (/app) and a writable workdir (/sandbox).
RUN install -d -m 0777 /sandbox
COPY agent.py /app/agent.py
WORKDIR /sandbox
