#! /usr/bin/env bash
#
# Usage: ./edit-pg-dump.sh <file-name.sql>
#

if [ "$#" -ne 1 ]; then
    echo "Invalid usage: ./edit-pg-dump.sh <file-name.sql>"
fi

filename=$1

if [ ! -f $filename ] || [ "$filename" == "" ]; then
    echo "file $filename does not exist"
    exit 1
fi

echo "making a copy"
cp $filename $filename.backup

echo "processing file"

# delete all comments

sed -i '/^--/d' $filename

# delete front matter

read -r -d '' lines << EOF
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;
SET default_tablespace = '';
SET default_with_oids = false;
EOF

while read -r line; do
    sed -i '/^'"$line"'$/d' $filename
done <<< $lines

# delete notify triggers

sed -i -E '/^CREATE TRIGGER "?notify_hasura_\w+"? AFTER \w+ ON "?\w+"?\."?\w+"? FOR EACH ROW EXECUTE PROCEDURE "?hdb_views"?\."?notify_hasura_\w+"?\(\);$/d' $filename

# delete empty lines

sed -i '/^[[:space:]]*$/d' $filename

echo "done"
