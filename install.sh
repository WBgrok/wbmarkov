#!/bin/bash

usage() {
	echo "Usage: $0 [-h hostname] [-p port] [-u username] [-d db_name]"
	echo "Will create a database and deploy the schema ont the specify PostgreSQL server"
	echo ""
	echo "CAUTION: This will delete any existing DB by this name"
	echo ""
	echo "	-h hostname: db server host or socket directory (default \"localhost\")"
	echo "	-p port      db server port (default \"5432\")"
	echo "	-u username  db user name (default \"$USER\")"
	echo "	-d db_name   name of the DB to create (defalt \"markov\")"
	exit 1
}

# we expect an even number of args, with a maximum of eight
nargs=$#
if [ $((nargs%2)) -ne 0 ] || [ "$nargs" -gt 8 ]
then
	usage
fi

# defaults
hostname="localhost"
port="5432"
username="$USER"
db_name="markov"

set_h=false
set_p=false
set_u=false
set_d=false

nv="n"
for arg in "$@"
do
	echo "arg $nv $arg "
	if [ "$nv" == "n" ]
	then
		if [ "$arg" == "-h" ]
		then 
			nv="h"
		elif [ "$arg" == "-p" ]
		then
			nv="p"
		elif [ "$arg" == "-u" ]
		then
			nv="u"
		elif [ "$arg" == "-d" ]
		then
			nv="d"
		fi
	elif [ "$nv" == "h" ]
	then
		if $set_h
		then
			usage
		else
			hostname="$arg"
			set_h=true
			nv="n"
		fi
	elif [ "$nv" == "p" ]
	then
		if $set_p
		then
			usage
		else
			port="$arg"
			set_p=true
			nv="n"
		fi
	elif [ "$nv" == "u" ]
	then
		if $set_u
		then
			usage
		else
			username="$arg"
			set_u=true
			nv="n"
		fi
	elif [ "$nv" == "d" ]
	then
		if $set_d
		then
			usage
		else
			db_name="$arg"
			set_d=true
			nv="n"
		fi
	else
		usage
	fi
done


echo "creating $db_name using $usernam on $hostname:$port"

echo "drop database $db_name;" > /tmp/wbmarkov.sql
echo "create database $db_name;" >> /tmp/wbmarkov.sql

psql -h $hostname -p $port -U $username -f /tmp/wbmarkov.sql
if [ $? -ne 0 ]
then
	rm /tmp/wbmarkov.sql
	echo "could not create database"
	exit 1
fi
psql -h $hostname -p $port -U $username -f schema.sql $db_name
if [ $? -ne 0 ]
then
	rm /tmp/wbmarkov.sql
	echo "could not load schema database"
	exit 1
fi

rm /tmp/wbmarkov.sql

echo "Database created - use 'psql -h $hostname -p $port -U $username $db_name' to connect"

