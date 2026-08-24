FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1
EXPOSE 18765
CMD ["ecos-mcp"]
