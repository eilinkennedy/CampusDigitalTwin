from django import template


register = template.Library()


@register.filter
def getattribute(value, attr):
    return getattr(value, attr)