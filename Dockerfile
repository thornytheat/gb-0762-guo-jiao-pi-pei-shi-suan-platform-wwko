FROM python:3.12-slim
WORKDIR /opt/pectin
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PECTIN_ARCHIVE=/var/pectin PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "flask", "--app", "app.main", "run", "--host=0.0.0.0", "--port=8000"]
