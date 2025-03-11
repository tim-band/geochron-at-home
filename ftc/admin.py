from django.contrib import admin
from ftc.models import (
    Project, Sample, Grain, FissionTrackNumbering, TutorialResult,
    GrainPoint, GrainPointCategory, TutorialPage, ContainedTrack,
    Region
)

class GrainInline(admin.TabularInline):
    model = Grain
    extra = 0

class SampleInline(admin.TabularInline):
    model = Sample
    extra = 0

@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    inlines = [GrainInline]
    model = Sample
    extra = 0

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    #fieldsets = []
    inlines = [SampleInline]
    list_display = (
        'project_name', 'creator', 'create_date',
        'project_description', 'closed', 'priority'
    )
    filter_horizontal = (
        'groups_who_have_access',
    )

class GrainPointInline(admin.TabularInline):
    model = GrainPoint
    extra = 0

class ContainedTrackInline(admin.TabularInline):
    model = ContainedTrack
    extra = 0

@admin.register(FissionTrackNumbering)
class FissionTrackNumberingAdmin(admin.ModelAdmin):
    list_display = ('id', 'grain', 'ft_type', 'worker', 'result', 'create_date', 'analyst')
    list_filter = ['grain', 'grain__sample', 'grain__sample__in_project']
    inlines = [GrainPointInline, ContainedTrackInline]

@admin.register(TutorialResult)
class TutorialResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'date')

@admin.register(GrainPointCategory)
class GrainPointCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['id', 'grain', 'result']
    list_filter = ['grain__sample', 'grain__sample__in_project', 'grain', 'result']

admin.site.register(Grain, admin.ModelAdmin)

admin.site.register(TutorialPage, admin.ModelAdmin)

admin.site.register(ContainedTrack, admin.ModelAdmin)

admin.site.register(GrainPoint, admin.ModelAdmin)
