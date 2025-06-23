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

@register.filter
def get_file_name(value):
    if isinstance(value, str):
        split_value = value.split('\\')[-1]
    return split_value

@register.filter
def subtract(value, arg):
    """
    Subtracts arg from value.
    Example: {{ 100|subtract:completion_percentage }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value
    
@register.filter
def is_previewable(filename):
    return get_file_extension(filename) in ['pdf', 'jpeg', 'jpg', 'png']

@register.filter
def file_type(filename):
    ext = get_file_extension(filename)
    return 'pdf' if ext == 'pdf' else 'image' if ext in ['jpeg', 'jpg', 'png'] else 'other'

@register.filter
def file_icon(filename):
    ext = get_file_extension(filename)
    return {
        'jpeg': 'fa-file-image',
        'jpg': 'fa-file-image',
        'png': 'fa-file-image',
        'pdf': 'fa-file-pdf',
        'docx': 'fa-file-word',
        'csv': 'fa-file-csv',
        'xlsx': 'fa-file-excel'
    }.get(ext, 'fa-file')

@register.filter
def file_color(filename):
    ext = get_file_extension(filename)
    return {
        'jpeg': '#08428e',
        'jpg': '#08428e',
        'png': '#08428e',
        'pdf': '#a10707',
        'docx': '#2a6ec6',
        'csv': '#178939',
        'xlsx': '#178939'
    }.get(ext, '#0e0f11')