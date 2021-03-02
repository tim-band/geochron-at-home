from ftc.models import Image

def get_grain_images_list(grain_pool_path, owner, project_name, sample_name, sample_property, grain_nth, ft_type):
    images = Image.objects.filter(grain__sample__sample_name=sample_name,
        grain__sample__in_project__project_name=project_name,
        grain__index=grain_nth).order_by('index').values_list('index', flat=True)
    return list(map(lambda x:'/ftc/image/{0}/{1}/{2}/{3}'.format(
        project_name, sample_name, grain_nth, x), images))
