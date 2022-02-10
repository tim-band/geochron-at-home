from django.template import Library

register = Library()

@register.filter_function
def order_by(queryset, argstring):
    args = [x.strip() for x in argstring.split(',')]
    return queryset.order_by(*args)
