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
exit 2
else
# escape single quotes
pass=$(echo ${POSTGRES_PASSWORD} | sed "s/'/\\\\'/g")
# if we are the postgres user wanting the DB on localhost, we'll use peer authentication
if [ "x$(whoami)" = "xpostgres" -a "${DB_HOST}" = "localhost" ]
then
conn=""
else
conn="-h ${DB_HOST}"
fi
psql -v PW=\'${pass}\' -v DB=${POSTGRES_DB} -v GUSER=${POSTGRES_USER} ${conn}<<SQL
drop database :DB;
create role :GUSER with login encrypted password :PW;
alter role :GUSER with CREATEDB;
create database :DB with owner :GUSER;
SQL
fi
