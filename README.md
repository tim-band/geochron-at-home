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

Edit the file `gahrc`. In particular replace `<GEOCHRON_PASSWORD>` with the
password you set after `\password geochron` above. Then run the following:

```sh
(geochron-at-home) $ source gahrc
(geochron-at-home) $ ./site_init.sh
(geochron-at-home) $ python manage.py collectstatic
```

### Starting Geochron@Home



And you can now browse to `localhost:8000/ftc`

## Running in production

Need to serve files (with nginx, say) from the `static/` directory at the URL `/static/`.

Run 2 workers with:

```sh
(geochron-at-home) $ gunicorn -b 0.0.0.0:8080 --workers=2 geochron.wsgi
```
