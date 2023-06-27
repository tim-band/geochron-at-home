# Generated by Django 4.1.7 on 2023-06-22 12:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0014_remove_sample_total_grains'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrainPointCategory',
            fields=[
                ('name', models.CharField(max_length=20, primary_key=True, verbose_name='Short unique name for the feature type')),
                ('description', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='GrainPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('x_pixels', models.IntegerField()),
                ('y_pixels', models.IntegerField()),
                ('comment', models.TextField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.grainpointcategory')),
                ('result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.fissiontracknumbering')),
            ],
        ),
    ]