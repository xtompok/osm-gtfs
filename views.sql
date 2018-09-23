DROP MATERIALIZED VIEW IF EXISTS  osm_stop_pos CASCADE;
CREATE MATERIALIZED VIEW osm_stop_pos AS
	SELECT *,ST_Transform(wkb_geometry,3857) AS geom FROM points 
	WHERE other_tags->'public_transport' = 'stop_position' 
	AND wkb_geometry && ST_MakeEnvelope(14.22,49.94,14.71,50.18,4326)
	;
CREATE INDEX osm_stop_pos_geom ON osm_stop_pos USING GIST(geom);

DROP MATERIALIZED VIEW IF EXISTS  osm_platforms CASCADE;
CREATE MATERIALIZED VIEW osm_platforms AS
	SELECT *,ST_Transform(wkb_geometry,3857) AS geom FROM lines 
	WHERE other_tags->'public_transport' = 'platform' 
	AND wkb_geometry && ST_MakeEnvelope(14.22,49.94,14.71,50.18,4326)
	;
CREATE INDEX osm_platforms_geom ON osm_platforms USING GIST(geom);

DROP MATERIALIZED VIEW IF EXISTS  platforms_without_stop_pos CASCADE;
CREATE MATERIALIZED VIEW platforms_without_stop_pos AS
	SELECT * FROM osm_platforms 
	
	EXCEPT 
	
	SELECT l.* 
	FROM osm_platforms AS l 
	INNER JOIN osm_stop_pos AS p ON ST_DWithin(l.geom,p.geom, 10)
	;

DROP MATERIALIZED VIEW IF EXISTS  highways CASCADE;
CREATE MATERIALIZED VIEW highways AS 
	SELECT
		osm_id,
		ST_Transform(wkb_geometry,3857) AS geom,
		other_tags->'oneway' AS oneway
	FROM lines
	WHERE
		"highway" IN ('primary','primary_link','residential','secondary','secondary_link','service','tertiary_link','tertiary','trunk','trunk_link') AND
		 wkb_geometry && ST_MakeEnvelope(14.22,49.94,14.71,50.18,4326)
	;
CREATE INDEX highways_geom ON highways USING GIST(geom);
CREATE INDEX highways_osm_id ON highways(osm_id);

DROP MATERIALIZED VIEW IF EXISTS stops_highways CASCADE;
CREATE MATERIALIZED VIEW stops_highways AS
	SELECT p.*,
		h.osm_id AS hid,
		ST_Distance(p.geom,h.geom) AS dist,
		ST_X(ST_ClosestPoint(h.geom,p.geom)) AS proj_x,
		ST_Y(ST_ClosestPoint(h.geom,p.geom)) AS proj_y
	FROM highways AS h
	INNER JOIN osm_stop_pos AS p
		ON st_dwithin(p.geom, h.geom, 20);
CREATE INDEX stops_highways_osm_id ON stops_highways(osm_id);

DROP MATERIALIZED VIEW IF EXISTS highways_nodes CASCADE;
CREATE MATERIALIZED VIEW highways_nodes AS
	SELECT  n.id AS nid, 
		ST_Transform(n.geom,3857) AS geom,
		wn.way_id AS hid,
		wn.sequence_id AS seq_id
	FROM nodes AS n 
        INNER JOIN way_nodes AS wn ON n.id = wn.node_id
        INNER JOIN highways AS h ON h.osm_id::int = wn.way_id;
CREATE INDEX highways_nodes_nid ON highways_nodes(nid);
CREATE INDEX highways_nodes_geom ON highways_nodes(geom);
CREATE INDEX highways_nodes_hid ON highways_nodes(hid);

DROP MATERIALIZED VIEW IF EXISTS stops_highways_nodes CASCADE;
CREATE MATERIALIZED VIEW stops_highways_nodes AS
	SELECT p.osm_id AS sid,
		h.hid AS hid,
		h.nid AS nid,
		ST_Distance(p.geom,h.geom) AS dist 
	FROM highways_nodes AS h
	INNER JOIN osm_stop_pos AS p
		ON st_dwithin(p.geom, h.geom, 20);
CREATE INDEX shn_nid ON stops_highways_nodes(nid);
CREATE INDEX shn_hid ON stops_highways_nodes(hid);
CREATE INDEX shn_sid ON stops_highways_nodes(sid);

DROP MATERIALIZED VIEW IF EXISTS highways_segments_distances CASCADE;
CREATE MATERIALIZED VIEW highways_segments_distances AS
	SELECT n.nid AS nid,s.objectid AS sid, ST_Distance(n.geom,s.geom) AS dist
	FROM highways_nodes AS n CROSS JOIN pid_segments AS s 
	WHERE s.buffer && n.geom;
CREATE INDEX hsd_nid ON highways_segments_distances(nid); 
CREATE INDEX hsd_sid ON highways_segments_distances(sid); 
