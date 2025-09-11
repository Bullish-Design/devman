{% if use_docker %}
FROM python:{ '{ python_version }' }-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

# Default command varies by template; see docker-compose.yml
CMD ["python", "-V"]
{% endif %}
