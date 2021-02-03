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

If you do this you will have a database user that does not correspond to
a real user on your system. If you want to log in to the database with this
user, you will have to specify the host even if it is on localhost, or it will
complain that the authentication failed. So you can log on, if you want,
like this:

```sh
$ psql -h localhost geochron geochron
Password for user geochron:
geochron=>
```

### Configure your Geochron@home instance

Copy the file `env` to `.env`, and edit the new copy as appropriate. In
particular replace `<GEOCHRON_PASSWORD>` with the password you set
after `\password geochron` above. These settings will be set as environment
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
(geochron-at-home) $ python manage.py makemigrations ftc
(geochron-at-home) $ ./site_init.sh
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

Note that if your `OUT_EMAIL_...` settings are incorrect, it will appear
as if users trying to log in are failing authentication with Geochron@home,
when what is really happening is that Django is failing to authenticate with
the email server.

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

You can upload a new set of images by giving them the following paths:
`user_upload/<user-name>/<project-name>/<sample-name>/<grain-name>/<image-name>.jpg`
with the following changes:
* You can use `.jpeg` or `.png` instead of `.jpg` for the filename extension
* `<user-name>` needs to be placed with a valid user name in the Geochron@home system
* `<project-name>` can be anything
* `<sample-name>` can be anything
* `<grain-name>` must be `Grain` followed by two digits
* `<image-name>` must be one of
    - `ReflStackFlat`
    - `StackFlat`
    - `stack-` followed by a natural number
    - `mica` followed by any of the above

You also need a file called `rois.json` in alongside each set
of image files. This represents a JSON object with the following
attributes:
* `image_width`: the width of all the images
* `image_height`: the height of all the images
* `regions`: an array of regions with tracks to count, each an object with the following attributes:
    - `shift`: an array of `[x,y]`, sometimes (don't really understand it) the offset of `coords`, below.
    - `vertices`: an array of `[[x0,y0], [x1,y1], ...]`; the boundary of the region

From the Django project's pipenv shell:

```sh
(geochron-at-home) $ python upload_projects.py -s geochron.settings -i user_upload -o ftc/static/grain_pool
```

(upload_projects needs fixing: uses hardcoded project admin 'john')

Or you can keep it watching for uploads to be available with:

```sh
(geochron-at-home) $ ./watch-for-upload.sh
```

If running `watch-for-upload.sh` you need to add a file maybe like
so (again replacing `<user-name>` with your user name):

```sh
(geochron-at-home) $ touch user_upload/<user-name>/do_commit
```

This file will be deleted by `watch-for-upload.sh` after it has logged
the new samples.

## Downloading results

I think you just pick them out of the file system, although I have to see
what the various reports do.
