# -*- coding: utf-8 -*-
# Generated by Django 1.11.25 on 2019-10-23 15:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entitlements', '0011_historicalcourseentitlement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseentitlement',
            name='order_number',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourseentitlement',
            name='order_number',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]