#!/bin/bash

echo "$(basename -- $0) site initializing"
python manage.py migrate --noinput
python manage.py collectstatic --noinput > /dev/null
python site_default_users.py
