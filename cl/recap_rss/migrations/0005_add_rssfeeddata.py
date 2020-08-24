# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-07-22 23:27
from __future__ import unicode_literals

import cl.lib.storage
import cl.recap_rss.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0096_add_court_fields_and_noops'),
        ('recap_rss', '0004_add_rss_cache'),
    ]

    operations = [
        migrations.CreateModel(
            name='RssFeedData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True, db_index=True, help_text=b'The time when this item was created')),
                ('date_modified', models.DateTimeField(auto_now=True, db_index=True, help_text=b'The last moment when the item was modified.')),
                ('filepath', models.FileField(help_text=b'The path of the file in the local storage area.', max_length=150, storage=cl.lib.storage.UUIDFileSystemStorage(), upload_to=cl.recap_rss.models.make_rss_feed_path)),
                ('court', models.ForeignKey(help_text=b'The court where the RSS feed was found', on_delete=django.db.models.deletion.CASCADE, related_name='rss_feed_data', to='search.Court')),
            ],
        ),
    ]