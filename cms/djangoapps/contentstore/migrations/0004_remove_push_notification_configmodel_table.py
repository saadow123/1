# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-26 20:12
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contentstore', '0003_remove_assets_page_flag'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pushnotificationconfig',
            name='changed_by',
        ),
        migrations.DeleteModel(
            name='PushNotificationConfig',
        ),
    ]