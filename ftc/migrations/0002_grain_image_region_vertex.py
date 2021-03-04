# Generated by Django 3.1.6 on 2021-03-04 10:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Grain',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.IntegerField()),
                ('image_width', models.IntegerField()),
                ('image_height', models.IntegerField()),
                ('sample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.sample')),
            ],
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shift_x', models.IntegerField()),
                ('shift_y', models.IntegerField()),
                ('grain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.grain')),
            ],
        ),
        migrations.CreateModel(
            name='Vertex',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('x', models.IntegerField()),
                ('y', models.IntegerField()),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.region')),
            ],
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('format', models.CharField(choices=[('J', 'JPEG'), ('P', 'PNG')], max_length=1)),
                ('ft_type', models.CharField(choices=[('S', 'Spontaneous Fission Tracks'), ('I', 'Induced Fission Tracks')], max_length=1)),
                ('index', models.IntegerField()),
                ('data', models.BinaryField()),
                ('grain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ftc.grain')),
            ],
        ),
    ]
