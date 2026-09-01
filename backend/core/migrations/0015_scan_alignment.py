from django.db import migrations, models
import core.models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_scan_intake'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanintakepage',
            name='alignment_failed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='scanintakepage',
            name='geometry_missing',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='scanintakepage',
            name='template_version',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='scanintakepage',
            name='warped_image',
            field=models.ImageField(blank=True, null=True, upload_to=core.models.scan_page_upload_path),
        ),
    ]
