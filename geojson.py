
import json

class GeoJsonObject:
	def __init__(self,atype):
		self.type = atype
	
	def to_json(self):
		return {"type" : self.type}

	def from_json(self,ajson):
		self.type = ajson["type"]

	def dump(self,fd):
		ajson = self.to_json()
		json.dump(ajson,fd)
	
	def load(self,fd):
		ajson = json.load(fd)
		self.from_json(ajson)

class GeoJsonGeometry(GeoJsonObject):
	def __init__(self,atype,coordinates,properties):
		super().__init__(atype)
		self.coords = coordinates

	def to_json(self):
		ajson = super().to_json()
		ajson["coordinates"] = self.coords
		return ajson

	def from_json(self,ajson):
		super().from_json(ajson)
		self.coords = ajson['coordinates']

class GeoJsonFeature(GeoJsonObject):
	def __init__(self,properties):
		super().__init__("Feature")
		self.props = properties
	
	def from_json(self,ajson):
		super().from_json(ajson)
		self.props = ajson["properties"]
		self.geom.from_json(ajson['geometry'])
	
	def to_json(self):
		ajson = super().to_json()
		ajson["properties"] = self.props
		ajson["geometry"] = self.geom.to_json()
		return ajson
	

class LineStringGeometry(GeoJsonGeometry):
	def __init__(self,coordinates=[],properties={}):
		super().__init__("LineString", coordinates, properties)

	def apppend(self,coords):
		self.coordinates.append(coords)

class PointGeometry(GeoJsonGeometry):
	def __init__(self,coordinates=[],properties={}):
		super().__init__("Point", coordinates, properties)

class LineString(GeoJsonFeature):
	def __init__(self,coordinates=[], properties={}):
		super().__init__(properties)
		self.geom = LineStringGeometry(coordinates)


class Point(GeoJsonFeature):
	def __init__(self,coordinates=[], properties={}):
		super().__init__(properties)
		self.geom = PointGeometry(coordinates)

	
class FeatureCollection(GeoJsonObject):
	def __init__(self, features=[], properties={}):
		super().__init__("FeatureCollection")
		self.features = features
		self.props = properties
	
	def __getitem__(self,item):
		return self.features[item]
	
	def append(self,item):
		self.features.append(item)

	def to_json(self):
		ajson = super().to_json()
		ajson["properties"] = self.props
		ajson["features"] = [f.to_json() for f in self.features]
		return ajson
	
	def from_json(self,ajson):
		super().from_json(ajson)
		self.props = ajson['properties']
		self.features = []
		for jf in ajson['features']:
			if jf['type'] == "LineString":
				f = LineString()
			#FIXME other types
			f.from_json(jf)
			self.features.append(f)
				


