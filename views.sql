CREATE MATERIALIZED VIEW osm_stop_pos AS
	SELECT * FROM points 
	WHERE other_tags->'public_transport' = 'stop_position' 
	AND wkb_geometry && ST_MakeEnvelope(14.22,49.94,14.71,50.18,4326)
	;

CREATE MATERIALIZED VIEW osm_platforms AS
	SELECT * FROM lines 
	WHERE other_tags->'public_transport' = 'platform' 
	AND wkb_geometry && ST_MakeEnvelope(14.22,49.94,14.71,50.18,4326)
	;

CREATE MATERIALIZED VIEW platforms_without_stop_pos AS
	SELECT * FROM osm_platforms 
	
	EXCEPT 
	
	SELECT l.* 
	FROM osm_platforms AS l 
	INNER JOIN osm_stop_pos AS p ON ST_DWithin(ST_Transform(l.wkb_geometry,5514),ST_Transform(p.wkb_geometry, 5514), 10)
	;
