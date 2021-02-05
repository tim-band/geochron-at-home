#!/bin/sh
if [ -z "${POSTGRES_PASSWORD}" ]
then
echo 'POSTGRES_PASSWORD environment variable not set, are we in pipenv shell?'
elif [ -z "${POSTGRES_DB}" ]
then
echo 'POSTGRES_DB environment variable not set, are we in pipenv shell?'
elif [ -z "${POSTGRES_USER}" ]
then
echo 'POSTGRES_USER environment variable not set, are we in pipenv shell?'
elif [ -z "${DB_HOST}" ]
then
echo 'DB_HOST environment variable not set, are we in pipenv shell?'
else
# escape single quotes
pass=${POSTGRES_PASSWORD//\'/\\\'}
psql -1 -v PW=\'${pass}\' -v DB=${POSTGRES_DB} -v GUSER=${POSTGRES_USER} -h ${DB_HOST}<<SQL
create role :GUSER with login encrypted password :PW;
create database :DB with owner :GUSER;
SQL
fi
