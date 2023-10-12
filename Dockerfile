FROM python:3.12.0


WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt 

COPY . .

CMD flask run --host 0.0.0.0 --port 5000
