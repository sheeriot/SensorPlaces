from django import template

register = template.Library()

@register.filter
def filter_active(queryset):
    return [obj for obj in queryset if obj.is_active]

@register.filter
def filter_inactive(queryset):
    return [obj for obj in queryset if not obj.is_active]

@register.filter
def subtract(value, arg):
    return value - arg 