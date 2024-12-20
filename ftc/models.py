from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.urls import reverse
from django_prometheus.models import ExportModelOperationsMixin
import json
import logging

class Project(models.Model):
    alphanumeric = RegexValidator(r'^[0-9a-zA-Z_-]+$', 'Only alphanumeric, "-" and "_" are allowed.')
    project_name = models.CharField(
        max_length=36,
        validators=[alphanumeric],
        unique=True,
    )
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    create_date = models.DateTimeField(auto_now_add=True)
    project_description = models.CharField(max_length=200)
    priority = models.IntegerField(default='0')
    closed = models.BooleanField(default=False)

    class Meta:
        get_latest_by = "create_date"

    def __unicode__(self):
        return '%s owned by %s' % (self.project_name, self.creator.username)

    def get_absolute_url(self):
        return reverse('project', args=[self.pk])

    def get_owner(self):
        return self.creator

    @classmethod
    def filter_owned_by(cls, qs, user):
        return qs.filter(creator=user)

#
class Sample(models.Model):
    not_too_mad = RegexValidator(r'^[0-9a-zA-Z_\- #/\(\):@]+$', 'Only alphanumeric, space and "_-#():@" are allowed.')
    SAMPLE_PROPERTY = (
        ('T', 'Test Sample'),
        ('A', 'Age Standard Sample'),
        ('D', 'Dosimeter Sample'),
    )
    sample_name = models.CharField(max_length=36, validators=[not_too_mad])
    in_project = models.ForeignKey(Project, on_delete=models.CASCADE)
    sample_property = models.CharField(max_length=1, choices=SAMPLE_PROPERTY, default='T')
    priority = models.IntegerField(default='0')
    min_contributor_num = models.IntegerField(default='1')
    completed = models.BooleanField(default=False)
    public = models.BooleanField(default=False)

    class Meta:
        unique_together = ('sample_name', 'in_project',)

    def __unicode__(self):
        return 'sample %s belong to project %s as %s' % (self.sample_name, 
                self.in_project.project_name, self.sample_property)

    def get_absolute_url(self):
        return reverse('sample', args=[self.pk])

    def get_owner(self):
        return self.in_project.get_owner()

    @classmethod
    def filter_owned_by(cls, qs, user):
        return qs.filter(in_project__creator=user)

#
class Transform2D(models.Model):
    x0 = models.FloatField()
    y0 = models.FloatField()
    t0 = models.FloatField()
    x1 = models.FloatField()
    y1 = models.FloatField()
    t1 = models.FloatField()

