from django.contrib import admin
from ftc.models import (
    Project, Sample, Grain, FissionTrackNumbering, TutorialResult,
    GrainPoint, GrainPointCategory, TutorialPage, ContainedTrack
)

class GrainInline(admin.TabularInline):
    model = Grain
    extra = 0

class SampleInline(admin.TabularInline):
    model = Sample
    extra = 0

class SampleAdmin(admin.ModelAdmin):
    inlines = [GrainInline]
    model = Sample
    extra = 0

class ProjectAdmin(admin.ModelAdmin):
    #fieldsets = []
    inlines = [SampleInline]
    list_display = (
        'project_name', 'creator', 'create_date',
        'project_description', 'closed', 'priority'
    )

class GrainPointInline(admin.TabularInline):
    model = GrainPoint
    extra = 0

class ContainedTrackInline(admin.TabularInline):
    model = ContainedTrack
    extra = 0

class FissionTrackNumberingAdmin(admin.ModelAdmin):
    list_display = ('id', 'grain', 'ft_type', 'worker', 'result', 'create_date')
    list_filter = ['grain', 'grain__sample', 'grain__sample__in_project']
    inlines = [GrainPointInline, ContainedTrackInline]

class TutorialResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'date')

class GrainPointCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

admin.site.register(Project, ProjectAdmin)

admin.site.register(FissionTrackNumbering, FissionTrackNumberingAdmin)

admin.site.register(TutorialResult, TutorialResultAdmin)

admin.site.register(Sample, SampleAdmin)

admin.site.register(Grain, admin.ModelAdmin)

admin.site.register(GrainPointCategory, GrainPointCategoryAdmin)

admin.site.register(TutorialPage, admin.ModelAdmin)

admin.site.register(ContainedTrack, admin.ModelAdmin)

admin.site.register(GrainPoint, admin.ModelAdmin)
