# The gah command-line tool

## How to install

You can use the `./gah/gah.py` script from any machine that can
see the API endpoints. Although you can run it with
`python3 ./gah/gah.py`, or `./gah/gah.py`, or with
`pipenv run gah` or within `pipenv shell` as simply `gah`, perhaps
the most convenient way is to install it using `pipx`. If you are working
on a cloned `geochron-at-home` repo you can install it with:

```sh
pipx install ./geochron
```

or you can install it to any machine directly from github with:

```sh
pipx install git+https://github.com/tim-band/geochron-at-home.git#subdirectory=gah
```

You can uninstall it with:

```sh
pipx uninstall geochron-at-home-cli
```

In the following descriptions we will be calling `gah` as if in
`pipenv shell` or having installed it via `pipx`, so the commands
start `gah`. You might be using `pipenv run gah`, `./gah/gah.py`
or something else.

## Setup

To use `gah`, you must first tell it where the endpoints are:

```sh
(geochron-at-home) $ gah set url https://my.domain.com/geochron@home
```

```sh
$ gah set url https://my.domain.com/geochron@home
```

Do not include any `/ftc` or `/api`. This produces a file
`gah.config` that stores this and other information. As long
as you run `gah` from a directory containing such a
file, you will be able to use these settings.

Next, you need to log in with `gah login`. You can use
any admin user on the site. This login session will last for
one day, beyond which a further login will be required. You
can use `gah logout` to forget this login session.

## Main usage

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

## Uploading projects, samples and grains

To create a new sample with all its images in an existing project (say
`ProjectDEF`), you might do this:

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
