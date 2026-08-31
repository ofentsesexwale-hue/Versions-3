from django.db import migrations, models


def backfill_digits(apps, schema_editor):
    def fill(model):
        for row in model.objects.all().iterator():
            digits = ''.join(ch for ch in (row.id_number or '') if ch.isdigit())
            if row.id_number_digits != digits:
                model.objects.filter(pk=row.pk).update(id_number_digits=digits)

    fill(apps.get_model('core', 'Caregiver'))
    fill(apps.get_model('core', 'HouseholdMember'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_docs_and_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='caregiver',
            name='id_number_digits',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='householdmember',
            name='id_number_digits',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.RunPython(backfill_digits, migrations.RunPython.noop),
    ]
