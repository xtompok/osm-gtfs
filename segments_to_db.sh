#!/bin/sh

DB="cz_osm"
TABLE="pid_segments"

psql $DB -c "DROP TABLE IF EXISTS $TABLE CASCADE;";
ogr2ogr -f "PostgreSQL" PG:"dbname=$DB user=jethro" "DOP_PID_TRASY_L.json" -nln $TABLE -overwrite

psql $DB -c "ALTER TABLE $TABLE ADD geom geometry;";
psql $DB -c "UPDATE $TABLE SET geom=ST_Transform(wkb_geometry,3857);"
psql $DB -c "CREATE INDEX ${TABLE}_geom ON $TABLE USING GIST(geom);"

psql $DB -c "ALTER TABLE $TABLE ADD buffer geometry;"
psql $DB -c "UPDATE $TABLE SET buffer=ST_Buffer(geom,100);"
psql $DB -c "CREATE INDEX ${TABLE}_buffer ON $TABLE USING GIST(buffer);"
