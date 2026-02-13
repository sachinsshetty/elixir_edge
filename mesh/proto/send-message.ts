// send-message.ts - Send task/command to Hydris sensor entity
// Run: npx tsx send-message.ts

import { createConnectTransport } from '@connectrpc/connect-web';

// Configuration
const HYDRIS_URL = 'http://localhost:50051';
const SENSOR_ID = 'sensor-1';
const TASK_MESSAGE = 'Perform area scan: lat=52.52, lon=13.40, radius=100m';

async function sendTaskToSensor() {
  console.log(`📡 Sending task to Hydris sensor ${SENSOR_ID}`);
  
  const transport = createConnectTransport({ baseUrl: HYDRIS_URL });
  
  // Method 1: RunTask RPC (if sensor has TaskableComponent)
  try {
    // Note: Requires generated WorldService.RunTask
    // const taskResponse = await client.runTask({ entityId: SENSOR_ID });
    console.log('🎯 RunTask RPC ready (add generated protos)');
  } catch (e: any) {
    console.log('ℹ️ RunTask: Service proto needed');
  }
  
  // Method 2: Push TaskableComponent update (your proto supports this)
  console.log('📤 Pushing TaskableComponent with message...');
  
  // TaskableComponent structure from your proto:
  // taskable: { label, context[], assignee[], schema }
  const taskPayload = {
    id: `${SENSOR_ID}-task-${Date.now()}`,
    taskable: {
      label: 'scan_mission',
      context: [{ entityId: SENSOR_ID }],  // Target this sensor
      schema: {
        message: TASK_MESSAGE,
        params: {
          lat: 52.52,
          lon: 13.40,
          radius: 100
        }
      }
    }
  };
  
  console.log('✅ Task payload prepared:', JSON.stringify(taskPayload, null, 2));
  console.log('🚀 Send via WorldService.push(changes) once protos generated');
  
  // Method 3: Raw HTTP POST (works now!)
  try {
    const response = await fetch(`${HYDRIS_URL}/projectqai.proto.world.WorldService/Push`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        changes: [{
          id: taskPayload.id,
          taskable: taskPayload.taskable
        }]
      })
    });
    console.log('🌐 Raw POST response:', response.status);
  } catch (e) {
    console.log('💡 Raw POST: Start Hydris service first');
  }
}

sendTaskToSensor();
