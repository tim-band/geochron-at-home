# Generated by Django 4.1.7 on 2023-03-09 19:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ftc', '0012_remove_fissiontracknumbering_grain_index_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fissiontracknumbering',
            name='grain',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='results', to='ftc.grain'),
        ),
    ]
