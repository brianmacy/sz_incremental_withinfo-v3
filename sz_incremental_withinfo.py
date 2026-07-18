#! /usr/bin/env python3

import concurrent.futures

import argparse
import orjson
import itertools

import sys
import os
import time

from senzing import SzEngineFlags, SzError

import senzing_core

INTERVAL = 10000


def process_entity(engine, entity_id):
    try:
        return engine.get_entity_by_entity_id(
            entity_id, SzEngineFlags.SZ_ENTITY_INCLUDE_RECORD_DATA
        )
    except SzError as err:
        # assuming it is failing because it doesn't exist (SZ_NOT_FOUND)
        print(err, file=sys.stderr)
        return None
    except Exception as err:
        print(err, file=sys.stderr)
        raise


def process_redo(engine):
    try:
        redo_record = engine.get_redo_record()
        if not redo_record:
            return None
        return engine.process_redo_record(redo_record, SzEngineFlags.SZ_WITH_INFO)
    except Exception as err:
        print(err, file=sys.stderr)
        raise


def process_line(engine, line):
    try:
        record = orjson.loads(line.encode())
        return engine.add_record(
            record["DATA_SOURCE"],
            record["RECORD_ID"],
            line,
            SzEngineFlags.SZ_WITH_INFO,
        )
    except Exception as err:
        print(f"{err} [{line}]", file=sys.stderr)
        raise


try:
    parser = argparse.ArgumentParser()
    parser.add_argument("fileToProcess", default=None)
    parser.add_argument(
        "-o",
        "--outFile",
        dest="outFile",
        default="load_delta.json",
        help="name of output file to use",
    )
    parser.add_argument(
        "-i",
        "--infoFile",
        dest="infoFile",
        default="/tmp/withInfo.json",
        help="name of temporary withinfo file to use",
    )
    parser.add_argument(
        "-t",
        "--debugTrace",
        dest="debugTrace",
        action="store_true",
        default=False,
        help="output debug trace information",
    )
    args = parser.parse_args()

    engine_config = os.getenv("SENZING_ENGINE_CONFIGURATION_JSON")
    if not engine_config:
        print(
            "The environment variable SENZING_ENGINE_CONFIGURATION_JSON must be set with a proper JSON configuration.",
            file=sys.stderr,
        )
        print(
            "Please see https://docs.senzing.com for configuration details.",
            file=sys.stderr,
        )
        exit(-1)

    # Initialize the Senzing engine via the v4 abstract factory
    factory = senzing_core.SzAbstractFactoryCore(
        "sz_incremental_withinfo", engine_config, verbose_logging=args.debugTrace
    )
    g2 = factory.create_engine()
    prevTime = time.time()

    with open(args.fileToProcess, "r") as fp:
        numLines = 0
        q_multiple = 2
        max_workers = None

        if os.path.isfile(args.infoFile):
            print(
                f"Temporary WithInfo file {args.infoFile} already exists.  This may be from a failed run.",
                file=sys.stderr,
            )
            print(
                "Make sure these entities are processed and remove the file before re-running",
                file=sys.stderr,
            )
            exit(-1)

        fpWithInfo = open(args.infoFile, "w+")
        fpOut = open(args.outFile, "w+")

        with concurrent.futures.ThreadPoolExecutor(max_workers) as executor:
            try:
                ## process the input file with each withinfo getting output
                futures = {
                    executor.submit(process_line, g2, line): line
                    for line in itertools.islice(fp, q_multiple * executor._max_workers)
                }

                while futures:

                    done, _ = concurrent.futures.wait(
                        futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    # Wish I could use as_completed but, understandbly, it doesn't like the modification of futures
                    # as it is being iterated on.  It kind of works for a while and then falls over.
                    for fut in done:  # concurrent.futures.as_completed(futures):
                        result = fut.result()
                        futures.pop(fut)

                        if result:
                            print(result, file=fpWithInfo)

                        numLines += 1
                        if numLines % INTERVAL == 0:
                            nowTime = time.time()
                            speed = int(INTERVAL / (nowTime - prevTime))
                            print(
                                f"Processed {numLines} adds, {speed} records per second"
                            )
                            prevTime = nowTime
                        if numLines % 100000 == 0:
                            print(f"\n{g2.get_stats()}\n")

                        line = fp.readline()
                        if line:
                            futures[executor.submit(process_line, g2, line)] = line

                print(f"Processed total of {numLines} adds")

                ##
                ## process redo
                ##

                ## note that this is a set not and not a dict like before
                futures = set()
                numLines = 0
                for i in range(executor._max_workers):
                    futures.add(executor.submit(process_redo, g2))

                while futures:

                    done, _ = concurrent.futures.wait(
                        futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for fut in done:
                        result = fut.result()
                        futures.remove(fut)

                        if result:
                            print(result, file=fpWithInfo)
                            futures.add(executor.submit(process_redo, g2))
                            numLines += 1

                            if numLines % INTERVAL == 0:
                                nowTime = time.time()
                                speed = int(INTERVAL / (nowTime - prevTime))
                                print(
                                    f"Processed {numLines} redo, {speed} records per second"
                                )
                                prevTime = nowTime
                            if numLines % 100000 == 0:
                                print(f"\n{g2.get_stats()}\n")

                print(f"Processed total of {numLines} redo")

                ##
                ## Process withinfo
                ##

                fpWithInfo.seek(0)
                numLines = 0
                futures = {}

                # probably more efficient ways to do this but it is best to dedupe the entityIDs
                unique_entities = set()
                for line in fpWithInfo:
                    record = orjson.loads(line.encode())
                    for entity in record["AFFECTED_ENTITIES"]:
                        unique_entities.add(entity["ENTITY_ID"])

                print(f"Extracted {numLines} unique entities from WithInfo")

                for i in range(executor._max_workers):
                    if unique_entities:
                        entity_id = unique_entities.pop()
                        futures[
                            executor.submit(process_entity, g2, entity_id)
                        ] = entity_id

                while futures:

                    done, _ = concurrent.futures.wait(
                        futures, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for fut in done:
                        result = fut.result()
                        processed_entity_id = futures.pop(fut)

                        if result:
                            print(result, file=fpOut)
                        else:
                            print(
                                '{ENTITY":{"ENTITY_ID"'
                                + str(processed_entity_id)
                                + ',"RECORDS":[]}}',
                                file=fpOut,
                            )

                        numLines += 1
                        if numLines % INTERVAL == 0:
                            nowTime = time.time()
                            speed = int(INTERVAL / (nowTime - prevTime))
                            print(
                                f"Processed {numLines} withinfo, {speed} records per second"
                            )
                            prevTime = nowTime
                        if numLines % 100000 == 0:
                            print(f"\n{g2.get_stats()}\n")

                        if unique_entities:
                            entity_id = unique_entities.pop()
                            futures[
                                executor.submit(process_entity, g2, entity_id)
                            ] = entity_id

                print(f"Processed total of {numLines} withinfo")
                fpWithInfo.close()
                os.remove(args.infoFile)

            except Exception as err:
                print(f"Shutting down due to error: {err}", file=sys.stderr)
                executor.shutdown()
                exit(-1)

except Exception as err:
    print(err, file=sys.stderr)
    exit(-1)
