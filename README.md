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

If any static files have changed you might have to:

```sh
(gechron-at-home) $ STATIC_ROOT='static' python manage.py collectstatic
```

Then, in any case you must:

```sh
(geochron-at-home) $ python manage.py runserver
```

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
location /gah/metrics {
    deny all;
    access_log off;
    error_log off;
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

Firstly copy the file `production_env` to `production.env` and edit the copy
to your liking.

We must build the docker swarm, setting the hosts and base URL. For
example, if the service is being hosted at `www.myhost.com/geochron@home`
behind a reverse proxy that strips the initial `/geochron@home`
then you need to set:

```
SITE_DOMAIN=www.myhost.com
ALLOWED_HOSTS=localhost,www.myhost.com
```

Multiple hosts can be specified in `ALLOWED_HOSTS` as a
comma-separated list. Any host can be allowed with `ALLOWED_HOSTS='*'`.
The `localhost,` setting is needed if you want any local access, for
example a local prometheus collecting metrics.
You can ignore (or delete) the settings for `DB_HOST` and `STATIC_ROOT`
as these are overridden in the compose file.

Now you can build it with `docker-compose build` and run it with
`docker-compose up -d`. Or you can do both with at once with
`docker-compose up -d --build`.

To set up the database, run:

```
$ docker-compose exec django ./site_init.sh
```

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
location /geochron@home/ {
        proxy_pass http://127.0.0.1:3830/;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect off;
        location /geochron@home/static/ {
                proxy_pass http://127.0.0.1:3830/static/;
        }
}
```

### Backup and restore

Back up the entire database like this:

```sh
docker-compose exec db pg_dump -c -U geochron | gzip -c > ../gah.gz
```

Restore it like this:

```sh
gunzip -c ../gah.gz | docker-compose exec -T db psql -U geochron -f-
```

## Uploading crystal images (old style)

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

## Running tests

From the pipenv shell:

```sh
(geochron-at-home) $ python test/integration.py
```

for the Selenium test, or

```sh
(geochron-at-home) $ ./manage.py test
```

for the lower-level tests. There are no unit tests.

At some point the Selenium test should probably be brought
under `./manage.py test`

### Troubleshooting image upload

If the web server returns a 403 (forbidden) when attempting to access
these images, you may have uploaded images that are not readable by
all users. You can correct this by entering the `django` container with
`docker-compose exec django sh`, navigating to the offending
directory within `/code/static/grain_pool` and using `chmod ao+r *`.

## Using the API

There is an API available (with the same users), secured
with Java Web Tokens.

A couple of scripts are provided that interface with this API, marshalling
the Json Web Tokens you need along the way.

### Initializing the JWT

Before using the API you must initialize the JWT. Also,
periodically, or if you susupect the JWT might have leaked
you should also re-initialize the JWT.

Firstly, remove any lines beginning `JWT_` from your
`.env` file (for local development) or `production.env`
(for production). Then, from the Pipenv shell:

```sh
(geochron-at-home) $ ./gen_jwt >> .env
```

for local development, or

```sh
(geochron-at-home) $ ./gen_jwt >> production.env
```

for production.

Now restart geochron@home:

```sh
(geochron-at-home) exit
$ pipenv shell
(geochron-at-home) ./manage.py runserver
```

or for production:

```sh
$ docker-compose down
$ docker-compose up -d --build
```

### Using the API

You can use the `./gah.py` script from any machine that
can see the API endpoints. But first, you have to tell it where
the endpoints are:

```sh
./gah.py set url https://my.domain.com/geochron@home
```

Do not include any `/ftc` or `/api`. This produces a file
`gah.config` that stores this and other information. As long
as you run `./gah.py` from a directory containing such a
file, you will be able to use these settings.

Next, you need to log in with `./gah.py login`. You can use
any admin user on the site. This login session will last for
one day, beyond which a further login will be required.

Now you can use the other commands of `gah`, for example:

* `./gah.py` on its own lists help and commands
* `./gah/py project -h` to get help on the project commands
* `./gah.py project list` lists all the project IDs
* `./gah.py project info <ID>` gives information on project with ID `<ID>`
* `./gah.py project create <project-name> "<description>" <priority>`
* `./gah.py sample -h` to get help on the sample commands
* `./gah.py grain <sample-ID> <path>` to upload all the grains in the
directory under `<path>`. Every directory that contains a file called
`rois.json` will become a grain, and all image files in the same directory
with the right sort of file name will become images in the grain (see
the Upload Image Files section above).
