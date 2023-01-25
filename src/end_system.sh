#!/bin/bash

while :
do
	randNumber=$((RANDOM % 9))
	echo "VL numero : ${randNumber}"
	./sendv2.py $randNumber
	sleep 1
done
