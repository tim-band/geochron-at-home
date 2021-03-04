from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

# import re

# Create your models here.
class Project(models.Model):
    alphanumeric = RegexValidator(r'^[0-9a-zA-Z_-]+$', 'Only alphanumeric, "-" and "_" are allowed.')
    project_name = models.CharField(max_length=36, validators=[alphanumeric])
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    create_date = models.DateTimeField(auto_now_add=True)
    project_description = models.CharField(max_length=200)
    priority = models.IntegerField(default='0')
    closed = models.BooleanField(default=False)
    #project path

    class Meta:
        unique_together = ('project_name', 'creator',)
        get_latest_by = "create_date"

    def __unicode__(self):
        return '%s owned by %s' % (self.project_name, self.creator.username)

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

#
class Grain(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)
    index = models.IntegerField()
    image_width = models.IntegerField()
    image_height = models.IntegerField()

#
class Region(models.Model):
    grain = models.ForeignKey(Grain, on_delete=models.CASCADE)
    shift_x = models.IntegerField()
    shift_y = models.IntegerField()

#
class Vertex(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    x = models.IntegerField()
    y = models.IntegerField()

#
class Image(models.Model):
    IMAGE_FORMAT=(
        ('J', 'JPEG'),
        ('P', 'PNG'),
    )
    FT_TYPE = (
        ('S', 'Spontaneous Fission Tracks'),
        ('I', 'Induced Fission Tracks'),
    )
    grain = models.ForeignKey(Grain, on_delete=models.CASCADE)
    format = models.CharField(max_length=1, choices=IMAGE_FORMAT)
    ft_type = models.CharField(max_length=1, choices=FT_TYPE)
    index = models.IntegerField()
    data = models.BinaryField()

#
class FissionTrackNumbering(models.Model):
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

    class Meta:
        unique_together = ('in_sample', 'grain', 'ft_type', 'worker', 'create_date')

    def project_name(self):
        return self.in_sample.in_project

    def __unicode__(self):
        return '%s-%s-%d-%s-%s: %d' %(self.in_sample.in_project, self.in_sample.sample_name, self.grain, self.ft_type, self.worker.username, self.result)
