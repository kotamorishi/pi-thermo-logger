#!/bin/bash -ex

BASEDIR=$(dirname "$0")
MAIN=thermal_checker.py

pkill -f ${MAIN} || true
nohup python3 ${BASEDIR}/${MAIN} >${BASEDIR}/log.txt 2>&1 &

echo "Logger started"
