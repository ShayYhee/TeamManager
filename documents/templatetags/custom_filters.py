from django import template

register = template.Library()

@register.filter
def extension_is_image(value):
    """Check if the file extension is an image (JPEG, PNG, JPG)."""
    if not value:
        return False
    extension = value.split('.')[-1].lower()
    return extension in ['jpg', 'jpeg', 'png']

@register.filter
def extension_is_pdf(value):
    """Check if the file extension is PDF."""
    if not value:
        return False
    extension = value.split('.')[-1].lower()
    return extension == 'pdf'

@register.filter
def underscore_to_space_upper(value):
    """Replaces underscores with spaces and converts to uppercase."""
    if isinstance(value, str):
        return value.replace('_', ' ').upper()
    return value

@register.filter
def dict_get(obj, key):
    """Access dictionary or object attributes dynamically."""
    try:
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key)
    except:
        return ''
    
@register.filter
def get_file_extension(value):
    if isinstance(value, str):
        split_value = value.split('.')[-1]
    return split_value.lower()
