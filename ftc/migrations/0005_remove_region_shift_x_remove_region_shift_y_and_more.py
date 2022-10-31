# Generated by Django 4.0.6 on 2022-07-20 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0004_grain_metadata'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='region',
            name='shift_x',
        ),
        migrations.RemoveField(
            model_name='region',
            name='shift_y',
        ),
        migrations.AddField(
            model_name='grain',
            name='shift_x',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='grain',
            name='shift_y',
            field=models.IntegerField(default=0),
        ),
    ]