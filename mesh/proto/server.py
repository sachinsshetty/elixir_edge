#!/usr/bin/env python3
"""
WorldService gRPC Server for projectqai/proto world.proto
Runs on localhost:5051 with reflection support
"""

import grpc
import world_pb2
import world_pb2_grpc
from concurrent import futures
import time

# Reflection support
from grpc_reflection.v1alpha import reflection

# In-memory entity store
entities = {}

class WorldServiceServicer(world_pb2_grpc.WorldServiceServicer):
    
    def ListEntities(self, request, context):
        """List entities matching filter (or all if empty)"""
        filtered = []
        for entity in entities.values():
            if _matches_filter(entity, request.filter):
                filtered.append(entity)
        print(f"📋 ListEntities: returning {len(filtered)} entities")
        return world_pb2.ListEntitiesResponse(entities=filtered)
    
    def GetEntity(self, request, context):
        """Get single entity by ID"""
        entity = entities.get(request.id)
        if entity:
            print(f"✅ GetEntity: found {request.id}")
            return world_pb2.GetEntityResponse(entity=entity)
        print(f"❌ GetEntity: {request.id} not found")
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Entity {request.id} not found")
        return world_pb2.GetEntityResponse()
    
    def Push(self, request, context):
        """Push entity changes (creates/updates)"""
        accepted = []
        for entity in request.changes:
            entities[entity.id] = entity
            accepted.append(entity.id)
            print(f"💾 Push: saved {entity.id}")
        return world_pb2.EntityChangeResponse(
            accepted=True, 
            debug=f"Updated {len(accepted)} entities: {accepted}"
        )
    
    def ExpireEntity(self, request, context):
        """Delete entity by ID"""
        if request.id in entities:
            del entities[request.id]
            print(f"🗑️  ExpireEntity: removed {request.id}")
            return world_pb2.ExpireEntityResponse()
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Entity {request.id} not found")
        return world_pb2.ExpireEntityResponse()
    
    def GetLocalNode(self, request, context):
        """Get local server node info"""
        # ✅ CORRECT: Use top-level NodeDevice (NOT nested)
        local_entity = world_pb2.Entity(
            id="ubuntu-server-local",
            label="Ubuntu WorldService Node",
            device=world_pb2.DeviceComponent(
                unique_hardware_id="ubuntu:22.04:localhost",
                labels={
                    "node": "server",
                    "role": "world-service",
                    "platform": "ubuntu"
                },
                node=world_pb2.NodeDevice(
                    hostname="localhost",
                    os="ubuntu 22.04",
                    arch="x86_64",
                    num_cpu=8
                )
            ),
            priority=world_pb2.PriorityRoutine
        )
        print("🖥️  GetLocalNode: returning server info")
        return world_pb2.GetLocalNodeResponse(
            entity=local_entity, 
            node_id="ubuntu-server-local"
        )
    
    def RunTask(self, request, context):
        """Run task on entity (stub)"""
        task_id = f"task-{int(time.time())}-{request.entity_id}"
        print(f"▶️  RunTask: queued {task_id} for {request.entity_id}")
        return world_pb2.RunTaskResponse(
            execution_id=task_id,
            status=world_pb2.TaskStatusRunning
        )

def _matches_filter(entity, filter_pb):
    """Simple filter matching logic"""
    if filter_pb.id and filter_pb.id != entity.id:
        return False
    if filter_pb.label and filter_pb.label not in (entity.label or ""):
        return False
    return True

def serve():
    """Start gRPC server on localhost:5051"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register service
    world_pb2_grpc.add_WorldServiceServicer_to_server(
        WorldServiceServicer(), server
    )
    
    # Enable reflection for grpcurl
    SERVICE_NAMES = (
        world_pb2.DESCRIPTOR.services_by_name['WorldService'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    
    # Bind port
    server.add_insecure_port('[::]:5051')
    
    print("=" * 60)
    print("🚀 WorldService gRPC Server")
    print("📍 localhost:5051")
    print("=" * 60)
    print("grpcurl commands:")
    print("  grpcurl -plaintext localhost:5051 list")
    print("  grpcurl -plaintext localhost:5051 world.WorldService/GetLocalNode")
    print("=" * 60)
    
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        server.stop(0)

if __name__ == '__main__':
    serve()
