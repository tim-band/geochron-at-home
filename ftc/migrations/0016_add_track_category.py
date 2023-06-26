from django.db import migrations

def add_track_category(apps, schema_editor):
    GrainPointCategory = apps.get_model("ftc", "GrainPointCategory")
    db_alias = schema_editor.connection.alias
    GrainPointCategory.objects.using(db_alias).bulk_create([
        GrainPointCategory(name="track", description="Genuine fission track"),
        GrainPointCategory(name="inclusion", description="Inclusion"),
        GrainPointCategory(name="surface", description="Surface mark"),
        GrainPointCategory(name="defect", description="Crystal defect"),
    ])

def remove_track_category(apps, schema_editor):
    GrainPointCategory = apps.get_model("ftc", "GrainPointCategory")
    db_alias = schema_editor.connection.alias
    GrainPointCategory.objects.using(db_alias).filter(name__in=[
        "track", "inclusion", "surface", "defect"
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0015_add_grainpoint_and_category'),
    ]

    operations = [
        migrations.RunPython(add_track_category, remove_track_category)
    ]
