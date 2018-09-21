#!/usr/bin/python3

import sys
import psycopg2
import psycopg2.extras
import json
from pyproj import Proj

MINLON=14.22
MINLAT=49.94
MAXLON=14.71
MAXLAT=50.18

PID_STOP_FILE="DOP_PID_ZASTAVKY_B.json"

def mode_from_tags(stop):
	stop["metro"] = False
	stop["tram"] = False
	stop["bus"] = False
	stop["funicular"] = False
	stop["train"] = False
	stop["boat"] = False
	
	if stop["highway"] == "bus_stop":
		stop["bus"] = True
	if stop.get("railway") == "halt":
		stop["train"] = True
	if stop.get("railway") == "tram_stop":
		stop["tram"] = True
	if stop.get("railway") == "station":
		if stop.get("station") == "subway":
			stop["metro"] = True
		else:
			stop["train"] = True

UTMproj = Proj("+proj=utm +zone=33N +ellps=WGS84 +datum=WGS84 +units=m +no_defs")

conn= psycopg2.connect("dbname=cz_osm")
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
psycopg2.extras.register_hstore(cur)

cur.execute("""SELECT ST_X(wkb_geometry) AS lon,
	ST_Y(wkb_geometry) AS lat,
	ref,osm_id,name,highway,other_tags 
	FROM osm_stop_pos""")

stops = []
for stoprow in cur.fetchall():
	stop=dict(stoprow)
	(stop["x"],stop["y"])=UTMproj(stop["lon"],stop["lat"])
	stop.update(stop["other_tags"])
	del(stop["other_tags"])
	stop["paired"] = False
	mode_from_tags(stop)	
	stops.append(stop)

with open("osmstops.json","w") as outfile:
	json.dump(stops,outfile,ensure_ascii=False,indent=2)


### PID stops

with open(PID_STOP_FILE) as infile:
	pidstops=json.load(infile)["features"]

stops=[]
for pidstop in pidstops:
	stop = {}
	props = pidstop["properties"]
	(stop["lon"],stop["lat"])=pidstop["geometry"]["coordinates"]
	(stop["x"],stop["y"])=UTMproj(stop["lon"],stop["lat"])
	stop["name"]=props["ZAST_NAZEV"]
	stop["ref"]="U{}Z{}".format(props["ZAST_UZEL_CISLO"],props["ZAST_ZAST_CISLO"])
	stop["pid_id"]=props["ZAST_ID"]
	stop["paired"] = False
	stop["metro"] = bool(props["ZAST_DD"] & 1)
	stop["tram"] = bool(props["ZAST_DD"] & 2)
	stop["bus"] = bool(props["ZAST_DD"] & 4)
	stop["funicular"] = bool(props["ZAST_DD"] & 8)
	stop["train"] = bool(props["ZAST_DD"] & 16)
	stop["boat"] = bool(props["ZAST_DD"] & 32)

	stops.append(stop)

stops = list(filter(lambda x: x["lon"]>MINLON and x["lon"]<MAXLON and x["lat"]>MINLAT and x["lat"]<MAXLAT,stops))

with open("pidstops.json","w") as outfile:
	json.dump(stops,outfile,ensure_ascii=False,indent=2)
