FROM python:3.12-slim

WORKDIR /app
COPY reconcile.py /app/reconcile.py
RUN chmod +x /app/reconcile.py

# Keep the task container alive so Harbor can execute the agent and verifier.
CMD ["bash"]
