FROM python:3.12
WORKDIR /code


ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN pip install --upgrade pip

RUN git clone --single-branch -b service-a https://github.com/sshumikhin/RTK-test.git

WORKDIR /code/RTK-test

RUN pip install --no-cache-dir --upgrade -r requirements.txt