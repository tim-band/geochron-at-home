from ftc.models import Region, Vertex

def save_rois_regions(rois, grain):
    for r in rois['regions']:
        region = Region(grain=grain)
        region.save()
        for v in r['vertices']:
            vertex = Vertex(region=region, x=v[0], y=v[1])
            vertex.save()
