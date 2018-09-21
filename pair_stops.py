#!/usr/bin/python3

import sys
import json
import math
from itertools import permutations
from statistics import mean

# najit s ref
# rozdelit na mista zastaveni a nastupiste
# rozdelit podle typu dopravy
# najit parovani u stejne pocetnych
# overit korektnost
# nahrat do OSM

def dist(stopa,stopb):
	return math.sqrt((stopa["x"]-stopb["x"])**2+(stopa["y"]-stopb["y"])**2)

def direction(stopa,stopb):
	d = dist(stopa,stopb)
	dirx = (stopa["x"]-stopb["x"])/d
	diry = (stopa["y"]-stopb["y"])/d
	return (dirx,diry)

def dir_error(dira,dirb):
#	""" 0 for same dir, 2 for opposite vectors """
#	return -(dira[0]*dirb[0]+dira[1]*dirb[1]-1);
	return 1-abs(dira[0]*dirb[0]+dira[1]*dirb[1])
	
def avgdir(dirs):
	return dirs[0]
	adirx = mean(list(map(lambda x:x[0],dirs)))
	adiry = mean(list(map(lambda x:x[1],dirs)))
	l = math.sqrt((adirx**2) + (adiry**2))
	return (adirx/l,adiry/l)

def pair_stop(osm,pid):
	dir_coeff = 1
	dist_coeff = 1
	dists = [[dist(a,b) for b in pid] for a in osm]
	dirs = [[direction(a,b) for b in pid] for a in osm]
	perms = permutations([x for x in range(len(osm))])
	minperm = None
	minweight = 10000
	for perm in perms:
		adir = avgdir([dirs[i][perm[i]] for i in range(len(osm))])
		dir_weight=sum([dir_error(dirs[i][perm[i]],adir) for i in range(len(osm))])
		dist_weight=sum([dists[i][perm[i]] for i in range(len(osm))])
		weight = dir_weight*dir_coeff + dist_weight*dist_coeff
		for i in range(len(osm)):
			print("d",dirs[i][perm[i]])
		print("a",adir)
		print(perm,weight)
		if weight < minweight:
			minperm = perm
			minweight = weight
	print(minperm,minweight)
	return (minperm,minweight)

def stop_pairing_geojson(osm,pid,perm,sumweight):
	stops = []
	for i in range(len(osm)):

		pair={
			"type":"Feature",
			"geometry":{
				"type":"LineString",
				"coordinates":[
					[osm[i]["lon"],osm[i]["lat"]],
					[pid[perm[i]]["lon"],pid[perm[i]]["lat"]]
				]
			},
			"properties":{
				"sum":sumweight,
				"name":osm[i]["name"]
			}
		}	
		stops.append(pair)
	return stops

def mark_ref_paired(osm,pid):
	""" Marks stops with common ref as paired="ref".
	Returns list of osm refs which are not in pid"""
	osmrefs = set(osm.keys())
	pidrefs = set(pid.keys())
	common = osmrefs.intersection(pidrefs)
	for ref in common:
		for stop in osm[ref]:
			stop["paired"] = "ref"
		for stop in pid[ref]:
			stop["paired"] = "ref"
	osm_orphans = osmrefs.difference(pidrefs)
	return osm_orphans

def filter_unpaired(stops):
	return list(filter(lambda x: x["paired"] == False,stops))
	
	
def dict_by_ref(stops):
	out = {}
	for stop in stops:
		if not stop["ref"]:
			continue
		if stop["ref"] in out:
			out[stop["ref"]].append(stop)
		else:
			out[stop["ref"]]=[stop]
	return out

def dict_by_name(stops):
	out = {}
	for stop in stops:
		if not stop["name"]:
			continue
		if stop["name"] in out:
			out[stop["name"]].append(stop)
		else:
			out[stop["name"]] = [stop]
	return out

transport_modes = ["metro","tram","bus","funicular","train","boat"]

pidstops=[]
with open("pidstops.json") as pidfile:
	pidstops=json.load(pidfile)

osmstops=[]
with open("osmstops.json") as osmfile:
	osmstops=json.load(osmfile)

osm_by_name = dict_by_name(osmstops)
pid_by_name = dict_by_name(pidstops)

osm_by_ref = dict_by_ref(osmstops)
pid_by_ref = dict_by_ref(pidstops)

osm_orphans = mark_ref_paired(osm_by_ref,pid_by_ref)
 
more_pid = 0
more_osm = 0
osm0 = 0
eq = 0
pairgeojson = []
for name in pid_by_name.keys():
	for mode in transport_modes:
		try:
			osm = list(filter(lambda x: x[mode],osm_by_name[name]))
		except KeyError:
			print("No stops in OSM with name {}".format(name))
			osm = []
		pid = list(filter(lambda x: x[mode],pid_by_name[name]))
		
		osm = filter_unpaired(osm)
		pid = filter_unpaired(pid)
		osmc = len(osm)
		pidc = len(pid)
		if osmc == 0:
			osm0+=1
		elif osmc > pidc:
			more_osm+=1
		elif osmc < pidc:
			more_pid+=1
			print("{}[{}] has more stops ({}) in PID than in OSM ({})".format(name,mode,len(pid),len(osm)))
		else:
			eq+=1	
			(perm,weight) = pair_stop(osm,pid)
			pairgeojson += stop_pairing_geojson(osm,pid,perm,weight)
		if  len(osm) > 0 and len(pid) > 0:
			print("{}[{}]: O:{} x P:{}".format(name,mode,len(osm),len(pid)))

with open("stops_pairing.geojson","w") as outfile:
	geojson = {
		"type":"FeatureCollection",
		"features":pairgeojson
	}
	json.dump(geojson,outfile)

print("More in osm: {}, more in PID: {}, equal: {}".format(more_osm,more_pid,eq))
