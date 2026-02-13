"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var world_1 = require("@projectqai/proto/world");
var protobuf_1 = require("@bufbuild/protobuf");
var connect_1 = require("@connectrpc/connect");
var connect_web_1 = require("@connectrpc/connect-web");
// Create an entity
var entity = (0, protobuf_1.create)(world_1.EntitySchema, {
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
var transport = (0, connect_web_1.createConnectTransport)({
    baseUrl: "http://localhost:50051"
});
var client = (0, connect_1.createClient)(world_1.WorldService, transport);
var response = await client.push({
    changes: [entity]
});
