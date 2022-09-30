from django.template import Library

register = Library()

large = ['k', 'M', 'G']
small = ['m', '\xb5', 'n', 'p']

@register.simple_tag
def si_mag(num, decimal_places=2, unit='', none='None'):
    if num is None:
        return none
    sign = ''
    if num < 0:
        num = -num
        sign = '-'
    mag = 0
    while mag < len(large) and 1000 <= num:
        num /= 1000
        mag += 1
    while -mag < len(small) and num < 1:
        num *= 1000
        mag -= 1
    prefix = ''
    if mag < 0:
        prefix = small[-1 - mag]
    elif 0 < mag:
        prefix = large[mag - 1]
    format_string = '{0}{1:.' + str(decimal_places) + 'f}{2}{3}'
    return format_string.format(sign, num, prefix, unit)
