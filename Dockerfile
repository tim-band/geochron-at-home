FROM python:3.10.7-alpine3.16

WORKDIR /code
RUN apk add python3-dev py3-pip postgresql-dev libffi-dev build-base postgresql-client
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY manage.py .
COPY site_init.sh .
COPY upload_projects.py .
COPY site_default_users.py .
COPY templates templates
COPY geochron geochron
COPY ftc ftc

# the following flags make gunicorn work better in a container:
# --worker-tmp-dir /dev/shm --threads=4 --worker-class=gthread --capture-output -b 0.0.0.0:80
CMD gunicorn --worker-tmp-dir /dev/shm --threads=4 --worker-class=gthread --log-level debug --capture-output -b 0.0.0.0:80 --workers=2 geochron.wsgi
