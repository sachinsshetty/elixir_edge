import { EntitySchema, WorldService } from "@projectqai/proto/world";
import { create } from "@bufbuild/protobuf";
import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";

// Create an entity
const entity = create(EntitySchema, {
  id: "sensor-1",
  geo: {
    latitude: 52.52,
    longitude: 13.40,
    altitude: 100
  },
  symbol: {
    milStd2525C: "SFGPES----"
  }
});

// Connect to Hydris and push the entity
const transport = createConnectTransport({
  baseUrl: "http://localhost:50051"
});
const client = createClient(WorldService, transport);

const response = await client.push({
  changes: [entity]
});