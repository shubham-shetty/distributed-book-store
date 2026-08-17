#!/bin/bash

echo "Clearing Order Database"
rm order/data/*

cd protos/
python3 -m grpc_tools.protoc -I=. --python_out=../catalog/ --grpc_python_out=../catalog/ ./catalog.proto
python3 -m grpc_tools.protoc -I=. --python_out=../order/ --grpc_python_out=../order/ ./catalog.proto
python3 -m grpc_tools.protoc -I=. --python_out=../order/ --grpc_python_out=../order/ ./order.proto
python3 -m grpc_tools.protoc -I=. --python_out=../front_end/ --grpc_python_out=../front_end/ ./catalog.proto
python3 -m grpc_tools.protoc -I=. --python_out=../front_end/ --grpc_python_out=../front_end/ ./order.proto

cd ..

# Check running services -> "ps -ef | grep python"
# Kill a service with -> "kill -9 <pid>"

echo "Starting Catalog Service"
python3 catalog/catalog.py &

echo "Starting Order Service"
python3 order/order.py -p 50043 &
sleep 5
python3 order/order.py -p 50044 &
sleep 5
python3 order/order.py -p 50045 &
sleep 1

echo "Starting Front-End Service"
python3 front_end/front_end.py --hn $1 &