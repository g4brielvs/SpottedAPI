# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-10-04 21:36
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_auto_20160903_1645'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Greeting',
        ),
    ]
