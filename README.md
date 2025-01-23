# Geochron@Home

Copyright 2014-2018 Jiangping He (geochron.home@gmail.com)
and 2019-2025 Tim Band.

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

### Crowdsourcing

Users can count random grains from the database by clicking the "Count"
button on the dashboard (after they have completed the tutorial). The
grains are chosen in the following manner:

- If the user has already saved a partial count, this grain will be chosen.
- Otherwise, it will choose, at random, one of the grains:
  - that has images of the correct type (Spontaneous or Induced)
  - and that does not already have a count from this user (if not guest)
  - and that has fewer than min_contributor_num non-guest counts
  - from the highest priority project
    - that is not "closed"
    - from the highest priority sample
      - that is not "completed"

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

### Using the API

You can use the `gah.py` script from any machine that can see the API endpoints.
To install it you need to install `pipx` on your machine then use it to install `gah`
from github:

```sh
python3 -m pip install --user pipx
pipx install git+https://github.com/tim-band/geochron-at-home.git#subdirectory=geochron/gah
```

Or you can install it from a local path, like `pipx install ./geochron`.

Before using it you have to tell it where the endpoints are:

```sh
(geochron-at-home) $ gah set url https://my.domain.com/geochron@home
```

Do not include any `/ftc` or `/api`. This produces a file
`gah.config` that stores this and other information. As long
as you run `gah` from a directory containing such a
file, you will be able to use these settings.

Next, you need to log in with `gah login`. You can use
any admin user on the site. This login session will last for
one day, beyond which a further login will be required. You
can use `gah logout` to forget this login session.

Now you can use the other commands of `gah`, for example:

* `gah` on its own lists help and commands
* `gah project -h` to get help on the project commands
* `gah project list` lists all the project IDs
* `gah project info <ID>` gives information on project with ID `<ID>`
* `gah project new <project-name> "<description>" <priority>`
* `gah sample -h` to get help on the sample commands
* `gah grain upload <path>` to upload all the grains in
the directory under `<path>`. Every directory that contains a file called
`rois.json` or contains `*_metadata.xml` files will become a grain, and
all image files in the same directory with the right sort of file name
will become images in the grain (see the Upload Image Files section above).
The grains will be added to samples inferred from the names of the
directories in which they sit, unless the `--sample <ID_OR_NAME>` option
is given in which case they will all be added to the identified sample.
* `gah grain delete <path>` will delete the grain implied by the
last two segments of `<path>`, which should match `<sample_name>/Grain<nn>`.
* `gah sample delete <name-or-id>` will delete the identified
sample; there will be no interactive confirmation, so be careful!
* `gah count list` returns results of user counts
* `gah count upload <file>` uploads new user counts. You can edit the file
returned from `gah count list` if you like.
* `gah genrois <path>` creates `rois.json` files for all the grains
within `<path>`. Obviously the ROI paths are arbitrary, but other data is
derived from the grain files present. This is necessary to upload grains
if you have not created your own `rois.json` files.

#### Example: Uploading a new sample

So, for example, to create a new sample with all its images in an
existing project (say `ProjectDEF`), you might do this:

```sh
(geochron-at-home) $ gah project list
1 ProjectABC
2 ProjectDEF
3 SomeOtherProject
```

So we need project ID `2`. We'll arbitrarily pick `20` as the priority (so
this sample will be shown before any with a lower number for the
priority and after any with a higher number) and `50` as the number of
contributors required to finish this sample. We will look for the
`"id":<N>` property of the JSON returned to feed to the `grain new`
function:

```sh
(geochron-at-home) $ gah sample new Sample123 2 T 20 50
b'{"id":199,"sample_name":"Sample123","in_project":2,"sample_property":"T","priority":20,"min_contributor_num":50,"completed":false}'
(geochron-at-home) $ gah grain upload --sample 199 /path/to/directory/of/grains
Created new grain 28
Uploaded image /path/to/directory/of/grains/Grain01/Stack-09.jpg as image 469
Uploaded image /path/to/directory/of/grains/Grain01/Stack-07.jpg as image 470
Uploaded image /path/to/directory/of/grains/Grain01/Stack-02.jpg as image 471
Uploaded image /path/to/directory/of/grains/Grain01/Stack-10.jpg as image 472
Uploaded image /path/to/directory/of/grains/Grain01/ReflStackFlat.jpg as image 473
Uploaded image /path/to/directory/of/grains/Grain01/Stack-12.jpg as image 474
...
```

