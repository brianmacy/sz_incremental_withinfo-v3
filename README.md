# sz_incremental_withinfo
Example script to add incremental batches of records to Senzing and receive the list of changed entities.

Ported to the Senzing v4 SDK.

# API demonstrated
## Core
* add_record (with the SZ_WITH_INFO flag): Does an add/replace on the record and returns the affected entities
* get_redo_record / process_redo_record (with the SZ_WITH_INFO flag): Process the internal redo records for things like historical generic correction and returns the affected entities
* get_entity_by_entity_id: Used to retrieve the changed entities
## Supporting
* senzing_core.SzAbstractFactoryCore: To initialize the Senzing environment and create the engine
* get_stats: To retrieve internal engine diagnostic information as to what is going on in the engine

For more details on the Senzing SDK go to https://docs.senzing.com


# Overview

This script uses Python futures to parallelize processing.  The Senzing engine is thread-safe.

In the first two phases it processes the input file in Senzing JSON format (https://senzing.zendesk.com/hc/en-us/articles/231925448-Generic-Entity-Specification-JSON-CSV-Mapping), writes a temporary file of the affected entities, and then reads that temporary file to get the final state of those entities with each entity represented once.

# Configuration

Senzing is configured entirely through the `SENZING_ENGINE_CONFIGURATION_JSON` environment
variable (the modern v4 replacement for the legacy `G2Module.ini`).  Nothing is hardcoded in
the script.  The value is a JSON document with `PIPELINE` (install/support paths) and `SQL`
(datastore connection) sections, for example:

```json
{
  "PIPELINE": {
    "CONFIGPATH": "/opt/senzing/er/resources/templates",
    "RESOURCEPATH": "/opt/senzing/er/resources",
    "SUPPORTPATH": "/opt/senzing/data"
  },
  "SQL": {
    "CONNECTION": "postgresql://senzing:password@postgres:5432:senzing"
  }
}
```

Set it in your shell (single line) before running, e.g.:

```
export SENZING_ENGINE_CONFIGURATION_JSON='{"PIPELINE":{"CONFIGPATH":"/opt/senzing/er/resources/templates","RESOURCEPATH":"/opt/senzing/er/resources","SUPPORTPATH":"/opt/senzing/data"},"SQL":{"CONNECTION":"postgresql://senzing:password@postgres:5432:senzing"}}'
```

# Building/Running

```
docker build -t brian/sz_incremental_withinfo .
docker run --user $UID -it -v $PWD:/data -e SENZING_ENGINE_CONFIGURATION_JSON \
  brian/sz_incremental_withinfo -o /data/delta.json -i /data/tmpinfo.json /data/shuffled_data_to_load.json
```

The Docker image is built on `senzing/senzingsdk-runtime` and ships both the PostgreSQL and
MSSQL backends by default.  For a leaner image build with a single backend, e.g.
`--build-arg WITH_MSSQL=0` (PostgreSQL only) or `--build-arg WITH_POSTGRES=0` (MSSQL only).

# Usage
usage: sz_incremental_withinfo.py [-h] [-o OUTFILE] [-i INFOFILE] [-t] fileToProcess

- o: output file of changed entities in JSON-lines
- i: a temporary file for the JSON-lines withInfo messages in case the process fails part way through
- t: detailed trace information from the engine
- fileToProcess: the actual Senzing JSON-lines file with records to add

# Pre-requisites

You will need a Senzing v4 repository/datastore and the `SENZING_ENGINE_CONFIGURATION_JSON`
environment variable set as described in the Configuration section above (see
https://docs.senzing.com).  When running via Docker the Senzing binaries are supplied by the
`senzing/senzingsdk-runtime` base image; you only need to provide the datastore connection
through `SENZING_ENGINE_CONFIGURATION_JSON`.
