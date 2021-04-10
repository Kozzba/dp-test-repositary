from qgis import processing
from qgis.core import QgsVectorLayer, QgsProject, QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsLayerTreeLayer, \
    QgsDistanceArea


class GtfsZones:
    def __init__(self, gpkg_path):
        self.gpkg_path = gpkg_path

    def voronoi(self):
        layer_stops = self.gpkg_path + '|layername=stops'
        # creates voronoi polygons
        processing.run("qgis:voronoipolygons", {
            'INPUT': layer_stops,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"voronoi\" (geom)'
        })

        _layer_stops = QgsVectorLayer(layer_stops, "stops", "ogr")
        _layer_stops.selectByExpression("\"zone_id\" in ('P','0','B') and \"location_type\" = 0")
        self._saveIntoGpkg(_layer_stops,'layer_stops_selected')

        layer_stops_selected = self._createVectorLayer('layer_stops_selected')
        processing.run("native:deleteduplicategeometries", {
            'INPUT': layer_stops_selected,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"stops_zoneP0B\" (geom)'
        })

        layer_voronoi = self._createVectorLayer('voronoi')
        layer_zoneP0B = self._createVectorLayer('stops_zoneP0B')
        # select voronoi polygons intersect with stops
        self._selectbylocation(layer_voronoi, layer_zoneP0B)

        self._saveIntoGpkg(layer_voronoi, 'zoneP0B_voronoi')

        layer_zoneP0B_voronoi = self._createVectorLayer('zoneP0B_voronoi')
        # combine features into new features
        self._dissolve(layer_zoneP0B_voronoi, 'zoneP0B_voronoi_dissolve')

        layer_zoneP0B_voronoi_dissolve = self._createVectorLayer('zoneP0B_voronoi_dissolve')
        self._multiparttosingleparts(layer_zoneP0B_voronoi_dissolve, 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_singleparts\" (geom)')

        layer_zoneP0B_singleparts = self._createVectorLayer('zoneP0B_singleparts')
        layer_zoneP0B_singleparts.selectByExpression('$area = maximum($area, "zone_id")')
        self._saveIntoGpkg(layer_zoneP0B_singleparts,'zoneP0B_max')

        layer_zoneP0B_max = self._createVectorLayer('zoneP0B_max')
        processing.run("native:deleteholes", {
            'INPUT': layer_zoneP0B_max, 'MIN_AREA': 500,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_without_holes\" (geom)'
        })

        self.zones = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
        list_zones = []

        for i in self.zones:
            # select stops by zone_id
            _layer_stops = QgsVectorLayer(layer_stops, "stops", "ogr")
            _layer_stops.selectByExpression("\"zone_id\" = " + i + "and \"location_type\" = 0")

            self._saveIntoGpkg(_layer_stops, 'stops_zone' + i)

            layer_zoneI = self._createVectorLayer('stops_zone' + i)

            # select voronoi polygons intersect with stops
            self._selectbylocation(layer_voronoi, layer_zoneI)

            self._saveIntoGpkg(layer_voronoi, 'zone' + i + '_voronoi')

            layer_zoneI_voronoi = self._createVectorLayer('zone' + i + '_voronoi')

            # combine features into new features
            self._dissolve(layer_zoneI_voronoi, 'zone' + i + '_voronoi_dissolve')

            list_zones.append(self.gpkg_path + '|layername=zone' + i + '_voronoi_dissolve')
        list_zones.append(self.gpkg_path + '|layername=zoneP0B_without_holes')

        # self._deleteLayer('voronoi')
        # self._deleteLayer('layer_stops_selected')
        # for i in zones:
                # self._deleteLayer('stops_zone' + i)
                # self._deleteLayer('zone' + i + '_voronoi')
        # self._deleteLayer('stops_zoneP0B')
        self._deleteLayer('zoneP0B_voronoi')
        self._deleteLayer('zoneP0B_singleparts')
        self._deleteLayer('zoneP0B_max')

        # merge layers of all zones
        self._mergevectorlayers(list_zones, 'zones')

        # insert zones layer to gtfs import group
        zones_layer = QgsProject.instance().addMapLayer(self._createVectorLayer('zones'), False)

        root = QgsProject.instance().layerTreeRoot()
        group_gtfs = root.findGroup('zones')
        group_gtfs.insertChildNode(0, QgsLayerTreeLayer(zones_layer))

        # self._deleteLayer('zoneP0B_voronoi_dissolve')
        # for i in zones:
        #     self._deleteLayer('zone' + i + '_voronoi_dissolve')

        self._smooth()

    def _createVectorLayer(self, layer_name):
        '''
        creates vector layer
        '''
        path_to_layer = self.gpkg_path + '|layername=' + layer_name
        layer = QgsVectorLayer(path_to_layer, layer_name, "ogr")
        return layer

    def _deleteLayer(self, layer_name):
        '''
        deletes layer into GeoPackage
        '''
        try:
            processing.run("native:spatialiteexecutesql", {
                'DATABASE': '{0}|layername={1}'.format(self.gpkg_path, layer_name),
                'SQL': 'drop table {0}'.format(layer_name)
            })
        except IndexError:
            layer_name = None

    def _saveIntoGpkg(self, layer, layer_name):
        '''
        saves layer into GeoPackage
        '''
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        options.driverName = 'GPKG'
        options.layerName = layer_name
        options.onlySelectedFeatures = True
        options.destCRS = QgsCoordinateReferenceSystem(4326)
        QgsVectorFileWriter.writeAsVectorFormat(layer, self.gpkg_path, options)

    def _dissolve(self, input, output, field = []):
        return processing.run("qgis:dissolve", {
                'FIELD': field,
                'INPUT': input,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"' + output + '\" (geom)'
        })

    def _selectbylocation(self, input, intersect, method = 0, predicate = [0]):
        return processing.run("qgis:selectbylocation", {
            'INPUT': input,
            'INTERSECT': intersect,
            'METHOD': method,
            'PREDICATE': predicate
        })

    def _mergevectorlayers(self, layers, output, crs = QgsCoordinateReferenceSystem('EPSG:4326')):
        return processing.run("qgis:mergevectorlayers", {
            'CRS': crs,
            'LAYERS': layers,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"' + output + '\" (geom)'
        })

    def _multiparttosingleparts(self, input, output):
        return processing.run("native:multiparttosingleparts", {
            'INPUT': input,
            'OUTPUT': output
        })

    def _smoothgeometry(self, input, output, iterations = 10, offset = 0.25, max_angle = 180):
        return processing.run('qgis:smoothgeometry', {
            'INPUT': self.gpkg_path + '|layername=' + input,
            'ITERATIONS': iterations,
            'OFFSET': offset,
            'MAX_ANGLE': max_angle,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"' + output + '\" (geom)'
        })

    def _smooth(self):
        '''
        Extract Vertices >>> Merge vector layers >>> Concave hull (alpha shapes) >>> Simplify >>> Smooth
        '''

        expressionP0B = "zone_id not in ('P', 'B', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9') " \
                        "and (zone_id like '%B%' or zone_id like '%P%' or zone_id like '%0%')"
        self._smooth_process('P0B', expressionP0B)

        list_zones_smoothed = []
        for i in self.zones:

            self._smooth_process(i,"zone_id LIKE '" + i + "," + str(int(i)+1) + "'")

            list_zones_smoothed.append(self.gpkg_path + '|layername=zone' + i + '_concaveHull_smoothed')

        list_zones_diff = []
        for i in range(len(list_zones_smoothed) - 1):
            processing.run("qgis:difference", {
                'INPUT': list_zones_smoothed[i+1],
                'OVERLAY': list_zones_smoothed[i],
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + str(i+1) + '_smoothed_diff\" (geom)'
            })

            diff = self._createVectorLayer('zone' + str(i+1) + '_smoothed_diff')

            d = QgsDistanceArea()
            d.setEllipsoid('WGS84')

            diff.startEditing()
            feats = []
            for feat in diff.getFeatures():
                geom = feat.geometry()
                if d.measureArea(geom) / 1e6 < 50:
                    feats.append(feat.id())
                diff.deleteFeatures(feats)
            diff.commitChanges()
            diff.updateExtents()

            list_zones_diff.append(self.gpkg_path + '|layername=zone' + str(i+1) + '_smoothed_diff')
        list_zones_diff.append(list_zones_smoothed[0])
        list_zones_diff.append(self.gpkg_path + '|layername=zoneP0B_concaveHull_smoothed')

        self._mergevectorlayers(list_zones_diff, 'zones_smoothed')

        processing.run("qgis:collect", {
            'INPUT': self.gpkg_path + '|layername=zones_smoothed',
            'FIELD': ['zone_id'],
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zones_smoothed_collected\" (geom)'
        })

        root = QgsProject.instance().layerTreeRoot()
        group_gtfs = root.findGroup('zones')
        smooth_layer = QgsProject.instance().addMapLayer(self._createVectorLayer('zones_smoothed_collected'), False)
        group_gtfs.insertChildNode(0, QgsLayerTreeLayer(smooth_layer))


    def _smooth_process(self, zone_id, expression):
        '''
        select border stops >>> Extract vertices >>> Concave Hull >>> Simplify Geometries >>> Smooth
        '''

        layer_stops = self._createVectorLayer('stops')
        layer_stops.selectByExpression(expression)
        self._saveIntoGpkg(layer_stops, 'stops_border_zone' + zone_id)

        self._border_zones(zone_id)

        # extract vertices (polygon to nodes)
        processing.run('qgis:extractvertices', {
            'INPUT': self.gpkg_path + '|layername=zone' + zone_id + '_voronoi_dissolve',
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + zone_id + '_vertices\" (geom)'
        })

        # merge stops_zoneI + stops_border_zoneI + zoneI_vertices
        zoneI_vertices_stops = [self.gpkg_path + '|layername=stops_zone' + zone_id, 
                                self.gpkg_path + '|layername=stops_border_zone' + zone_id, 
                                self.gpkg_path + '|layername=zone' + zone_id + '_vertices']

        self._mergevectorlayers(zoneI_vertices_stops, 'zone' + zone_id + '_vertices_stops')

        processing.run("qgis:concavehull", {
            'INPUT': self.gpkg_path + '|layername=zone' + zone_id + '_vertices_stops',
            'ALPHA': 0.09,
            'HOLES': False,
            'NO_MULTIGEOMETRY': True,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + zone_id + '_concaveHull\" (geom)'
        })

        processing.run("qgis:simplifygeometries", {
            'INPUT': self.gpkg_path + '|layername=zone' + zone_id + '_concaveHull',
            'METHOD': 0,
            'TOLERANCE': 0.005,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + zone_id + '_concaveHull_simplified\" (geom)'
        })

        self._smoothgeometry('zone' + zone_id + '_concaveHull_simplified', 'zone' + zone_id + '_concaveHull_smoothed')
        self._smoothgeometry('border_voronoi_dissolve_singleparts_counted_zone' + zone_id + '_moreThanTwo', 'border_zone' + zone_id +'_smooth')
        # processing.run('qgis:smoothgeometry', {
        #     'INPUT': self.gpkg_path + '|layername=zone' + zone_id + '_concaveHull_simplified',
        #     'ITERATIONS': 10,
        #     'OFFSET': 0.25,
        #     'MAX_ANGLE': 180,
        #     'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + zone_id + '_concaveHull_smoothed\" (geom)'
        # })

        layer = self._createVectorLayer('zone' + zone_id + '_concaveHull_smoothed')

        layer.startEditing()
        zone_id_idx = layer.fields().lookupField('zone_id')
        for feat in layer.getFeatures():
            layer.changeAttributeValue(feat.id(), zone_id_idx, zone_id)
        layer.commitChanges()

        self._saveIntoGpkg(layer,'zone' + zone_id + '_concaveHull_smoothed')

    def _border_zones(self, zone_id):
        '''
        border layer and voronoi layer >>> Select by location >>> Dissolve >>> Multipart to singleparts >>>
        Count Points in Polygon
        '''

        layer_border = self._createVectorLayer('stops_border_zone' + zone_id)
        layer_voronoi = self._createVectorLayer('voronoi')
        self._selectbylocation(layer_voronoi, layer_border)

        self._saveIntoGpkg(layer_voronoi, 'border_voronoi_zone' + zone_id)
        layer_border_zone_voronoi = self._createVectorLayer('border_voronoi_zone' + zone_id)

        self._dissolve(layer_border_zone_voronoi, 'border_voronoi_dissolve_zone' + zone_id)

        layer_border_voronoi_dissolve_zone = self._createVectorLayer('border_voronoi_dissolve_zone' + zone_id)
        self._multiparttosingleparts(layer_border_voronoi_dissolve_zone, 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"border_voronoi_dissolve_singleparts_zone' + zone_id + '\" (geom)')

        layer_border_voronoi_dissolve_singleparts_zone = self._createVectorLayer('border_voronoi_dissolve_singleparts_zone' + zone_id)
        processing.run("native:countpointsinpolygon", {
            'POLYGONS': layer_border_voronoi_dissolve_singleparts_zone,
            'POINTS': layer_border,
            'FIELD': 'NUMPOINTS',
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"border_voronoi_dissolve_singleparts_counted_zone' + zone_id + '\" (geom)'
        })

        layer_border_voronoi_dissolve_singleparts_counted_zone = self._createVectorLayer('border_voronoi_dissolve_singleparts_counted_zone' + zone_id)
        layer_border_voronoi_dissolve_singleparts_counted_zone.selectByExpression('NUMPOINTS > 2')
        self._saveIntoGpkg(layer_border_voronoi_dissolve_singleparts_counted_zone, 'border_voronoi_dissolve_singleparts_counted_zone' + zone_id + '_moreThanTwo')
