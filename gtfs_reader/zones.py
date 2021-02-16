from qgis import processing
from qgis.core import QgsVectorLayer, QgsProject, QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsLayerTreeLayer


class GtfsZones:
    def __init__(self, gpkg_path):
        self.gpkg_path = gpkg_path

    def voronoi(self):
        layer_stops = self.gpkg_path + '|layername=stops'
        # creates voronoi polygons
        processing.run("qgis:voronoipolygons", {
            'INPUT': layer_stops,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"voronoi\" (geom)'})

        layer_voronoi = self._createVectorLayer('voronoi')

        _layer_stops = QgsVectorLayer(layer_stops, "stops", "ogr")
        _layer_stops.selectByExpression("\"zone_id\" in ('P','0','B')")

        self._saveIntoGpkg(_layer_stops,'layer_stops_selected')

        layer_stops_selected = self._createVectorLayer('layer_stops_selected')

        processing.run("native:deleteduplicategeometries", {
            'INPUT': layer_stops_selected,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"stops_zoneP0B\" (geom)'})

        layer_zoneP0B = self._createVectorLayer('stops_zoneP0B')

        # select voronoi polygons intersect with stops
        processing.run("qgis:selectbylocation", {
            'INPUT': layer_voronoi,
            'INTERSECT': layer_zoneP0B,
            'METHOD': 0,
            'PREDICATE': [0]})

        self._saveIntoGpkg(layer_voronoi, 'zoneP0B_voronoi')

        layer_zoneP0B_voronoi = self._createVectorLayer('zoneP0B_voronoi')

        # combine features into new features
        processing.run("qgis:dissolve", {
            'FIELD': [],
            'INPUT': layer_zoneP0B_voronoi,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_voronoi_dissolve\" (geom)'})

        layer_zoneP0B_voronoi_dissolve = self._createVectorLayer('zoneP0B_voronoi_dissolve')

        processing.run("native:multiparttosingleparts", {
            'INPUT': layer_zoneP0B_voronoi_dissolve,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_singleparts\" (geom)'})

        layer_zoneP0B_singleparts = self._createVectorLayer('zoneP0B_singleparts')

        layer_zoneP0B_singleparts.selectByExpression('$area = maximum($area, "zone_id")')

        self._saveIntoGpkg(layer_zoneP0B_singleparts,'zoneP0B_max')

        layer_zoneP0B_max = self._createVectorLayer('zoneP0B_max')

        processing.run("native:deleteholes", {
            'INPUT': layer_zoneP0B_max, 'MIN_AREA': 500,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_without_holes\" (geom)'})

        zones = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

        for i in zones:
            # select stops by zone_id
            _layer_stops = QgsVectorLayer(layer_stops, "stops", "ogr")
            processing.run("qgis:selectbyattribute", {'FIELD': 'zone_id',
                                                      'INPUT': _layer_stops,
                                                      'METHOD': 0,
                                                      'OPERATOR': 0,
                                                      'VALUE': '' + i + ''})

            self._saveIntoGpkg(_layer_stops, 'stops_zone' + i)

            layer_zoneI = self._createVectorLayer('stops_zone' + i)

            # select voronoi polygons intersect with stops
            processing.run("qgis:selectbylocation", {
                'INPUT': layer_voronoi,
                'INTERSECT': layer_zoneI,
                'METHOD': 0,
                'PREDICATE': [0]})

            self._saveIntoGpkg(layer_voronoi, 'zone' + i + '_voronoi')

            layer_zoneI_voronoi = self._createVectorLayer('zone' + i + '_voronoi')

            # combine features into new features
            processing.run("qgis:dissolve", {
                'FIELD': [],
                'INPUT': layer_zoneI_voronoi,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_voronoi_dissolve\" (geom)'})

        # self._deleteLayer('voronoi')
        # self._deleteLayer('layer_stops_selected')
        # for i in zones:
                # self._deleteLayer('stops_zone' + i)
                # self._deleteLayer('zone' + i + '_voronoi')
        # self._deleteLayer('stops_zoneP0B')
        self._deleteLayer('zoneP0B_voronoi')
        self._deleteLayer('zoneP0B_singleparts')
        self._deleteLayer('zoneP0B_max')


        # # merge layers of zone P,0 and B
        # merge = processing.run("qgis:mergevectorlayers", {'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
        #                                                   'LAYERS': [
        #                                                       self.gpkg_path + '|layername=zone0_voronoi_dissolve',
        #                                                       self.gpkg_path + '|layername=zoneB_voronoi_dissolve',
        #                                                       self.gpkg_path + '|layername=zoneP_voronoi_dissolve'],
        #                                                   'OUTPUT': 'TEMPORARY_OUTPUT'})
        #
        # # combine features into new features
        # processing.run("qgis:dissolve", {
        #     'FIELD': [],
        #     'INPUT': merge['OUTPUT'],
        #     'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_voronoi_dissolve\" (geom)'})

        # merge layers of all zones
        list_zones = []
        for i in zones:
            list_zones.append(self.gpkg_path + '|layername=zone' + i + '_voronoi_dissolve')
        list_zones.append(self.gpkg_path + '|layername=zoneP0B_without_holes')

        processing.run("qgis:mergevectorlayers", {
            'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
            'LAYERS': list_zones,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zones\" (geom)'})

        # insert zones layer to gtfs import group
        path_to_layer = self.gpkg_path + "|layername=zones"
        layer = QgsVectorLayer(path_to_layer, 'zones', "ogr")
        zones_layer = QgsProject.instance().addMapLayer(layer, False)

        root = QgsProject.instance().layerTreeRoot()
        group_gtfs = root.findGroup('zones')
        group_gtfs.insertChildNode(0, QgsLayerTreeLayer(zones_layer))

        # self._deleteLayer('zoneP0B_voronoi_dissolve')
        # for i in zones:
        #     self._deleteLayer('zone' + i + '_voronoi_dissolve')

        self._lang()

    def _createVectorLayer(self, layer_name):
        path_to_layer = self.gpkg_path + '|layername=' + layer_name
        layer = QgsVectorLayer(path_to_layer, layer_name, "ogr")
        return layer

    def _deleteLayer(self, layer_name):
        try:
            processing.run("native:spatialiteexecutesql",
                           {'DATABASE': '{0}|layername={1}'.format(self.gpkg_path, layer_name),
                            'SQL': 'drop table {0}'.format(layer_name)})
        except IndexError:
            layer_name = None

    def _saveIntoGpkg(self, layer, layer_name):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        options.driverName = 'GPKG'
        options.layerName = layer_name
        options.onlySelectedFeatures = True
        options.destCRS = QgsCoordinateReferenceSystem(4326)
        QgsVectorFileWriter.writeAsVectorFormat(layer, self.gpkg_path, options)

    def _lang(self):
        '''
        Lang Simplification Algorithm
        '''

        '''
        Densify By Count >>> Delete holes >>> Smooth (QGIS) || Generalize (Grass)
        '''
        densify_by_count = processing.run('qgis:densifygeometries',
                                        {'INPUT': self.gpkg_path + '|layername=zones',
                                         'VERTICES': 3,
                                         'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"densifyByCount\" ('
                                                                                      'geom)'})

        delete_holes = processing.run('qgis:deleteholes',
                                     {'INPUT': densify_by_count['OUTPUT'],
                                      'MIN_AREA': 30,
                                      'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"deleteHoles\" (geom)'})



        layer_stops = self._createVectorLayer('stops')
        layer_stops.selectByExpression("zone_id not in ('P', 'B', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9') "
                                       "and (zone_id like '%B%' or zone_id like '%P%' or zone_id like '%0%')")
        self._saveIntoGpkg(layer_stops, 'stops_border_zoneP0B')

        processing.run('qgis:extractvertices',
                       {'INPUT': self.gpkg_path + '|layername=zoneP0B_voronoi_dissolve',
                        'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_vertices\" (geom)'})

        zoneP0B_vertices_stops = []
        zoneP0B_vertices_stops.append(self.gpkg_path + '|layername=stops_zoneP0B')
        zoneP0B_vertices_stops.append(self.gpkg_path + '|layername=stops_border_zoneP0B')
        zoneP0B_vertices_stops.append(self.gpkg_path + '|layername=zoneP0B_vertices')

        processing.run("qgis:mergevectorlayers", {
            'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
            'LAYERS': zoneP0B_vertices_stops,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_vertices_stops\" (geom)'})

        processing.run("qgis:concavehull", {
            'INPUT': self.gpkg_path + '|layername=zoneP0B_vertices_stops',
            'ALPHA': 0.09,
            'HOLES': False,
            'NO_MULTIGEOMETRY': True,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_concaveHull\" (geom)'
        })

        processing.run("qgis:simplifygeometries", {
            'INPUT': self.gpkg_path + '|layername=zoneP0B_concaveHull',
            'METHOD': 0,
            'TOLERANCE': 0.005,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_concaveHull_simplified\" (geom)'
        })

        processing.run('qgis:smoothgeometry', {
            'INPUT': self.gpkg_path + '|layername=zoneP0B_concaveHull_simplified',
            'ITERATIONS': 10,
            'OFFSET': 0.25,
            'MAX_ANGLE': 180,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B_concaveHull_smoothed\" (geom)'})



        zones = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

        list_zones_smoothed = []

        for i in zones:
            # extract vertices (polygon to nodes)
            processing.run('qgis:extractvertices',
                           {'INPUT': self.gpkg_path + '|layername=zone' + i + '_voronoi_dissolve',
                            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_vertices\" (geom)'})

            layer_stops = self._createVectorLayer('stops')
            layer_stops.selectByExpression("zone_id LIKE '" + i + ",%' OR zone_id LIKE '%," + i + "'")
            self._saveIntoGpkg(layer_stops,'stops_border_zone' + i)

            # extract_vertices = self._createVectorLayer('extractVertices')
            # extract_vertices.selectByExpression('zone_id = ' + i)
            # self._saveIntoGpkg(extract_vertices, 'zone' + i + '_vertices')

            # merge stops_zoneI + stops_border_zoneI + zoneI_vertices
            zoneI_vertices_stops = []
            zoneI_vertices_stops.append(self.gpkg_path + '|layername=stops_zone' + i)
            zoneI_vertices_stops.append(self.gpkg_path + '|layername=stops_border_zone' + i)
            zoneI_vertices_stops.append(self.gpkg_path + '|layername=zone' + i + '_vertices')

            processing.run("qgis:mergevectorlayers", {
                'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
                'LAYERS': zoneI_vertices_stops,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_vertices_stops\" (geom)'})

            processing.run("qgis:concavehull", {
                'INPUT': self.gpkg_path + '|layername=zone' + i + '_vertices_stops',
                'ALPHA': 0.09,
                'HOLES': False,
                'NO_MULTIGEOMETRY': True,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_concaveHull\" (geom)'
            })

            processing.run("qgis:simplifygeometries", {
                'INPUT': self.gpkg_path + '|layername=zone' + i + '_concaveHull',
                'METHOD': 0,
                'TOLERANCE': 0.005,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_concaveHull_simplified\" (geom)'
            })

            processing.run('qgis:smoothgeometry', {
                'INPUT': self.gpkg_path + '|layername=zone' + i + '_concaveHull_simplified',
                'ITERATIONS': 10,
                'OFFSET': 0.25,
                'MAX_ANGLE': 180,
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + i + '_concaveHull_smoothed\" (geom)'})

            list_zones_smoothed.append(self.gpkg_path + '|layername=zone' + i + '_concaveHull_smoothed')

        list_zones_diff = []
        for i in range(len(list_zones_smoothed) - 1):
            processing.run("qgis:difference", {
                'INPUT': list_zones_smoothed[i+1],
                'OVERLAY': list_zones_smoothed[i],
                'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zone' + str(i+1) + '_smoothed_diff\" (geom)'})
            list_zones_diff.append(self.gpkg_path + '|layername=zone' + str(i+1) + '_smoothed_diff')
        list_zones_diff.append(list_zones_smoothed[0])
        list_zones_diff.append(self.gpkg_path + '|layername=zoneP0B_concaveHull_smoothed')

        processing.run("qgis:mergevectorlayers", {
            'CRS': QgsCoordinateReferenceSystem('EPSG:4326'),
            'LAYERS': list_zones_diff,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zones_smoothed\" (geom)'})

        # grass
        # grass_generalize = processing.run('grass7:v.generalize',
        #                                   {'input': delete_holes['OUTPUT'],
        #                                    'method': 2,
        #                                    'threshold': 1,
        #                                    'output': 'TEMPORARY_OUTPUT',
        #                                    'error': 'TEMPORARY_OUTPUT'})
        #
        # grass_generalize_converted = processing.run('gdal:convertformat', {
        #     'INPUT': grass_generalize['output'],
        #     'OPTIONS': '',
        #     'OUTPUT': 'grass_generalize_converted.shp'})


        # grass_generalize_converted_toGpkg = QgsVectorLayer(grass_generalize_converted['OUTPUT'],
        #                                                    'grass_generalize_lang', "ogr")



        # self._saveIntoGpkg(grass_generalize_converted_toGpkg,'grass_generalize_lang')
        # grass_generalize_convertedd = QgsVectorLayer(grass_generalize_converted['OUTPUT'], 'grass_generalize_lang', "ogr")
        # grass_generalize_converted_toMap = QgsVectorLayer(self.gpkg_path + '|layername=grass_generalize_lang', 'grass_generalize_lang', "ogr")



        # generalize_layer = QgsProject.instance().addMapLayer(grass_generalize_converted_toGpkg, False)
        #
        # root = QgsProject.instance().layerTreeRoot()
        # group_gtfs = root.findGroup('zones')
        # group_gtfs.insertChildNode(0, QgsLayerTreeLayer(generalize_layer))
