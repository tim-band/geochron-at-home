from django.contrib import admin
from ftc.models import Project, Sample, Grain, FissionTrackNumbering, TutorialResult

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

class FissionTrackNumberingAdmin(admin.ModelAdmin):
    list_display = ('grain', 'ft_type', 'worker', 'result', 'create_date')
    list_filter = ['grain', 'grain__sample', 'grain__sample__in_project']

class TutorialResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'date')

admin.site.register(Project, ProjectAdmin)

admin.site.register(FissionTrackNumbering, FissionTrackNumberingAdmin)

admin.site.register(TutorialResult, TutorialResultAdmin)

admin.site.register(Sample, SampleAdmin)
