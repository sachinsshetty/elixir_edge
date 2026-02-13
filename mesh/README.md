Meshtactic

Project Q : Data Transfer

https://meshtastic.org/docs/hardware/devices/lilygo/techo/

https://github.com/Xinyuan-LilyGO/T-Echo




pip install meshtastic

sudo chmod a+rw /dev/ttyACM0

meshtastic --port /dev/ttyACM0 --info

meshtastic --port /dev/ttyACM0 --send "hello from Sachin"

--


# In some project directory
mkdir -p proto && cd proto
wget https://raw.githubusercontent.com/projectqai/proto/main/world.proto


---

pip install grpcio grpcio-tools

--

python -m grpc_tools.protoc \
  -I. \
  --python_out=. \
  --grpc_python_out=. \
  world.proto

---

python server.py

python client.py

snap install --edge grpcurl

[]