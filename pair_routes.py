#!/usr/bin/python3

import psycopg2
import psycopg2.extras
import networkx as nx
import json
import traceback
import functools
import sys
from heapq import *
from geojson import LineString,FeatureCollection

SEGMENTS_FILE="DOP_PID_TRASY_L.json"

conn= psycopg2.connect("dbname=cz_osm")
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
psycopg2.extras.register_hstore(cur)

def create_graph():
	cur.execute("""SELECT DISTINCT nid, 
			ST_X(ST_Transform(geom,3857)) AS x,
			ST_Y(ST_Transform(geom,3857)) AS y
		FROM highways_nodes AS n
		""")
	nodes = [(r['nid'],{"x":r['x'],"y":r['y']}) for r in cur.fetchall()]
	G = nx.DiGraph()
	G.add_nodes_from(nodes)

	cur.execute("""SELECT n.*,wn.way_id,wn.sequence_id,h.oneway
		FROM nodes AS n
		INNER JOIN way_nodes AS wn ON n.id = wn.node_id
 		INNER JOIN highways AS h ON h.osm_id::int = wn.way_id 
 		ORDER BY way_id,sequence_id;""")
	way_mem = -1
	node_mem = -1
	for r in cur.fetchall():
		if way_mem == r['way_id']:
			G.add_edge(node_mem,r['id'])
			if (r['oneway'] != "yes"):
				G.add_edge(r['id'],node_mem)
		else:
			way_mem = r['way_id']
		node_mem = r['id']
	print("Nodes: {}, edges: {}".format(G.number_of_nodes(),G.number_of_edges()))	
	return G

G = create_graph()
new_id_cnt = 0

def get_nearest_or_divide(sid):
	global new_id_cnt
	cur.execute("""SELECT * FROM stops_highways
		WHERE osm_id = %s ORDER BY dist ASC""",(sid,))
	hways = cur.fetchall()

	if len(hways) == 0:
		print ("No highways in given distance")
		return None

	cur.execute("""SELECT * FROM stops_highways_nodes 
		WHERE sid = %s AND hid = %s ORDER BY dist ASC""",
		(sid,hways[0]['hid']))
	hway_nodes = cur.fetchall()
	if len(hway_nodes) > 0 and hway_nodes[0]['dist'] < hways[0]['dist']+5:
		return hway_nodes[0]['nid']

	point = (hways[0]['proj_x'],hways[0]['proj_y'])
	point_id = -new_id_cnt
	new_id_cnt += 1

	G.add_node(point_id,{'x': point[0], 'y':point[1], 'added':True})

	cur.execute("""SELECT nid,ST_X(geom) AS x,ST_Y(geom) AS y
		FROM highways_nodes WHERE hid = %s ORDER BY seq_id """,(hways[0]['hid'],))
	nodes = cur.fetchall()
	mempt = nodes[0]
	pt = None
	for pt in nodes[1:]:
		dseg = (pt['x']-mempt['x'], pt['y']-mempt['y'])
		dpt = (point[0]-mempt['x'], point[1]-mempt['y'])
		cross = (dseg[0]*dpt[1]-dseg[1]*dpt[0])
		if abs(cross) > 0.00001:
			mempt = pt
			continue
		dotpt = dseg[0]*dpt[0] + dseg[1]*dpt[1]
		dotseg = dseg[0]*dseg[0] + dseg[1]*dseg[1]
		if 0 > dotpt or dotpt > dotseg:
			mempt = pt
			continue
		break
	
	if mempt == pt:
		print("Line segment not found!")
		sys.exit(1)
	#G.remove_edge(mempt['nid'],pt['nid'])
	G.add_edge(mempt['nid'],point_id)
	G.add_edge(point_id,pt['nid'])
	if (pt['nid'],mempt['nid']) in G.edges():
		#G.remove_edge(mempt['nid'],pt['nid'])
		G.add_edge(point_id,mempt['nid'])
		G.add_edge(pt['nid'],point_id)

	return point_id 

			


