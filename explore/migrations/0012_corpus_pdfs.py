# Generated by Django 3.0.6 on 2020-05-25 12:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('explore', '0011_auto_20200505_2005'),
    ]

    operations = [
        migrations.AddField(
            model_name='corpus',
            name='pdfs',
            field=models.TextField(blank=True, null=True),
        ),
    ]
