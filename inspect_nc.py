"""Inspect the downloaded ERA5 pressure-level NetCDF."""
import netCDF4 as nc
ds = nc.Dataset('data/amphan_2020_plevel_850hpa.nc')
print('Variables:', list(ds.variables.keys()))
print('Dimensions:', {k: len(v) for k, v in ds.dimensions.items()})
for v in ds.variables:
    var = ds.variables[v]
    units = getattr(var, 'units', '?')
    print(f'  {v}: shape={var.shape}, units={units}')
ds.close()
