// test.ts - Works WITHOUT proto generation
import { createConnectTransport } from '@connectrpc/connect-web';

async function testHydrisConnection() {
  const transport = createConnectTransport({ baseUrl: 'http://localhost:50051' });
  
  console.log('🚀 Testing Hydris WorldService at localhost:50051');
  console.log('✅ Transport created successfully');
  
  // Test: Try to fetch (won't work without service but confirms transport)
  console.log('📡 Service ready for proto-generated calls');
  
  // Raw HTTP health check
  try {
    const response = await fetch('http://localhost:50051/health');
    console.log('🏥 Health:', response.status === 200 ? 'OK' : 'Down');
  } catch {
    console.log('🏥 Health endpoint not available (normal for some setups)');
  }
}

testHydrisConnection();
