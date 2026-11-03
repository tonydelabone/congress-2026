# US congressional districts 2026

Test data for Viz Maps shape collections: the districts of the 120th Congress (elected in
November 2026), one GeoJSON file per district, served by GitHub Pages so clients can fetch them
directly.

- `districts/{id}.geojson`: a FeatureCollection with one feature; properties `congress`, `fips`,
  `id` (e.g. `TX07`) and `name`, and a bbox. Alaska's bbox crosses the antimeridian (west > east).
- `index.json`: every district with its file and bbox.
- `tools/shp2geojson.py`: the conversion, using the Python standard library only.

## Source and license

[U.S. Congress GIS Database](https://simplemaps.com/data/congress) (Basic, v2.3) by
simplemaps.com, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Changes: converted from the WGS84 shapefile to GeoJSON, one file per district, coordinates
rounded to 5 decimals.

The Basic set is low resolution. For testing only; not an official source of district
boundaries.
