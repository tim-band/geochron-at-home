from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.urls import reverse
from django_prometheus.models import ExportModelOperationsMixin

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
    alphanumeric = RegexValidator(r'^[0-9a-zA-Z_-]+$', 'Only alphanumeric, "-" and "_" are allowed.')
    SAMPLE_PROPERTY = (
        ('T', 'Test Sample'),
        ('A', 'Age Standard Sample'),
        ('D', 'Dosimeter Sample'),
    )
    sample_name = models.CharField(max_length=36, validators=[alphanumeric])
    in_project = models.ForeignKey(Project, on_delete=models.CASCADE)
    sample_property = models.CharField(max_length=1, choices=SAMPLE_PROPERTY, default='T')
    total_grains = models.IntegerField()
    priority = models.IntegerField(default='0')
    min_contributor_num = models.IntegerField(default='1')
    completed = models.BooleanField(default=False)

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
class Grain(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    index = models.IntegerField()
    image_width = models.IntegerField()
    image_height = models.IntegerField()
    scale_x = models.FloatField(null=True)
    scale_y = models.FloatField(null=True)
    stage_x = models.FloatField(null=True)
    stage_y = models.FloatField(null=True)
    shift_x = models.IntegerField(default=0)
    shift_y = models.IntegerField(default=0)

    class Meta:
        unique_together = ('sample', 'index',)

    def get_owner(self):
        return self.sample.get_owner()

    @classmethod
    def filter_owned_by(cls, qs, user):
        return qs.filter(sample__in_project__creator=user)

    def get_images_crystal(self):
        return self.image_set.filter(ft_type='S').order_by('index')
    
    def get_images_mica(self):
        return self.image_set.filter(ft_type='I').order_by('index')

#
class Region(models.Model):
    grain = models.ForeignKey(Grain, on_delete=models.CASCADE)

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
    in_sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    grain = models.IntegerField()
    ft_type = models.CharField(max_length=1, choices=FT_TYPE)
    worker = models.ForeignKey(User, on_delete=models.CASCADE)
    result = models.IntegerField() #-1 means this is a partial save state
    create_date = models.DateTimeField(auto_now_add=True)
    latlngs = models.TextField(default='')

    def project_name(self):
        return self.in_sample.in_project

    def __unicode__(self):
        return '%s-%s-%d-%s-%s: %d' %(self.in_sample.in_project, self.in_sample.sample_name, self.grain, self.ft_type, self.worker.username, self.result)

    @classmethod
    def objects_owned_by(cls, user):
        return cls.objects.filter(in_sample__in_project__creator=user)

#
class TutorialResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
