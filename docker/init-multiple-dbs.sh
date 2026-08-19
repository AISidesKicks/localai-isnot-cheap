#!/bin/bash
set -e
set -u

function database_exists() {
  local database=$1
  psql -tA --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "SELECT 1 FROM pg_database WHERE datname = '$database'" | grep -q 1
}

function create_database() {
  local database=$1
  echo "Creating database '$database'"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE $database;
EOSQL
}

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
  echo "Multiple database creation requested: $POSTGRES_MULTIPLE_DATABASES"
  for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr ',' ' '); do
    if database_exists "$db"; then
      echo "Database '$db' already exists, skipping"
    else
      create_database "$db"
    fi
  done
  echo "Multiple databases created"
fi
