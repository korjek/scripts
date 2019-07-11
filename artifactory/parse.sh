#!/bin/bash
awk '{ if (/XXXYYYZZZ/) {path=$3}; if (/"properties"/) {open=1}; if (open == 1){ if (/docker.manifest.type/) {found=1};if (/]/) {if (found == 1) { print path; }; open=0;found=0}} }' $1
awk '{ if (/XXXYYYZZZ/) {open=1; line=$2}; if (open == 1){ if (/Package/) {found=1};if (/^$/) {if (found == 0) { print line; }; open=0;found=0}} }' $1