#
class Grain(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    index = models.IntegerField()
    image_width = models.IntegerField()
    image_height = models.IntegerField()
    scale_x = models.FloatField(null=True, blank=True)
    scale_y = models.FloatField(null=True, blank=True)
    stage_x = models.FloatField(null=True, blank=True)
    stage_y = models.FloatField(null=True, blank=True)
    mica_stage_x = models.FloatField(null=True, blank=True)
    mica_stage_y = models.FloatField(null=True, blank=True)
    shift_x = models.IntegerField(default=0, blank=True)
    shift_y = models.IntegerField(default=0, blank=True)
    mica_transform_matrix = models.ForeignKey(Transform2D, on_delete=models.CASCADE, null=True)

    class Meta:
        unique_together = ('sample', 'index',)

    def get_absolute_url(self):
        return reverse('grain_images', args=[self.pk])

    def get_owner(self):
        return self.sample.get_owner()

    @classmethod
    def filter_owned_by(cls, qs, user):
        return qs.filter(sample__in_project__creator=user)

    def get_images_crystal(self):
        return self.image_set.filter(ft_type='S').order_by('index')
    
    def get_images_mica(self):
        return self.image_set.filter(ft_type='I').order_by('index')

    def count_images_crystal(self):
        return self.image_set.filter(ft_type='S').count()

    def count_images_mica(self):
        return self.image_set.filter(ft_type='I').count()

    def count_results(self):
        return FissionTrackNumbering.objects.filter(
            grain=self,
            result__gte=0,
        ).count()

    def owners_result_of(self, ft_type):
        ftn = FissionTrackNumbering.objects.filter(
            grain__sample=self.sample,
            grain__index=self.index,
            ft_type=ft_type,
            worker=self.get_owner()
        ).first()
        if ftn == None:
            return None
        return ftn.result

    def owners_result(self):
        return self.owners_result_of('S')

    def owners_result_mica(self):
        return self.owners_result_of('I')

    def roi_area_pixels(self):
        """
        Find the area of the ROI in pixels.

        Currently this does not take account of negative ROI regions.
        """
        total = 0
        for r in self.region_set.all():
            total += r.area()
        return total

    def roi_area_mm2(self):
        """
        Find the area of the ROI in pixels.

        Currently this does not take account of negative ROI regions.
        """
        scale_x = self.scale_x
        scale_y = self.scale_y
        if scale_x is None or scale_y is None:
            return None
        return scale_x * scale_y * self.roi_area_pixels() * 1e6

    def roi_contains_point(self, x, y):
        """
        Find if the point at (x,y) pixels is within this grain's Region of Interest.

        If a point is within two sub-regions it counts as not being within
        the region-of-interest; a region within a region is counted as
        a hole.
        """
        count = 0
        for r in self.region_set.all():
            if r.contains_point(x, y):
                count += 1
        return count % 2 == 1

    def get_analyses(self):
        return FissionTrackNumbering.objects.filter(
            grain__sample=self.sample,
            grain__index=self.index,
            worker__username='guest',
            analyst__isnull=False
        )

#
class Region(models.Model):
    grain = models.ForeignKey(Grain, on_delete=models.CASCADE)

    def area(self):
        """ Returns the region's area in pixels """
        vs = list(self.vertex_set.all())
        vs.sort(key=lambda v: v.pk)
        n = len(vs)
        if n == 0:
            return 0
        last_v = vs[n - 1]
        total = 0
        for v in vs:
            total += v.x * last_v.y - last_v.x * v.y
            last_v = v
        return abs(total / 2)

    def contains_point(self, x, y):
        """Find if the point at (x,y) pixels is contained within this region"""
        vs = list(self.vertex_set.all())
        vs.sort(key=lambda v: v.pk)
        n = len(vs)
        if n == 0:
            return 0
        last_v = vs[n - 1]
        total = 0
        for v in vs:
            if (
                ((v.x <= x and x < last_v.x) or (last_v.x <= x and x < v.x))
                and (y < last_v.y + (v.y - last_v.y) * (x - last_v.x) / (v.x - last_v.x))
            ):
                total += 1
            last_v = v
        return total % 2 == 1

#
class Vertex(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    x = models.IntegerField()
    y = models.IntegerField()

#
class Image(ExportModelOperationsMixin('image'), models.Model):
    IMAGE_FORMAT=(
        ('J', 'JPEG'),
        ('P', 'PNG'),
    )
    FT_TYPE = (
        ('S', 'Spontaneous Fission Tracks'),
        ('I', 'Induced Fission Tracks'),
    )
    LIGHT_PATH = (
        ('T', 'Transmitted Light'),
        ('R', 'Reflected Light'),
    )
    grain = models.ForeignKey(Grain, on_delete=models.CASCADE)
    format = models.CharField(max_length=1, choices=IMAGE_FORMAT)
    ft_type = models.CharField(max_length=1, choices=FT_TYPE)
    index = models.IntegerField()
    data = models.BinaryField()
    light_path = models.CharField(max_length=1, choices=LIGHT_PATH, null=True)
    focus = models.FloatField(null=True)

    class Meta:
        unique_together = ('grain', 'index', 'ft_type')

    def get_owner(self):
        return self.grain.get_owner()

    @classmethod
    def filter_owned_by(cls, qs, user):
        return qs.filter(grain__sample__in_project__creator=user)

#
class FissionTrackNumbering(ExportModelOperationsMixin('result'), models.Model):
    FT_TYPE = (
        ('S', 'Spontaneous Fission Tracks'),
        ('I', 'Induced Fission Tracks'),
    )
    grain = models.ForeignKey(
        Grain,
        on_delete=models.CASCADE,
        null=True,
        related_name='results'
    )
    ft_type = models.CharField(max_length=1, choices=FT_TYPE)
    worker = models.ForeignKey(User, on_delete=models.CASCADE)
    # If the worker is guest uploaded results won't overwrite existing
    # results unless the analyst also matches and isn't NULL.
    analyst = models.TextField(null=True)
    result = models.IntegerField() #-1 means this is a partial save state
    create_date = models.DateTimeField(auto_now_add=True)

    def project_name(self):
        return self.grain.sample.in_project

    def __unicode__(self):
        return '%s-%s-%d-%s-%s: %d' %(
            self.grain.sample.in_project,
            self.grain.sample.sample_name,
            self.grain.index,
            self.ft_type,
            self.worker.username,
            self.result
        )

    @classmethod
    def objects_owned_by(cls, user):
        return cls.objects.filter(grain__sample__in_project__creator=user)

    def roi_area_micron2(self):
        a = self.grain.roi_area_mm2()
        if a is None:
            return None
        return a * 1e6

    def points(self):
        return [
            {
                'x_pixels': gp.x_pixels,
                'y_pixels': gp.y_pixels,
                'category': gp.category.name,
                'comment': gp.comment
            }
            for gp in self.grainpoint_set.all()
        ]

    def get_latlngs(self):
        width = self.grain.image_width
        height = self.grain.image_height
        return [
            [ (height - gp.y_pixels) / width, gp.x_pixels / width ]
            for gp in self.grainpoint_set.filter(category__name='track')
        ]

    def get_latlngs_within_roi(self):
        # if there are no regions we will count every marker as being
        # within the ROI, otherwise nothing will be.
        if 0 == self.grain.region_set.count():
            return self.get_latlngs()
        width = self.grain.image_width
        height = self.grain.image_height
        return [
            [ (height - gp.y_pixels) / width, gp.x_pixels / width ]
            for gp in self.grainpoint_set.filter(category__name='track')
            if self.grain.roi_contains_point(gp.x_pixels, gp.y_pixels)
        ]

    @property
    def latlngs(self):
        """
        Returns the old latlngs field for backward compatibility.
        """
        return json.dumps(self.get_latlngs())

    @latlngs.setter
    def latlngs(self, value : list[list[float]]):
        self.grainpoint_set.all().delete()
        self.addGrainPointsFromLatlngs(value)

    def addGrainPointsFromLatlngs(self, marker_latlngs : list[list[float]]):
        width = self.grain.image_width
        height = self.grain.image_height
        track = GrainPointCategory(name='track')
        GrainPoint.objects.bulk_create([
            GrainPoint(
                category=track,
                result=self,
                x_pixels=lng * width,
                y_pixels=height - lat * width
            )
            for (lat, lng) in marker_latlngs
        ])

    def addGrainPointsFromGrainPoints(self, points : list[dict[str, any]]):
        """
        Add grain points from a list of dicts. Each dict has elements
        `x_pixels` and `y_pixels` for the co-ordinates of the track with
        (0,0) being the top left, `category` being 'track' or one of the
        other category names, and `comment` being a string describing the
        point.
        """
        for p in points:
            category = p.get('category', 'track')
            gpc = GrainPointCategory.objects.get(pk=category)
            if gpc is None:
                logging.warn('No such category {0}'.format(category))
                gpc = GrainPointCategory.objects.get(pk='track')
            gp = GrainPoint(
                result=self,
                x_pixels=p['x_pixels'],
                y_pixels=p['y_pixels'],
                comment=p.get('comment', ''),
                category=gpc
            )
            gp.save()

    def get_contained_tracks(self):
        return [
            { k: getattr(ct, k) for k in [
                'x1_pixels',
                'y1_pixels',
                'z1_level',
                'x2_pixels',
                'y2_pixels',
                'z2_level'
            ]}
            for ct in self.containedtrack_set.all()
        ]

    @property
    def contained_tracks(self) -> str:
        return json.dumps(self.get_contained_tracks())

    @contained_tracks.setter
    def contained_tracks(self, tracks : list[dict[str, any]]):
        """
        Set grain points from a list of dicts. Each dict has elements
        `x1_pixels`, `y1_pixels`, `z1_level`, `x2_pixels`, `y2_pixels`
        and `z2_level`. (`x1_pixels`, `y1_pixels`) and (`x2_pixels`, `y2_pixels`)
        are co-ordinates on the image, (0,0) being the top left. `z1_level`
        and `z2_level` are the respective z-positions of the ends with 0
        representing the top level (near the surface) and increasing by
        1 for every image in the z-stack. Non-integers are acceptable to
        describe points that are not in perfect focus in any z-stack image.
        """
        self.containedtrack_set.all().delete()
        for t in tracks:
            ct = ContainedTrack(result=self, **t)
            ct.save()

    @property
    def contained_tracks_latlngs(self):
        width = self.grain.image_width
        height = self.grain.image_height
        return [
            [[ (height - ct.y1_pixels) / width, ct.x1_pixels / width, ct.z1_level ],
             [ (height - ct.y2_pixels) / width, ct.x2_pixels / width, ct.z2_level ],]
            for ct in self.containedtrack_set.all()
        ]

    def get_contained_track_count(self):
        return self.containedtrack_set.count()

    def get_track_count(self):
        return self.grainpoint_set.count()

#
class TutorialResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

class GrainPointCategory(models.Model):
    """
    Type of grain point feature (for example, track or crystal defect)
    """
    class Meta:
        verbose_name = 'Grain Point Category'
        verbose_name_plural = 'Grain Point Categories'
    name = models.CharField(primary_key=True, max_length=20)
    description = models.TextField()

class GrainPoint(models.Model):
    """
    A marker for a track or possibly some other feature.
    """
    result = models.ForeignKey(FissionTrackNumbering, on_delete=models.CASCADE)
    x_pixels = models.IntegerField()
    y_pixels = models.IntegerField()
    category = models.ForeignKey(GrainPointCategory, on_delete=models.CASCADE)
    comment = models.TextField()

class TutorialPage(models.Model):
    """
    A page of the tutorial
    """
    PAGE_TYPE = (
        ('E', 'Explain category'),
        ('C', 'Choose category test'),
        ('I', 'Find category test with immediate result'),
        ('S', 'Find category test with results after submit')
    )
    marks = models.ForeignKey(FissionTrackNumbering, on_delete=models.CASCADE)
    category = models.ForeignKey(GrainPointCategory, on_delete=models.CASCADE, null=True, blank=True)
    page_type = models.CharField(max_length=1, null=True, choices=PAGE_TYPE)
    limit = models.IntegerField(null=True, blank=True)
    message = models.TextField()
    active = models.BooleanField(default=True)
    sequence_number = models.IntegerField(default=50)

class ContainedTrack(models.Model):
    """
    Both ends of a track found by a user.
    """
    result = models.ForeignKey(FissionTrackNumbering, on_delete=models.CASCADE)
    x1_pixels = models.IntegerField()
    y1_pixels = models.IntegerField()
    z1_level = models.IntegerField()
    x2_pixels = models.IntegerField()
    y2_pixels = models.IntegerField()
    z2_level = models.IntegerField()