If your grains are in a directory named after the sample you can combine
these:

```sh
(geochron-at-home) $ gah sample upload 2 T 20 999 /path/to/sample/Sample456
Created new grain 33
Uploaded image /path/to/sample/Sample456/Grain01/MicaReflStack-00.jpg as image 4981
Uploaded image /path/to/sample/Sample456/Grain01/MicaReflStack-01.jpg as image 4982
Uploaded grain count: 19
```

The structure of your grains directory should be `GrainNN/Stack-NN.jpg` to
get predictable grain and image numbers. The capitalisation (or indeed spelling)
of `Grain` does not matter as long as it is followed by two digits. The acceptable
names for the images are:

* `Stack-NN.jpg` for transmitted light apatite image, lower number is shallower
* `ReflStackFlat.jpg` for reflected light apatite image
* `MicaStack-NN.jpg` for transmitted light reflected image, lower number is shallower
* `MicaReflStackFlat.jpg` for reflected light apatite image
* as above, but `.jpeg` instead of `.jpg`
* as above, but `.png` instead of `.jpg` (for PNG image)

#### Example: Uploading user counts

If you have counted grains in some other program, you can still display these counts in
Geochron@Home by uploading them. The command is simple:

```sh
$ gah count upload count.json
```

where `count.json` has the following format:
```json
[{
    "sample": 14,
    "index": 1,
    "ft_type": "S",
    "user": "admin",
    "date": "2024-06-26",
    "points": [{
        "x_pixels": 444,
        "y_pixels": 555,
        "category": "track",
        "comment": "Not sure about this one"
    }],
    "lines": [
        [100, 200, 2, 500, 600, 4],
        [560, 560, 3.5, 900, 100, 3],
        {
          "x1_pixels": 1000,
          "y1_pixels": 1200,
          "z1_level": 2,
          "x2_pixels": 700,
          "y2_pixels": 900,
          "z2_level": 2.5
        }
    ]
}]
```

Here `"points"` is the list of etch pits identified by the user.
(`x_pixels`, `y_pixels`) is the position of the etch pit, `category`
is optional, and can take the values `track` (default), `inclusion`,
`surface` or `defect`. More can be added through the admin
interface by altering the `GrainPointCategory` table. `comment`
is also optional. `category` and `comment` are useful for
making tutorial pages.

`"lines"` is the list of contained tracks. Currently Geochron@Home
has no way to allow users to add these, they can only be uploaded.
We can see two different ways to specify a line; one is to describe
the endpoints with keys `x1_pixels`, `y1_pixels`,  `z1_level`,
`x2_pixels`, `y2_pixels` and  `z2_level`. As these names suggest,
the x and y co-ordinates are defined in pixels, whereas the z
co-ordinate is the focus level at which the end is in focus (with
0 as the uppermost level). Alternatively, a simple list of six floating
point numbers is acceptable.

The overall type is a list, so as many results as you like can be
uploaded in one call. For each uploaded result, any existing
result from this user for this grain is discarded.

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

If `gah` gives you `Failed (with HTTP code 500: Internal Server Error)`
including detail `InvalidKeyError at /ftc/api/get-token` then you have
a problem with your JWT token (see the information about `gen_jwt.py`
above). However, VSCode's terminal fails to read these JWT tokens
correctly out of the `.env` file and so running the server from within
VSCode's terminal will fail to respond correctly to `gah` unless
you also set the environment variable `DISABLE_JWT=1`.

#### TODO:

* Need a way to find out which grain in the DB came from which folder on the file system; presumably this will need a database migration to give every grain an origin note.
