from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0071_folder_is_public'),
    ]

    operations = [
        migrations.AlterField(
            model_name='File',
            name='folder',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='files', null=True, blank=True, to='documents.folder')
        ),
    ]
