Meshtactic

Project Q : Data Transfer

https://meshtastic.org/docs/hardware/devices/lilygo/techo/

https://github.com/Xinyuan-LilyGO/T-Echo


https://projectqai.github.io/




pip install meshtastic

sudo chmod a+rw /dev/ttyACM0

meshtastic --port /dev/ttyACM0 --info

meshtastic --port /dev/ttyACM0 --send "hello from Sachin"

--
npm install -D tsx
npx tsx test.ts




--

# In some project directory
mkdir -p proto && cd proto
wget https://raw.githubusercontent.com/projectqai/proto/main/world.proto


---

docker run -p 50051:50051 -ti ghcr.io/projectqai/hydris:v0.0.18

---



pip install grpcio grpcio-tools

--

python -m grpc_tools.protoc \
  -I. \
  --python_out=. \
  --grpc_python_out=. \
  world.proto

---
npm install @projectqai/proto @bufbuild/protobuf @connectrpc/connect @connectrpc/connect-web

npx tsc client.ts
---

python server.py

python client.py

snap install --edge grpcurl


pip install grpcio grpcio-tools grpcio-reflection


--

grpcurl -plaintext localhost:5051 list


--

grpcurl -plaintext localhost:5051 world.WorldService/GetLocalNode

--

grpcurl -plaintext -d '{"id": "lilygo-techo-001"}' localhost:5051 world.WorldService/GetEntity

grpcurl -plaintext -d '{"id": "lilygo-techo-001"}' localhost:5051 world.WorldService/GetEntity
{
  "entity": {
    "id": "lilygo-techo-001",
    "label": "T-Echo Drone Node",
    "priority": "PriorityRoutine",
    "geo": {
      "longitude": 8.6821,
      "latitude": 50.1109,
      "altitude": 100
    },
    "device": {
      "unique_hardware_id": "nRF52840:ABC123",
      "labels": {
        "node": "techo-node",
        "role": "sensor"
      },
      "serial": {
        "path": "/dev/ttyACM0",
        "baud_rate": 115200
      }
    }
  }
}


---


# Terminal 1
pip install grpcio-reflection  # if not installed
python server.py

# Terminal 2  
python client.py

# Terminal 3
grpcurl -plaintext localhost:5051 world.WorldService/GetLocalNode
grpcurl -plaintext -d '{"id": "lilygo-techo-001"}' localhost:5051 world.WorldService/GetEntity
grpcurl -plaintext -d '{"filter": {}}' localhost:5051 world.WorldService/ListEntities

