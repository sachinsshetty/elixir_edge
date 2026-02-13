import grpc
import world_pb2
import world_pb2_grpc
from concurrent import futures
from google.protobuf import timestamp_pb2
import time

# In-memory store for entities (replace with real DB later)
entities = {}

class WorldServiceServicer(world_pb2_grpc.WorldServiceServicer):
    
    def ListEntities(self, request, context):
        """List entities matching filter"""
        filtered = [e for e in entities.values() if _matches_filter(e, request.filter)]
        return world_pb2.ListEntitiesResponse(entities=filtered)
    
    def GetEntity(self, request, context):
        """Get single entity by ID"""
        entity = entities.get(request.id)
        if entity:
            return world_pb2.GetEntityResponse(entity=entity)
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Entity {request.id} not found")
        return world_pb2.GetEntityResponse()
    
    def Push(self, request, context):
        """Push entity changes (creates/updates)"""
        accepted = []
        for entity in request.changes:
            entities[entity.id] = entity
            accepted.append(entity.id)
        return world_pb2.EntityChangeResponse(accepted=True, debug=f"Updated {len(accepted)} entities")
    
    def ExpireEntity(self, request, context):
        """Expire entity by ID"""
        if request.id in entities:
            del entities[request.id]
        return world_pb2.ExpireEntityResponse()
    
    def GetLocalNode(self, request, context):
        """Get local node info (stub)"""
        local = world_pb2.Entity(
            id="local-node-001",
            label="Ubuntu Server Node",
            device=world_pb2.DeviceComponent(
                unique_hardware_id="ubuntu:localhost",
                labels={"node": "server", "role": "world-service"}
            )
        )
        return world_pb2.GetLocalNodeResponse(entity=local, node_id="local-node-001")
    
    def RunTask(self, request, context):
        """Run task on entity (stub)"""
        return world_pb2.RunTaskResponse(
            execution_id=f"task-{int(time.time())}",
            status=world_pb2.TaskStatusRunning
        )

def _matches_filter(entity, filter):
    """Simple filter matcher (extend as needed)"""
    if filter.id and filter.id != entity.id:
        return False
    if filter.label and filter.label not in entity.label:
        return False
    return True

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    world_pb2_grpc.add_WorldServiceServicer_to_server(WorldServiceServicer(), server)
    server.add_insecure_port('[::]:5051')
    print("🚀 WorldService gRPC server running on localhost:5051")
    print("📱 Test with your client.py or grpcurl:")
    print("   grpcurl -plaintext -d '{\"filter\":{}}' localhost:5051 world.WorldService/ListEntities")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
