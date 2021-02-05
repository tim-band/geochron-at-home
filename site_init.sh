#!/bin/sh

python manage.py migrate --noinput
python site_default_users.py
if [ -d vendor ]
then
python manage.py collectstatic --noinput > /dev/null
fi
