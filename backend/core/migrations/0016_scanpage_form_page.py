from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_scan_alignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanintakepage',
            name='form_page',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
