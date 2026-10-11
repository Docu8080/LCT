FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FSP_DATABASE=/data/fsp.sqlite3
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY server.py assessment.py matching.py resume.py ./
COPY static ./static
COPY fonts ./fonts
RUN useradd --system --uid 10001 talent && mkdir /data && chown talent /data
USER talent
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]

