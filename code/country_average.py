import salem

shape_path = "../inputs/"
land = salem.read_shapefile(shape_path + "ne_110m_land.shp", cached=True)
mask = ds.salem.roi(shape=land, all_touched=True)