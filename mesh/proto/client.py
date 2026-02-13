import grpc
import world_pb2
import world_pb2_grpc

def main():
    # 1. Connect to localhost:5051
    channel = grpc.insecure_channel("localhost:5051")
    stub = world_pb2_grpc.WorldServiceStub(channel)
    
    # 2. Prepopulate Entity (Frankfurt drone example)
    entity = world_pb2.Entity(
        id="lilygo-techo-001",
        label="T-Echo Drone Node",
        geo=world_pb2.GeoSpatialComponent(
            longitude=8.6821,
            latitude=50.1109,
            altitude=100.0
        ),
        device=world_pb2.DeviceComponent(
            unique_hardware_id="nRF52840:ABC123",
            labels={
                "node": "techo-node",
                "role": "sensor"
            },
            serial=world_pb2.SerialDevice(
                path="/dev/ttyACM0",
                baud_rate=115200
            )
        ),
        priority=world_pb2.PriorityRoutine
    )
    
    # 3. Send via Push RPC (EntityChangeRequest contains changes)
    request = world_pb2.EntityChangeRequest(changes=[entity])
    response = stub.Push(request)
    
    print("Server response:", response)

if __name__ == "__main__":
    main()
