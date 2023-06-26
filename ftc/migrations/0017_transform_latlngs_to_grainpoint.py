from django.db import migrations
import json

def transform_latlngs_to_grainpoints(apps, schema_editor):
    GrainPoint = apps.get_model("ftc", "GrainPoint")
    GrainPointCategory = apps.get_model("ftc", "GrainPointCategory")
    FissionTrackNumbering = apps.get_model("ftc", "FissionTrackNumbering")
    db_alias = schema_editor.connection.alias
    track = GrainPointCategory.objects.using(db_alias).get(name="track")
    points = [
        GrainPoint(
            result=ftn,
            x_pixels=round(lng * ftn.grain.image_width),
            y_pixels=round(ftn.grain.image_height - lat * ftn.grain.image_width),
            category=track
        )
        for ftn in FissionTrackNumbering.objects.using(db_alias).all()
        for (lat, lng) in json.loads(ftn.latlngs) or []
    ]
    GrainPoint.objects.using(db_alias).bulk_create(points)

def transform_grainpoints_to_latlngs(apps, schema_editor):
    GrainPoint = apps.get_model("ftc", "GrainPoint")
    GrainPointCategory = apps.get_model("ftc", "GrainPointCategory")
    FissionTrackNumbering = apps.get_model("ftc", "FissionTrackNumbering")
    db_alias = schema_editor.connection.alias
    track = GrainPointCategory.objects.using(db_alias).get(name="track")
    latlngss = {}
    for gp in GrainPoint.objects.using(db_alias).filter(category=track):
        ftn = gp.result
        grain = ftn.grain
        c = latlngss.get(ftn.pk, [])
        lat = gp.x_pixels / grain.image_width
        lng = (grain.image_height - gp.y_pixels) / grain.image_width
        c.append([lat, lng])
        latlngss[ftn.pk] = c
    for ftn in FissionTrackNumbering.objects.using(db_alias).all():
        if ftn.pk in latlngss:
            ftn.latlngs = json.dumps(latlngss[ftn.pk])
            ftn.save()

class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0016_add_track_category'),
    ]

    operations = [
        migrations.RunPython(
            transform_latlngs_to_grainpoints,
            transform_grainpoints_to_latlngs
        )
    ]
