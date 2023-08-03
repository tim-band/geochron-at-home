# Generated by Django 4.1.7 on 2023-08-01 09:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0018_remove_fissiontracknumbering_latlngs_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TutorialPage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_type', models.CharField(choices=[('E', 'Explain category'), ('C', 'Choose category test'), ('I', 'Find category test with immediate result'), ('S', 'Find category test with results after submit')], max_length=1, null=True)),
                ('limit', models.IntegerField(blank=True, null=True)),
                ('message', models.TextField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.grainpointcategory')),
                ('marks', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.fissiontracknumbering')),
            ],
        ),
    ]
