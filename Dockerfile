FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup -S compass && adduser -S -G compass -h /app compass
WORKDIR /app

COPY --chown=compass:compass pyproject.toml README_EN.md ./
COPY --chown=compass:compass src ./src
RUN python -m pip install --no-cache-dir .

USER compass
EXPOSE 8788

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8788/api/health', timeout=2).read()"

ENTRYPOINT ["python", "-m", "credential_compass"]
