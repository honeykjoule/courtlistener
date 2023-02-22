# Generated by Django 3.2.16 on 2023-01-20 05:34

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import pgtrigger.compiler
import pgtrigger.migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0010_auto_20230116_0550'),
        ('pghistory', '0005_events_middlewareevents'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('audio', '0001_initial'),
        ('favorites', '0003_alter_note_fields_noop'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocketTagEvent',
            fields=[
                ('pgh_id', models.AutoField(primary_key=True, serialize=False)),
                ('pgh_created_at', models.DateTimeField(auto_now_add=True)),
                ('pgh_label', models.TextField(help_text='The event label.')),
                ('id', models.IntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='NoteEvent',
            fields=[
                ('pgh_id', models.AutoField(primary_key=True, serialize=False)),
                ('pgh_created_at', models.DateTimeField(auto_now_add=True)),
                ('pgh_label', models.TextField(help_text='The event label.')),
                ('id', models.IntegerField()),
                ('date_created', models.DateTimeField(auto_now_add=True, help_text='The original creation date for the item')),
                ('date_modified', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=100, verbose_name='a name for the alert')),
                ('notes', models.TextField(blank=True, max_length=500, validators=[django.core.validators.MaxLengthValidator(500)], verbose_name='notes about the item saved')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PrayerEvent',
            fields=[
                ('pgh_id', models.AutoField(primary_key=True, serialize=False)),
                ('pgh_created_at', models.DateTimeField(auto_now_add=True)),
                ('pgh_label', models.TextField(help_text='The event label.')),
                ('id', models.IntegerField()),
                ('date_created', models.DateTimeField(auto_now_add=True, help_text='The time when this item was created')),
                ('status', models.SmallIntegerField(choices=[(1, 'Still waiting for the document.'), (2, 'Prayer has been granted.')], default=1, help_text='Whether the prayer has been granted or is still waiting.')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='UserTagEvent',
            fields=[
                ('pgh_id', models.AutoField(primary_key=True, serialize=False)),
                ('pgh_created_at', models.DateTimeField(auto_now_add=True)),
                ('pgh_label', models.TextField(help_text='The event label.')),
                ('id', models.IntegerField()),
                ('date_created', models.DateTimeField(auto_now_add=True, help_text='The moment when the item was created.')),
                ('date_modified', models.DateTimeField(auto_now=True, help_text='The last moment when the item was modified. A value in year 1750 indicates the value is unknown')),
                ('name', models.SlugField(db_index=False, help_text='The name of the tag')),
                ('title', models.TextField(blank=True, help_text='A title for the tag')),
                ('description', models.TextField(blank=True, help_text='The description of the tag in Markdown format')),
                ('published', models.BooleanField(default=False, help_text='Whether the tag has been shared publicly.')),
            ],
            options={
                'abstract': False,
            },
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='dockettag',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "favorites_dockettagevent" ("docket_id", "id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "tag_id") VALUES (NEW."docket_id", NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."tag_id"); RETURN NULL;', hash='29317d5fa7f67f1673d3e8629f95ad1d4611680a', operation='INSERT', pgid='pgtrigger_snapshot_insert_d9def', table='favorites_dockettag', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='dockettag',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD.* IS DISTINCT FROM NEW.*)', func='INSERT INTO "favorites_dockettagevent" ("docket_id", "id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "tag_id") VALUES (NEW."docket_id", NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."tag_id"); RETURN NULL;', hash='741d5f0b8e26c83cdc757b4924fbd3cc22a7ecfc', operation='UPDATE', pgid='pgtrigger_snapshot_update_2cb4a', table='favorites_dockettag', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='note',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "favorites_noteevent" ("audio_id_id", "cluster_id_id", "date_created", "date_modified", "docket_id_id", "id", "name", "notes", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "recap_doc_id_id", "user_id") VALUES (NEW."audio_id_id", NEW."cluster_id_id", NEW."date_created", NEW."date_modified", NEW."docket_id_id", NEW."id", NEW."name", NEW."notes", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."recap_doc_id_id", NEW."user_id"); RETURN NULL;', hash='3783aab50aab2ed0ac3eae8e6e6b70f2f72cef6a', operation='INSERT', pgid='pgtrigger_snapshot_insert_7e480', table='favorites_note', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='note',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD.* IS DISTINCT FROM NEW.*)', func='INSERT INTO "favorites_noteevent" ("audio_id_id", "cluster_id_id", "date_created", "date_modified", "docket_id_id", "id", "name", "notes", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "recap_doc_id_id", "user_id") VALUES (NEW."audio_id_id", NEW."cluster_id_id", NEW."date_created", NEW."date_modified", NEW."docket_id_id", NEW."id", NEW."name", NEW."notes", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."recap_doc_id_id", NEW."user_id"); RETURN NULL;', hash='a8a09a17456f083920b6e36d8c7f6e2695aa0b4d', operation='UPDATE', pgid='pgtrigger_snapshot_update_cc74c', table='favorites_note', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='prayer',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "favorites_prayerevent" ("date_created", "id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "recap_document_id", "status", "user_id") VALUES (NEW."date_created", NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."recap_document_id", NEW."status", NEW."user_id"); RETURN NULL;', hash='96821b8db3f57317a614f51f61d735a30970305e', operation='INSERT', pgid='pgtrigger_snapshot_insert_9becd', table='favorites_prayer', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='prayer',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD.* IS DISTINCT FROM NEW.*)', func='INSERT INTO "favorites_prayerevent" ("date_created", "id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "recap_document_id", "status", "user_id") VALUES (NEW."date_created", NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."recap_document_id", NEW."status", NEW."user_id"); RETURN NULL;', hash='43216b61a7ffdd9308b5e6064efd9276d791b9ec', operation='UPDATE', pgid='pgtrigger_snapshot_update_8f75d', table='favorites_prayer', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='usertag',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_insert', sql=pgtrigger.compiler.UpsertTriggerSql(func='INSERT INTO "favorites_usertagevent" ("date_created", "date_modified", "description", "id", "name", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "published", "title", "user_id") VALUES (NEW."date_created", NEW."date_modified", NEW."description", NEW."id", NEW."name", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."published", NEW."title", NEW."user_id"); RETURN NULL;', hash='d24099cd7f1c3d33a6410d564e6ede52c12bec1e', operation='INSERT', pgid='pgtrigger_snapshot_insert_38cf8', table='favorites_usertag', when='AFTER')),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name='usertag',
            trigger=pgtrigger.compiler.Trigger(name='snapshot_update', sql=pgtrigger.compiler.UpsertTriggerSql(condition='WHEN (OLD."id" IS DISTINCT FROM NEW."id" OR OLD."date_created" IS DISTINCT FROM NEW."date_created" OR OLD."date_modified" IS DISTINCT FROM NEW."date_modified" OR OLD."user_id" IS DISTINCT FROM NEW."user_id" OR OLD."name" IS DISTINCT FROM NEW."name" OR OLD."title" IS DISTINCT FROM NEW."title" OR OLD."description" IS DISTINCT FROM NEW."description" OR OLD."published" IS DISTINCT FROM NEW."published")', func='INSERT INTO "favorites_usertagevent" ("date_created", "date_modified", "description", "id", "name", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "published", "title", "user_id") VALUES (NEW."date_created", NEW."date_modified", NEW."description", NEW."id", NEW."name", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."published", NEW."title", NEW."user_id"); RETURN NULL;', hash='620a5e1618c400875c028db158d92e5c0bdd520d', operation='UPDATE', pgid='pgtrigger_snapshot_update_8ec9c', table='favorites_usertag', when='AFTER')),
        ),
        migrations.AddField(
            model_name='usertagevent',
            name='pgh_context',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pghistory.context'),
        ),
        migrations.AddField(
            model_name='usertagevent',
            name='pgh_obj',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='event', to='favorites.usertag'),
        ),
        migrations.AddField(
            model_name='usertagevent',
            name='user',
            field=models.ForeignKey(db_constraint=False, help_text='The user that created the tag', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='prayerevent',
            name='pgh_context',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pghistory.context'),
        ),
        migrations.AddField(
            model_name='prayerevent',
            name='pgh_obj',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='event', to='favorites.prayer'),
        ),
        migrations.AddField(
            model_name='prayerevent',
            name='recap_document',
            field=models.ForeignKey(db_constraint=False, help_text="The document you're praying for.", on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='search.recapdocument'),
        ),
        migrations.AddField(
            model_name='prayerevent',
            name='user',
            field=models.ForeignKey(db_constraint=False, help_text='The user that made the prayer', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='audio_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='audio.audio', verbose_name='the audio file that is saved'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='cluster_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='search.opinioncluster', verbose_name='the opinion cluster that is saved'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='docket_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='search.docket', verbose_name='the docket that is saved'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='pgh_context',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pghistory.context'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='pgh_obj',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='event', to='favorites.note'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='recap_doc_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='search.recapdocument', verbose_name='the RECAP document that is saved'),
        ),
        migrations.AddField(
            model_name='noteevent',
            name='user',
            field=models.ForeignKey(db_constraint=False, help_text='The user that owns the note', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dockettagevent',
            name='docket',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='search.docket'),
        ),
        migrations.AddField(
            model_name='dockettagevent',
            name='pgh_context',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='pghistory.context'),
        ),
        migrations.AddField(
            model_name='dockettagevent',
            name='pgh_obj',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='event', to='favorites.dockettag'),
        ),
        migrations.AddField(
            model_name='dockettagevent',
            name='tag',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', related_query_name='+', to='favorites.usertag'),
        ),
    ]