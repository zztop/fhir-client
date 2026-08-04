FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system ".[dev]"

COPY src/ ./src/

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.cli.main"]
