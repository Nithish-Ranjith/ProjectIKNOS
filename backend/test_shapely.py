import json
from shapely.geometry import shape, mapping
from shapely.affinity import scale, rotate

cadastral_geom = {"type":"Polygon","coordinates":[[[80.097164347,16.28734498],[80.097162746,16.287694859],[80.096811634,16.28769336],[80.096813236,16.287343481],[80.097164347,16.28734498]]]}

poly = shape(cadastral_geom)
distorted = scale(poly, xfact=1.02, yfact=1.03, origin='centroid')
distorted = rotate(distorted, angle=0.5, origin='centroid')
distorted = distorted.buffer(0.00005, resolution=4).buffer(-0.00005, resolution=4)
distorted = distorted.simplify(0.00001, preserve_topology=True)

print(mapping(distorted))
