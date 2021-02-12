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

### Configure your Geochron@home instance

Copy the file `env` to `.env`, and edit the new copy as appropriate. In
particular replace `<GEOCHRON_PASSWORD>` with the password you set
after `\password geochron` above. These settings will be set as environment
variables when you enter your pipenv shell (see next section).

### Setting up a Python environment

You can set up a pipenv to run Geochron@home like so (after installing Python 2.7):

```sh
$ pip install pipenv
$ pipenv install
```

Now you can enter the pipenv shell like this:

```sh
$ pipenv shell
(geochron-at-home) $
```

and now you can run the app and use all the Python tools it depends on.
You can exit this any time with `exit`:

```sh
(geochron-at-home) $ exit
$
```

And enter it by cding to the correct directory and typing:

```sh
$ pipenv shell
(geochron-at-home) $
```

### Setting up PostgreSQL

Set yourself up a PostgreSQL database from the pipenv shell like this:

```sh
(geochron-at-home) $ sudo -Eu postgres ./init_db.sh
(geochron-at-home) $ ./site_init.sh
```

If you do this you will have a database user that does not correspond to
a real user on your system. If you want to log in to the database with this
user, you will have to specify the host even if it is on localhost, or it will
complain that the authentication failed. So you can log on, if you want,
like this:

```
$ psql -h localhost geochron geochron
Password for user geochron:
geochron=>
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

## Running in production with docker-compose

(this is a work in progress)

Firstly copy the file `production_env` to `production.env` and edit the copy
to your liking. `DB_HOST` must remain set to `db`.

We must build the docker swarm, setting the hosts and base URL. In this
example, the service is being hosted at `www.myhost.com/geochron@home`,
behind a reverse proxy that strips the initial `/geochron@home`. Multiple hosts
can be specified in `ALLOWED_HOSTS` as a comma-separated list. Any host can
be allowed with `ALLOWED_HOSTS='*'`.

```sh
$ ALLOWED_HOSTS=www.myhost.com BASE_URL=/geochron@home docker-compose build
$ docker-compose up -d
```

To set up the database, run:

```
$ docker-compose exec django ./site_init.sh
```

(you can ignore warnings about `ALLOWED_HOSTS` and `BASE_URL` not
being defined)

You can now browse to [http://localhost:3830/ftc] to see it running.

If you want to see logs from Django, you can do so with:

```sh
$ docker logs -f geochron-at-home_django_1
```

(with the `-f` to show log messages as they arrive, or without
to show just the messages currently logged)

### nginx stanza

To proxy to this docker swarm with nginx (using the path
`/geochronathome`), you can use:

```
location /geochronathome/ {
        proxy_pass http://127.0.0.1:3830/;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect off;
        location /geochronathome/static/ {
                proxy_pass http://127.0.0.1:3830/static/;
        }
}
```

Or, if you are not using `ALLOWED_HOSTS` you need:

```
location /geochronathome/ {
        proxy_pass http://127.0.0.1:3830;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header SCRIPT_NAME /geochronathome;
		proxy_redirect /geochronathome/ /geochronathome/;
        proxy_redirect / /geochronathome/;
        location /geochronathome/static/ {
                proxy_pass http://127.0.0.1:3830/static/;
        }
}
```

(note the deleted slash from the `proxy_pass` line)

## Uploading x-ray images

You can upload a new set of images by giving them the following paths:
`user_upload/<user-name>/<project-name>/<sample-name>/<grain-name>/<image-name>.jpg`
(please ensure that all these files are readable by all users)
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

This file can be generated with the [`fissiontracks` R utility](https://github.com/pvermees/fissiontracks)

From the Django project's pipenv shell:

```sh
(geochron-at-home) $ python upload_projects.py -s geochron.settings -i user_upload -o static/grain_pool
```

Or, if you are using docker-compose:

```sh
$ docker-compose exec django python3 upload_projects.py -s geochron.settings -i user_upload -o static/grain_pool
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

### Troubleshooting image upload

If the web server returns a 403 (forbidden) when attempting to access
these images, you may have uploaded images that are not readable by
all users. You can correct this by entering the `django` container with
`docker-compose exec django sh`, navigating to the offending
directory within `/code/static/grain_pool` and using `chmod ao+r *`.
