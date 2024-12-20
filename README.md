# Geochron@Home

Copyright 2014-2023 Jiangping He (geochron.home@gmail.com)
and Tim Band.

This work was in part funded by the Natural Environment Research Council
(grant number 09 NE/T001518/1 ("Beyond Isoplot")).

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
particular replace `<GEOCHRON_PASSWORD>` with an arbitrary password
(this does not need to be a secure password on a local development
installation).

There are also the details for two initially-provisioned users in this
file: `admin` and `john`. You should change these users' details if
you are installing in production (or if you want to for some other
reason). The variables you need to change are called:

```
SITE_ADMIN_NAME
SITE_ADMIN_PASSWORD
SITE_ADMIN_EMAIL
PROJ_ADMIN_NAME
PROJ_ADMIN_PASSWORD
PROJ_ADMIN_EMAIL
```

These settings will be set as environment variables when
you enter your pipenv shell (see next section).

### Setting up a Python environment

You can set up a pipenv to run Geochron@home like so (after installing Python 3):

```sh
$ pip install pipenv
$ pipenv install --dev
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

### Setting up PostgreSQL

Set yourself up a PostgreSQL database from the pipenv shell like this:

```sh
(geochron-at-home) $ sudo -Eu postgres ./init_db.sh
(geochron-at-home) $ ./manage.py migrate sites
(geochron-at-home) $ ./manage.py migrate
(geochron-at-home) $ ./site_init.sh
```

If you do this you will have a database user that does not correspond to
a real user on your system. If you want to log in to the database with this
user, you will have to specify the host even if it is on localhost, or it will
complain that the authentication failed. So you can log on, if you want,
like this (this password is what you set as `POSTGRES_PASSWORD` in
the `.env` file):

```
$ psql -h localhost geochron geochron
Password for user geochron:
geochron=>
```

And you can exit postgres with `\q`.

#### Resetting the database in docker-compose

Normally a "production" server running inside docker-compose will
keep its database even if `docker-compose down -v` is used. To
clear it out and start again:

```sh
$ docker-compose down -v
$ sudo rm db/pgdata -rf
$ docker-compose up -d
$ docker-compose exec django ./site_init.sh
```

### Starting Geochron@Home

Run the server with:

```sh
$ pipenv run server
```

or from the pipenv shell you can also use:

```sh
(geochron-at-home) $ ./manage.py runserver
```

And you can now browse to `localhost:8000/ftc`

## Running in production without Docker

(this is a work in progress)

Need to serve files (with nginx, say) from the `/var/www/html/geochron_at_home/static/`
directory at the URL `/geochron_at_home/static/`. Ensure the following are set in
your .env file:

```
SCRIPT_NAME=/geochron_at_home
WWW_ROOT=/var/www/html
SSL_ONLY=false
DB_HOST=localhost
DB_PORT=5432
DJANGO_DEBUG=false
```

Also make sure your `SECRET_KEY` is set to a fresh random string.

Note that if your `OUT_EMAIL_...` settings are incorrect, it will appear
as if users trying to log in are failing authentication with Geochron@home,
when what is really happening is that Django is failing to authenticate with
the email server.

Let's say you wanted to serve your Geochron@home at `/geochron_at_home/`,
using port 3830 for your Django instance and ports 3851 and 3852 for
prometheus metrics, set the following in the http `server` block of your
nginx config:

```
location /geochron@home/static/ {
  root /home/wwwrunner/html;
}
location /geochron@home/metrics/1 {
  access_log off;
  error_log off;
  proxy_pass http://127.0.0.1:34982/;
}
location /geochron@home/metrics/2 {
  access_log off;
  error_log off;
  proxy_pass http://127.0.0.1:39481/;
}
location /geochron@home/ {
  proxy_pass http://127.0.0.1:39401/;
  proxy_http_version 1.1;
  proxy_set_header Host $http_host;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
}
```

Let's clone the database into directory `/var/www/repos/geochron-at-home`.
You need to install the pip environment as the user you want to run as:

```
cd /var/www/repos/geochron-at-home
sudo find . -exec chown wwwrunner:wwwrunner {} +
sudo -u wwwrunner python3 -m pipenv --python 3.9
sudo -u wwwrunner python3 -m pipenv install
```

Then you can make a systemd configuration file `/etc/systemd/system/geochron-at-home.service`:

```
[Unit]
Description=Geochron@Home
After=network.target

[Service]
Type=simple
User=wwwrunner
WorkingDirectory=/var/www/repos/geochron-at-home
ExecStartPre=/usr/bin/python3 -m pipenv run collect
ExecStartPre=/usr/bin/python3 -m pipenv run migrate
ExecStart=/usr/bin/python3 -m pipenv run gunicorn --log-level info --bind 127.0.0.1:39401 --workers=2 geochron.wsgi
Restart=always

