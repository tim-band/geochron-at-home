# Geochron@Home

Copyright 2014 Jiangping He, geochron.home@gmail.com

## Instructions not using Docker

### Notes on instructions

In all the following instructions where you have to type instructions into a
terminal, I have shown a 'prompt' before the characters to type. What the
promt is tells you what program or environment you are typing in; these
should not be typed yourself! The prompts I have used are as follows:
- `$` for a normal shell
- `(geochron-at-home) $` after typing `pipenv shell` you get this.
- `postgres=#` for PostgreSQL; after typing `psql` you get this.

### Setting up PostgreSQL

Firstly set yourself up a PostgreSQL database (and role if you like, with
password), perhaps like so:

```sh
$ sudo -u postres psql
postgres=# create role geochron;
postgres=# \password geochron;
postgres=# alter role geochron with login;
postgres=# create database geochron;
postgres=# alter database geochron owner to geochron;
postgres=# \q
```

### Configure your Geochron@home instance

Copy the file `env` to `.env`, and edit it as appropriate. In particular
replace `<GEOCHRON_PASSWORD>` with the password you set after
`\password geochron` above. These settings will be set as environment
variables when you enter your pipenv shell (see next section).

### Setting up a Python environment

You can set up a pipenv to run Geochron@home like so (after installing Python 2.7):

```sh
$ pip install pipenv
$ pipenv --python $(which python2.7)
$ pipenv shell
$ pip install -r requirements.txt
```

You are now in the pipenv; you can exit this any time with `exit`:

```sh
(geochron-at-home) $ exit
$
```

And enter it by cding to the correct directory and typing:

```sh
$ pipenv shell
(geochron-at-home) $
```

### Initialising Geochron@Home

```sh
(geochron-at-home) $ ./site_init.sh
(geochron-at-home) $ python manage.py collectstatic
```

### Starting Geochron@Home

(geochron-at-home) $ python manage.py runserver

And you can now browse to `localhost:8000/ftc`

## Running in production without Docker

(this is a work in progress)

Need to serve files (with nginx, say) from the `/var/www/html/geochron_at_home/static/`
directory at the URL `/geochron_at_home/static/`. Ensure the following are set in
your .env file:

```
STATIC_ROOT=/var/www/html/geochron_at_home/static/
STATIC_URL=/geochron_at_home/static/
SSL_ONLY=false
DB_HOST=localhost
DJANGO_DEBUG=false
```

Also make sure your `SECRET_KEY` is set to a fresh random string.

Let's say you wanted to serve your Geochron@home at `/gah/`, using port 3841 for
your Django instance:

Set the following in the http `server` block of your nginx config:

```
location /gah/static/ {
    root /var/www/html/geochron_at_home/static;
}
location /gah/ {
    ###
    ### Different depending on whether we are redirecting to https or not
}
```

Run 2 workers with:

```sh
(geochron-at-home) $ gunicorn -b 127.0.0.1:3841 --workers=2 geochron.wsgi
```

## Uploading x-ray images

From the Django project's pipenv shell:

```sh
(geochron-at-home) $ python upload_projects.py geochron.settings
```

(upload_projects needs fixing: uses hardcoded project admin 'john')
