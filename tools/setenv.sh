#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo $DIR

src_dir=`readlink -f "$DIR/../src"`
backup_dir=`readlink -f "$DIR/../backup"`


export PYTHONPATH="$src_dir;$backup_dir"

echo $PYTHONPATH

