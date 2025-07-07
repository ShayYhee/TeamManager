# tenants/migrations/000X_auto_fix_schema_name.py
from django.db import migrations

def set_schema_names(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    for tenant in Tenant.objects.all():
        if not tenant.schema_name:
            tenant.schema_name = f'tenant_{tenant.slug.replace("-", "_")}'
            tenant.save()

class Migration(migrations.Migration):
    dependencies = [
        ('tenants', 'previous_migration'),  # Replace with your latest migration
    ]
    operations = [
        migrations.RunPython(set_schema_names),
    ]