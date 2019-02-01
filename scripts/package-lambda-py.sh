#!/bin/sh
pip install requests -t ../lambda
pip install six -t ../lambda
pip install boto3 -t ../lambda
pip install pypd -t ../lambda

chmod -R 755 ../lambda

zip -r ../deployment.zip ../lambda
