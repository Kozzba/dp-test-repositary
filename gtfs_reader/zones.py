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
        expression = "\"zone_id\" in ('P','0','B')"
        _layer_stops.selectByExpression(expression)

        self._saveIntoGpkg(_layer_stops,'layer_stops_selected')

        layer_stops_selected = self._createVectorLayer('layer_stops_selected')

        processing.run("native:deleteduplicategeometries", {
            'INPUT': layer_stops_selected,
            'OUTPUT': 'ogr:dbname=\'' + self.gpkg_path + '\' table=\"zoneP0B\" (geom)'})

        layer_zoneP0B = self._createVectorLayer('zoneP0B')

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

        zones = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

        for i in zones:
            # select stops by zone_id
            _layer_stops = QgsVectorLayer(layer_stops, "stops", "ogr")
            processing.run("qgis:selectbyattribute", {'FIELD': 'zone_id',
                                                      'INPUT': _layer_stops,
                                                      'METHOD': 0,
                                                      'OPERATOR': 0,
                                                      'VALUE': '' + i + ''})

            self._saveIntoGpkg(_layer_stops, 'zone' + i)

            layer_zoneI = self._createVectorLayer('zone' + i)

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

        self._deleteLayer('voronoi')
        self._deleteLayer('layer_stops_selected')
        for i in zones:
                self._deleteLayer('zone' + i)
                self._deleteLayer('zone' + i + '_voronoi')
        self._deleteLayer('zoneP0B')
        self._deleteLayer('zoneP0B_voronoi')

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
        list_zones.append(self.gpkg_path + '|layername=zoneP0B_voronoi_dissolve')

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

        self._deleteLayer('zoneP0B_voronoi_dissolve')
        for i in zones:
            self._deleteLayer('zone' + i + '_voronoi_dissolve')

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

        # qgis

        # smooth = processing.run('qgis:smoothgeometry',
        #         { 'INPUT': deleteHoles['OUTPUT'],
        #           'ITERATIONS': 10,
        #           'OFFSET': 0.25,
        #           'MAX_ANGLE': 180,
        #           'OUTPUT': 'ogr:dbname=\''+ self.gpkg_path +'\' table=\"smooth\" (geom)'})

        # # extract vertices (polygon to nodes)
        # processing.run('qgis: extractvertices',
        #                { 'INPUT': self.gpkg_path + '|layername=zones',
        #                  'OUTPUT' : 'TEMPORARY_OUTPUT' })

        # grass
        grass_generalize = processing.run('grass7:v.generalize',
                                          {'input': delete_holes['OUTPUT'],
                                           'method': 2,
                                           'threshold': 1,
                                           'output': 'TEMPORARY_OUTPUT',
                                           'error': 'TEMPORARY_OUTPUT'})

        grass_generalize_converted = processing.run('gdal:convertformat', {
            'INPUT': grass_generalize['output'],
            'OPTIONS': '',
            'OUTPUT': 'grass_generalize_converted.shp'})

        grass_generalize_converted_toGpkg = QgsVectorLayer(grass_generalize_converted['OUTPUT'],
                                                           'grass_generalize_lang', "ogr")
        # self._saveIntoGpkg(grass_generalize_converted_toGpkg,'grass_generalize_lang')
        # grass_generalize_convertedd = QgsVectorLayer(grass_generalize_converted['OUTPUT'], 'grass_generalize_lang', "ogr")
        # grass_generalize_converted_toMap = QgsVectorLayer(self.gpkg_path + '|layername=grass_generalize_lang', 'grass_generalize_lang', "ogr")

        generalize_layer = QgsProject.instance().addMapLayer(grass_generalize_converted_toGpkg, False)

        root = QgsProject.instance().layerTreeRoot()
        group_gtfs = root.findGroup('zones')
        group_gtfs.insertChildNode(0, QgsLayerTreeLayer(generalize_layer))
