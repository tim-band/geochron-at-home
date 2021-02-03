from django.contrib import admin
from ftc.models import Project, Sample, FissionTrackNumbering

class SampleInline(admin.TabularInline):
    model = Sample
    extra = 0

class ProjectAdmin(admin.ModelAdmin):
    #fieldsets = []
    inlines = [SampleInline]
    list_display = ('project_name', 'creator', 'create_date', 'project_description', 'closed', 'priority')

class FissionTrackNumberingAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'in_sample', 'grain', 
                    'ft_type', 'worker', 'result', 'create_date')
    list_filter = ['grain']

admin.site.register(Project, ProjectAdmin)

admin.site.register(FissionTrackNumbering, FissionTrackNumberingAdmin)

#admin.site.register(Sample)
