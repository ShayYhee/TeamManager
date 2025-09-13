from django.db import migrations, models
import os
import uuid
import shutil
from django.conf import settings
from django.db.models import Count

def upload_to_folder(instance, filename):
    tenant_name = instance.tenant.name if instance.tenant else "default"
    username = instance.uploaded_by.username if instance.uploaded_by else "anonymous"
    folder_name = instance.folder.name if instance.folder else "unassigned"
    return os.path.join('uploads', tenant_name, username, folder_name, filename)

def migrate_public_folders_and_files(apps, schema_editor):
    PublicFolder = apps.get_model('documents', 'PublicFolder')
    PublicFile = apps.get_model('documents', 'PublicFile')
    Folder = apps.get_model('documents', 'Folder')
    File = apps.get_model('documents', 'File')

    public_folder_to_folder_map = {}
    default_folders = {}

    # Step 1: Identify duplicate share_tokens in PublicFile
    duplicate_tokens = (
        PublicFile.objects.values('share_token')
        .annotate(token_count=Count('share_token'))
        .filter(token_count__gt=1)
    )
    duplicate_token_values = {item['share_token'] for item in duplicate_tokens}
    print(f"Found {len(duplicate_token_values)} share_token values with duplicates in PublicFile.")

    # Step 2: Create default "unassigned" folders for PublicFile with folder=None
    for public_file in PublicFile.objects.filter(folder__isnull=True):
        key = (public_file.tenant_id, public_file.created_by_id)
        if key not in default_folders:
            default_folder = Folder(
                tenant=public_file.tenant,
                name="unassigned",
                created_by=public_file.created_by,
                is_public=True
            )
            try:
                default_folder.save()
                default_folders[key] = default_folder.id
            except Exception:
                default_folder = Folder.objects.get(
                    tenant=public_file.tenant,
                    name="unassigned",
                    created_by=public_file.created_by,
                    is_public=True
                )
                default_folders[key] = default_folder.id

    # Step 3: Migrate PublicFolder to Folder
    for public_folder in PublicFolder.objects.all():
        new_folder = Folder(
            tenant=public_folder.tenant,
            name=public_folder.name,
            parent=None,
            created_by=public_folder.created_by,
            created_at=public_folder.created_at,
            is_public=True
        )
        try:
            new_folder.save()
            public_folder_to_folder_map[public_folder.id] = new_folder.id
        except Exception:
            new_folder.name = f"{public_folder.name}_public"
            new_folder.save()
            public_folder_to_folder_map[public_folder.id] = new_folder.id

    # Step 4: Update parent relationships
    for public_folder in PublicFolder.objects.all():
        if public_folder.parent_id:
            new_folder = Folder.objects.get(id=public_folder_to_folder_map[public_folder.id])
            new_folder.parent_id = public_folder_to_folder_map.get(public_folder.parent_id)
            new_folder.save()

    # Step 5: Migrate PublicFile to File
    used_share_tokens = set(File.objects.values_list('share_token', flat=True).exclude(share_token__isnull=True))
    for public_file in PublicFile.objects.all():
        # Check for existing File with same tenant, uploaded_by, and original_name
        existing_file = File.objects.filter(
            tenant=public_file.tenant,
            uploaded_by=public_file.created_by,
            original_name=public_file.original_name
        ).first()

        if existing_file:
            print(f"Skipping PublicFile '{public_file.original_name}' (ID: {public_file.id}) as it already exists in File (ID: {existing_file.id})")
            continue  # Skip duplicate file

        new_folder_id = public_folder_to_folder_map.get(public_file.folder_id) if public_file.folder_id else default_folders.get((public_file.tenant_id, public_file.created_by_id))
        new_folder = Folder.objects.get(id=new_folder_id) if new_folder_id else None

        # Handle share_token: regenerate if it's a duplicate or already used
        share_token = public_file.share_token
        if share_token in duplicate_token_values or share_token in used_share_tokens:
            share_token = str(uuid.uuid4())
            print(f"Generated new share_token for PublicFile '{public_file.original_name}' (ID: {public_file.id}): {share_token}")

        new_file = File(
            tenant=public_file.tenant,
            folder=new_folder,
            uploaded_by=public_file.created_by,
            original_name=public_file.original_name,
            uploaded_at=public_file.created_at,
            is_public=True,
            share_token=share_token,
            is_shared=public_file.is_shared,
            shared_by=public_file.shared_by
        )

        # Copy file to new path if it exists
        old_path = public_file.file.path
        new_path = upload_to_folder(new_file, public_file.original_name)
        new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
        os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
        if os.path.exists(old_path):
            if os.path.exists(new_full_path):
                base, ext = os.path.splitext(new_path)
                new_path = f"{base}_public{ext}"
                new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
            try:
                shutil.copy2(old_path, new_full_path)
                new_file.file.name = new_path
            except Exception as e:
                print(f"Error copying file {old_path} to {new_full_path} for PublicFile ID {public_file.id}: {str(e)}")
        else:
            print(f"Warning: File {old_path} not found for PublicFile ID {public_file.id}")
            new_file.file.name = ''  # Set file field to empty to allow saving

        try:
            new_file.save()
            used_share_tokens.add(share_token)
        except Exception as e:
            print(f"Error saving File for PublicFile '{public_file.original_name}' (ID: {public_file.id}): {str(e)}")
            # Try again with a new share_token
            new_file.share_token = str(uuid.uuid4())
            try:
                new_file.save()
                used_share_tokens.add(new_file.share_token)
                print(f"Generated new share_token for PublicFile '{public_file.original_name}' due to conflict: {new_file.share_token}")
            except Exception as e:
                print(f"Failed to save File for PublicFile '{public_file.original_name}' (ID: {public_file.id}) after retry: {str(e)}")
                continue  # Skip to avoid transaction failure

def reverse_migration(apps, schema_editor):
    Folder = apps.get_model('documents', 'Folder')
    File = apps.get_model('documents', 'File')
    # Delete migrated folders and files
    Folder.objects.filter(is_public=True).delete()
    File.objects.filter(is_public=True).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0072_alter_file_folder'),
    ]

    operations = [
        migrations.RunPython(
            code=migrate_public_folders_and_files,
            reverse_code=reverse_migration,
        ),
    ]