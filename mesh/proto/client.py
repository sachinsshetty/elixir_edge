#!/usr/bin/env python3
"""
T-Echo client - sends device entity to WorldService at localhost:5051
"""

import grpc
import world_pb2
import world_pb2_grpc

def main():
    # Connect to server
    channel = grpc.insecure_channel("localhost:5051")
    stub = world_pb2_grpc.WorldServiceStub(channel)
    
    # ✅ CORRECT: Use top-level SerialDevice (NOT nested)
    entity = world_pb2.Entity(
        id="lilygo-techo-001",
        label="T-Echo Drone Node",
        geo=world_pb2.GeoSpatialComponent(
            longitude=8.6821,    # Frankfurt
            latitude=50.1109,
            altitude=100.0
        ),
        device=world_pb2.DeviceComponent(
            unique_hardware_id="nRF52840:ABC123",
            labels={
                "node": "techo-node",
                "role": "sensor",
                "location": "frankfurt"
            },
            serial=world_pb2.SerialDevice(
                path="/dev/ttyACM0",
                baud_rate=115200
            )
        ),
        priority=world_pb2.PriorityRoutine
    )
    
    # Send via Push RPC
    request = world_pb2.EntityChangeRequest(changes=[entity])
    response = stub.Push(request)
    
    print("✅ T-Echo entity sent!")
    print(f"Server response: {response.debug}")

if __name__ == '__main__':
    main()