def pair_segment(s):
	props = s['properties']
	try:
		start_stop = pidstops_by_id[props['ZAST_ID_ODKUD']]
		end_stop = pidstops_by_id[props['ZAST_ID_KAM']]
	except KeyError:
		traceback.print_exc()
		return None
	if 'osm_id' not in start_stop:
		print("Stop {} has no osm_id".format(start_stop['name']))
		return None
	if 'osm_id' not in end_stop:
		print("Stop {} has no osm_id".format(end_stop['name']))
		return None 
	
	print("From: {}; to {}".format(start_stop['name'],end_stop['name']))
	start = get_nearest_or_divide(start_stop['osm_id'])
	end = get_nearest_or_divide(end_stop['osm_id'])

	print("From: {}, node: {}; to {}, node {}".format(start_stop['name'],start,end_stop['name'],end))
	if start == None or end == None:
		return None
	return find_path(start,end,props['OBJECTID'])

@functools.total_ordering
class Node(object):
	def __init__(self,aid,afrom,weight):
		self.aid = aid
		self.afrom = afrom
		self.weight = weight
	
	def __eq__(self,other):
		if not isinstance(other,Node):
			return NotImplemented
		if self.aid == other.aid and \
			self.afrom == other.afrom and \
			self.weight == other.weight:
			return True
		return False
	def __lt__(self,other):
		if not isinstance(other,Node):
			return NotImplemented
		if self.weight < other.weight:
			return True
		if self.aid < other.aid:
			return True
		if self.afrom < other.afrom:
			return True
		return False

MAX_WEIGHT = 1000
def find_path(start,end,segment):
	stat = {}
	heap = []
	stat[start] = Node(start,None,0)
	heappush(heap,stat[start])
	print("S: {}".format(start))
	while True:
		if len(heap) == 0:
			break
		n = heappop(heap)
		if n.aid == end:
			break
		for neigh in G.neighbors(n.aid):
			weight = n.weight + dist_from_segment(neigh,segment)
			print("N: {}, w: {}".format(neigh,weight))
			if weight > MAX_WEIGHT:
				continue
			if neigh in stat and stat[neigh].weight < weight:
				continue
			stat[neigh] = Node(neigh,n.aid,weight)
			heappush(heap,stat[neigh])
	if end in stat:
		print ("Found segment with weight {}".format(stat[end].weight))
		return linestring_from_stat(stat,start,end)
	else:
		print ("Not found segment")
		return None

def linestring_from_stat(stat,start,end):
	nodes = []
	n = stat[end]
	while n.aid != start:
		nodes.append(n)
		n = stat[n.afrom]
	nodes.append(stat[start])
	nodes.reverse()
	linestring = []
	for n in nodes:
		linestring.append((G.node[n.aid]['x'],G.node[n.aid]['y']))
	return LineString(coordinates=linestring)
	

def dist_from_segment(nid,sid):
	cur.execute("""SELECT dist 
		FROM highways_segments_distances
		WHERE sid = %s AND nid = %s""",(sid,nid))
	if cur.rowcount == 0:
		if nid <= 0:
			return 0
		else:
			return MAX_WEIGHT
	return cur.fetchone()['dist']

def load_segments(filename):
	with open(filename) as segfile:
		return json.load(segfile)["features"]
def load_stops(filename):
	with open(filename) as stopfile:
		return json.load(stopfile)

pidstops = load_stops("pidstops-out.json")
osmstops = load_stops("osmstops-out.json")
pidstops_by_id = {s['pid_id']:s for s in pidstops}


segs = load_segments(SEGMENTS_FILE)

paired = FeatureCollection()
for s in segs:
	if not s['properties']['L_BUS']:
		continue
	p = pair_segment(s)
	if p:
		paired.append(p)

with open("segments-paired.json","w") as out:
	paired.dump(out)