[Install]
WantedBy=multi-user.target
```

Then do the set up. Firstly copy the file `production_env` to `.env`
and edit it as required. Ensure that you add:

```
STATIC_ROOT=/home/wwwrunner/html/geochron@home/static
DB_HOST=127.0.0.1
DB_PORT=5432
PROMETHEUS_METRICS_EXPORT_PORT_RANGE=39480-39499
SCRIPT_NAME=/geochron@home
SITE_NAME=geochron@home
SITE_DOMAIN=your.domain.ac.uk
```

Make sure you have set the postgres password and know what it is
(`sudo -u postgres psql` then `ALTER USER postgres PASSWORD 'mysupersecurepassword';`)

Then:

```
sudo -u wwwrunner pipenv install
sudo -u wwwrunner pipenv shell
mkdir ~/html
exit
sudo systemctl start geochron-at-home.service
pipenv --python 3.9
pipenv shell
sudo -Eu postgres ./init_db.sh
exit
sudo -u wwwrunner pipenv run ./site_init.sh
```

and start with `sudo systemctl start geochron-at-home`.

If you update the code, you can redeploy with `sudo systemctl restart geochron-at-home`.

And you can look at the logs with `journalctl -eu geochron-at-home`.


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
You can ignore (or delete) the settings for `DB_HOST`,
`DB_PORT` and `STATIC_ROOT` as these are overridden in the compose file.

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

As with running without Docker, whenever any static files (anything
in the `ftc/static` directory) have changed you will need to run:

```sh
(geochron-at-home) $ python manage.py collectstatic
```

### nginx stanza

To proxy to this docker swarm with nginx (using the path
`/geochron@home`), you can use:

```
location /geochron@home/ {
        proxy_pass http://127.0.0.1:3830; # note: no trailing /
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect off;
}
```

### Using Geochron@Home

Two users will have been set up, you can sign in as either  one. If
you did not change them from the defaults, they will be
`admin` with password `yOuRsEcReT_01` and `john` with password
`yOuRsEcReT_02`.

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
(geochron-at-home) $ pipenv requirements >requirements.txt
(geochron-at-home) $ ./manage.py collectstatic
(geochron-at-home) $ ./manage.py test
```

You can test only the API tests by adding the option `--tag api` or
only the selenium test by adding the option `--tag selenium`.

At present there are only these two types of test.

### Running the tests with a different browser

The default browser is Chromium, but you can choose Chrome or Firefox
instead as follows:

```sh
(geochron-at-home) $ BROWSER=chrome ./manage.py test
```

...for Chrome (make sure you have `chromedriver` installed and it has the
same version number as Chrome), or

```sh
(geochron-at-home) $ BROWSER=firefox ./manage.py test
```

...for Firefox (make sure you have `geckodriver` installed on your path, at
least version 0.32)

Instead of `./manage.py test` within pipenv shell, you can use the
following command in a normal shell:

```sh
$ pipenv run test
```

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

Firstly, remove any settings beginning `JWT_` from your
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

### Using the CLI

You can manage your Geochron@Home projects including making projects,
uploading samples, uploading and downloading results, using the command
line tool `gah`. See the [gah documentation](gah/README.md).

## Public samples

You can set a sample to be "public" either by ticking the "public" box
on the appropriate Sample page in the Admin view, or by choosing
Manage Projects, then the appropriate project, then the sample,
then click "Edit", tick the "public" box and click the "Save" button.

Once a sample is public, its grains will be available to view on
the URL `/ftc/grain/<grain-id>/user/<user-id>/` where `<grain-id>`
is the ID number of the grain and `<user-id>` is the ID number of
the user whose track markers are to be displayed.

Also a public sample can be displayed at `/ftc/public/<sample>/<grain-index>`,
where `<sample>` is the sample ID number and `<grain-index>` is
the number of the grain within the sample to view. Track markings
for the owner of the sample will be visible, if any. "Previous" and
"Next" buttons will be rendered to take the browser from grain to
grain within that sample.

## Localization

Text is internationalized by including the text:

```
{& load i18n %}
```

at the top of a template, then either using the tag
`{% translate "text to translate" %}` or the block tags:

```
{% blocktranslate %}
Text to translate, which can
include {{ context_variables }}
and multiple lines.
{% endblocktranslate %}
```

These translations are stored in `.mo` files. You can create
these by ensuring that you have the `gettext` package installed
on your system and typing (from the pipenv shell):

```
(geochron-at-home) $ mkdir locale
(geochron-at-home) $ ./manage.py makemessages -l zh_HANS
```

This one makes or updates the file for Simplified Chinese, called
`locale/zh_HANS/LC_MESSAGES/django.po`. Localization tools such as
Weblate understand this file format.

## Troubleshooting Geochron@Home development

You can run a Python shell that can call the app's functions directly with:

```sh
$ pipenv run shell
```

Or, for a less pleasant experience, but one that prints out the SQL commands
that are going to the database, try:

```sh
$ pipenv run debug
```

`django.test.Client` and `django.urls.reverse` are already imported
for you in the `run debug` shell, and you have an instance of `Client`
called `cli` and functions `get` and `post` that are shortcuts for
`cli.get` and `cli.post`.

To start with you are logged in as the site admin, but you can change
this with `login(username, password)`.

As an example, here is a way to see how many database commands are
issued when downloading JSON results:

```
(Pdb) get(reverse('getJsonResults'))
```

Remember that you exit a `Pdb` shell by typing `c` and pressing
return.

#### TODO:

* Need a way to find out which grain in the DB came from which folder on the file system; presumably this will need a database migration to give every grain an origin note.
