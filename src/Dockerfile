FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Regenerate gRPC stubs at image-build time (same protoc calls as build.sh),
# so they always match the grpcio/grpcio-tools versions in this image.
RUN cd protos && \
    python -m grpc_tools.protoc -I=. --python_out=../catalog/ --grpc_python_out=../catalog/ ./catalog.proto && \
    python -m grpc_tools.protoc -I=. --python_out=../order/ --grpc_python_out=../order/ ./catalog.proto && \
    python -m grpc_tools.protoc -I=. --python_out=../order/ --grpc_python_out=../order/ ./order.proto && \
    python -m grpc_tools.protoc -I=. --python_out=../front_end/ --grpc_python_out=../front_end/ ./catalog.proto && \
    python -m grpc_tools.protoc -I=. --python_out=../front_end/ --grpc_python_out=../front_end/ ./order.proto

# Actual command is supplied per-service by docker-compose.yml
