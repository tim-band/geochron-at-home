FROM python:3.9.1-alpine3.12

WORKDIR /code
COPY manage.py .
COPY requirements.txt .
COPY templates templates
COPY geochron geochron
COPY ftc ftc

# the following flags make gunicorn work better in a container:
# --worker-tmp-dir /dev/shm --threads=4 --worker-class=gthread --log-file=- -b 0.0.0.0:80
CMD gunicorn --worker-tmp-dir /dev/shm --threads=4 --worker-class=gthread --log-file=- -b 0.0.0.0:80 --workers=2 geochron.wsgi
