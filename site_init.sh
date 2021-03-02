#!/bin/sh

python3 manage.py migrate --noinput
python3 site_default_users.py
if [ "${STATIC_ROOT}x" != "x" ]
then
python3 manage.py collectstatic --noinput > /dev/null
fi
