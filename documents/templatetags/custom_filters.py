from django import template

register = template.Library()

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
