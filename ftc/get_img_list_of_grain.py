from django.urls import reverse
from ftc.models import Image

def get_grain_images_list(project_name, sample_name, sample_property, grain_nth, ft_type):
    images = Image.objects.filter(
        grain__sample__sample_name=sample_name,
        grain__sample__in_project__project_name=project_name,
        grain__index=grain_nth,
        ft_type=ft_type,
    ).order_by('index')
    return list(map(lambda x: reverse('get_image', args=[x.pk]), images))
