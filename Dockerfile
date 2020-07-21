FROM python:3.8-slim

COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -r requirements.txt
COPY . /app

ENTRYPOINT ["python", "list_lambdas.py"]
CMD ["--help"]