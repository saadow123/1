# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('credit', '0007_creditrequirement_copy_values'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='creditrequirement',
            name='order',
        ),
    ]