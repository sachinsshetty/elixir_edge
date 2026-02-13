package com.slabstech.health.elixir_t_echo

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import com.hoho.android.usbserial.driver.UsbSerialPort
import com.hoho.android.usbserial.driver.UsbSerialProber
import com.hoho.android.usbserial.util.SerialInputOutputManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.meshtastic.proto.MeshProtos
import org.meshtastic.proto.Portnums
// Try standard import. If this fails, your proto package is different.
// import org.meshtastic.proto.world.World
import java.io.IOException
import java.util.*

data class ReceivedMessage(
    val from: String,
    val text: String,
    val timestamp: Long,
    val isFromMe: Boolean = false
)

class MainActivity : ComponentActivity(), SerialInputOutputManager.Listener {

    private var serialPort: UsbSerialPort? = null
    private var ioManager: SerialInputOutputManager? = null
    private val framer = MeshtasticFramer()
    private lateinit var aiManager: TextClassifierManager

    // UI State
    private var statusText by mutableStateOf("Not connected")
    private var logText by mutableStateOf("")
    private var isConnected by mutableStateOf(false)
    private var myNodeNum by mutableStateOf<Int?>(null)
    private var receivedMessages by mutableStateOf(listOf<ReceivedMessage>())

    // AI State
    private var isModelLoading by mutableStateOf(false)
    private var isModelReady by mutableStateOf(false)
    private var aiPromptText by mutableStateOf("")
    private var aiResponseText by mutableStateOf("")
    private var isGenerating by mutableStateOf(false)

    private val ACTION_USB_PERMISSION = "com.slabstech.health.elixir_t_echo.USB_PERMISSION"
    private val TAG = "TechoApp"

    private val usbPermissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (ACTION_USB_PERMISSION == intent.action) {
                synchronized(this) {
                    val device: UsbDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
                    }

                    if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                        device?.let {
                            log("USB permission granted")
                            connectToDevice(it)
                        }
                    } else {
                        setStatus("USB permission denied")
                    }
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        aiManager = TextClassifierManager(this)

        lifecycleScope.launch {
            isModelLoading = true
            isModelReady = aiManager.loadModel()
            isModelLoading = false
            if (isModelReady) log("BERT Model loaded") else log("AI Model failed")
        }

        val filter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbPermissionReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(usbPermissionReceiver, filter)
        }

        setContent {
            MaterialTheme {
                TechoScreen(
                    statusText = statusText,
                    logText = logText,
                    isConnected = isConnected,
                    myNodeNum = myNodeNum,
                    receivedMessages = receivedMessages,

                    isModelLoading = isModelLoading,
                    isModelReady = isModelReady,
                    aiPrompt = aiPromptText,
                    aiResponse = aiResponseText,
                    isGenerating = isGenerating,
                    onAiPromptChange = { aiPromptText = it },
                    onGenerateAiResponse = { generateAiAnalysis() },

                    onConnect = { findAndRequestUsbPermission() },
                    onDisconnect = { disconnect() },
                    onSendMessage = { msg -> sendTextMessage(msg) },
                    // Restored functions
                    onSendWorldEntity = { sendWorldEntity() },
                    onSendSensorEntity = { sendSensorEntity() },
                    onClearMessages = { receivedMessages = emptyList() }
                )
            }
        }

        intent?.let { handleIntent(it) }
    }

    private fun generateAiAnalysis() {
        if (aiPromptText.isBlank() || !isModelReady) return
        isGenerating = true
        aiResponseText = ""
        lifecycleScope.launch {
            aiManager.classify(aiPromptText).collect { aiResponseText = it }
            isGenerating = false
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        aiManager.cleanup()
        try { unregisterReceiver(usbPermissionReceiver) } catch (_: Exception) {}
        disconnectInternal(false)
    }

    // ... [USB & Proto Handling] ...

    private fun handleIntent(intent: Intent) {
        if (UsbManager.ACTION_USB_DEVICE_ATTACHED == intent.action) {
            findAndRequestUsbPermission()
        }
    }

    private fun findAndRequestUsbPermission() {
        val usbManager = getSystemService(Context.USB_SERVICE) as? UsbManager ?: return
        val drivers = UsbSerialProber.getDefaultProber().findAllDrivers(usbManager)
        if (drivers.isEmpty()) {
            setStatus("No USB serial drivers found")
            return
        }
        val driver = drivers.first()
        val device = driver.device
        if (usbManager.hasPermission(device)) connectToDevice(device)
        else {
            val piFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0
            val permissionIntent = PendingIntent.getBroadcast(this, 0, Intent(ACTION_USB_PERMISSION), piFlags)
            usbManager.requestPermission(device, permissionIntent)
            setStatus("Requesting USB permission")
        }
    }

    private fun connectToDevice(device: UsbDevice) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
                val driver = UsbSerialProber.getDefaultProber().probeDevice(device) ?: return@launch
                val connection = usbManager.openDevice(driver.device) ?: return@launch
                val port = driver.ports.firstOrNull() ?: return@launch
                port.open(connection)
                port.setParameters(115200, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)
                serialPort = port
                ioManager = SerialInputOutputManager(port, this@MainActivity).also { it.start() }
                withContext(Dispatchers.Main) {
                    isConnected = true
                    setStatus("Connected")
                    requestDeviceConfig()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { setStatus("Error: ${e.message}") }
            }
        }
    }

    private fun requestDeviceConfig() {
        try {
            val toRadio = MeshProtos.ToRadio.newBuilder()
                .setWantConfigId((System.currentTimeMillis() / 1000).toInt())
                .build()
            sendToRadio(toRadio)
        } catch (_: Exception) {}
    }

    private fun sendTextMessage(text: String) {
        if (text.isBlank()) return
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val data = MeshProtos.Data.newBuilder()
                    .setPortnum(Portnums.PortNum.TEXT_MESSAGE_APP)
                    .setPayload(com.google.protobuf.ByteString.copyFromUtf8(text))
                    .build()
                val packet = MeshProtos.MeshPacket.newBuilder()
                    .setTo(0xFFFFFFFF.toInt())
                    .setDecoded(data)
                    .setWantAck(true)
                    .setId(kotlin.random.Random.nextInt(1, Int.MAX_VALUE))
                    .build()
                val toRadio = MeshProtos.ToRadio.newBuilder().setPacket(packet).build()
                sendToRadio(toRadio)
                withContext(Dispatchers.Main) { log("Sent: $text") }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { log("Send failed") }
            }
        }
    }

    // RESTORED: Sending World Entity
    // NOTE: This requires 'world.proto' to be compiled into 'world.World' package
    private fun sendWorldEntity() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // If 'world' is unresolved, verify your .proto file package!
                // Trying generic 'world.World' as per typical proto generation
                val entity = world.World.Entity.newBuilder()
                    .setId("lilygo-techo-001")
                    .setLabel("T-Echo Drone Node")
                    .setPriority(world.World.Priority.PriorityRoutine)
                    .setGeo(world.World.GeoSpatialComponent.newBuilder()
                        .setLongitude(8.6821)
                        .setLatitude(50.1109)
                        .setAltitude(100.0)
                        .build())
                    .build()

                val entityBytes = entity.toByteArray()
                val data = MeshProtos.Data.newBuilder()
                    .setPortnum(Portnums.PortNum.PRIVATE_APP)
                    .setPayload(com.google.protobuf.ByteString.copyFrom(entityBytes))
                    .build()

                val packet = MeshProtos.MeshPacket.newBuilder()
                    .setTo(0xFFFFFFFF.toInt())
                    .setDecoded(data)
                    .setWantAck(true)
                    .setId(kotlin.random.Random.nextInt(1, Int.MAX_VALUE))
                    .build()

                val toRadio = MeshProtos.ToRadio.newBuilder().setPacket(packet).build()
                sendToRadio(toRadio)
                withContext(Dispatchers.Main) { log("Sent World Entity") }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    log("Failed to send entity: ${e.message}")
                    Log.e(TAG, "Entity error", e)
                }
            }
        }
    }

    // RESTORED: Sending Sensor Entity
    private fun sendSensorEntity() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val entity = world.World.Entity.newBuilder()
                    .setId("sensor-sachin")
                    .setLabel("Sensor Sachin Node")
                    .setPriority(world.World.Priority.PriorityRoutine)
                    .setGeo(world.World.GeoSpatialComponent.newBuilder()
                        .setLatitude(50.52)
                        .setLongitude(23.40)
                        .setAltitude(100.0)
                        .build())
                    .setSymbol(world.World.SymbolComponent.newBuilder()
                        .setMilStd2525C("SFGPES----")
                        .build())
                    .build()

                val entityBytes = entity.toByteArray()
                val data = MeshProtos.Data.newBuilder()
                    .setPortnum(Portnums.PortNum.PRIVATE_APP)
                    .setPayload(com.google.protobuf.ByteString.copyFrom(entityBytes))
                    .build()

                val packet = MeshProtos.MeshPacket.newBuilder()
                    .setTo(0xFFFFFFFF.toInt())
                    .setDecoded(data)
                    .setWantAck(true)
                    .setId(kotlin.random.Random.nextInt(1, Int.MAX_VALUE))
                    .build()

                val toRadio = MeshProtos.ToRadio.newBuilder().setPacket(packet).build()
                sendToRadio(toRadio)
                withContext(Dispatchers.Main) { log("Sent Sensor Entity") }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { log("Failed sensor: ${e.message}") }
            }
        }
    }

    private fun sendToRadio(toRadio: MeshProtos.ToRadio) {
        val port = serialPort ?: return
        try {
            val payload = toRadio.toByteArray()
            val framed = framer.frame(payload)
            port.write(framed, 1000)
        } catch (e: IOException) {
            runOnUiThread { log("Write error") }
        }
    }

    override fun onNewData(data: ByteArray) {
        framer.feed(data) { payload ->
            try {
                val fromRadio = MeshProtos.FromRadio.parseFrom(payload)
                runOnUiThread { handleFromRadio(fromRadio) }
            } catch (_: Exception) {}
        }
    }

    override fun onRunError(e: Exception) {
        runOnUiThread { disconnectInternal(true) }
    }

    private fun handleFromRadio(fromRadio: MeshProtos.FromRadio) {
        if (fromRadio.hasMyInfo()) myNodeNum = fromRadio.myInfo.myNodeNum
        if (fromRadio.hasPacket()) {
            val packet = fromRadio.packet
            if (packet.hasDecoded() && packet.decoded.portnum == Portnums.PortNum.TEXT_MESSAGE_APP) {
                val text = packet.decoded.payload.toStringUtf8()
                val fromNode = "0x${packet.from.toString(16)}"
                val msg = ReceivedMessage(fromNode, text, System.currentTimeMillis(), false)
                receivedMessages = receivedMessages + msg
            }
            // Parse entities from PRIVATE_APP
            if (packet.hasDecoded() && packet.decoded.portnum == Portnums.PortNum.PRIVATE_APP) {
                try {
                    val bytes = packet.decoded.payload.toByteArray()
                    // Try to parse as Entity to log it
                    val entity = world.World.Entity.parseFrom(bytes)
                    log("Rx Entity: ${entity.label} (${entity.id})")
                } catch (_: Exception) {}
            }
        }
    }

    private fun disconnect() { disconnectInternal(true) }

    private fun disconnectInternal(keepLog: Boolean) {
        try { ioManager?.stop() } catch (_: Exception) {}
        ioManager = null
        try { serialPort?.close() } catch (_: Exception) {}
        serialPort = null
        isConnected = false
        myNodeNum = null
        setStatus("Disconnected")
        if (!keepLog) logText = ""
    }

    private fun setStatus(s: String) { statusText = s }
    private fun log(message: String) {
        val t = System.currentTimeMillis() % 100000
        logText = "[$t] $message\n$logText"
        Log.d(TAG, message)
    }
}

// ... [TechoScreen remains same] ...
@Composable
fun TechoScreen(
    statusText: String,
    logText: String,
    isConnected: Boolean,
    myNodeNum: Int?,
    receivedMessages: List<ReceivedMessage>,
    isModelLoading: Boolean,
    isModelReady: Boolean,
    aiPrompt: String,
    aiResponse: String,
    isGenerating: Boolean,
    onAiPromptChange: (String) -> Unit,
    onGenerateAiResponse: () -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onSendMessage: (String) -> Unit,
    onSendWorldEntity: () -> Unit,
    onSendSensorEntity: () -> Unit,
    onClearMessages: () -> Unit
) {
    var messageText by remember { mutableStateOf("") }
    var selectedTab by remember { mutableStateOf(0) }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("TEcho Meshtastic", style = MaterialTheme.typography.headlineSmall)
                    myNodeNum?.let { Text("Node: 0x${it.toString(16)}", style = MaterialTheme.typography.bodySmall) }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onConnect, enabled = !isConnected) { Text("Connect") }
                    Button(onClick = onDisconnect, enabled = isConnected, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) { Text("Disconnect") }
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(statusText, style = MaterialTheme.typography.bodyMedium)
            Spacer(modifier = Modifier.height(14.dp))
            TabRow(selectedTabIndex = selectedTab) {
                Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }, text = { Text("Chat") })
                Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }, text = { Text("Log") })
                Tab(selected = selectedTab == 2, onClick = { selectedTab = 2 }, text = { Text("AI") })
            }
            Spacer(modifier = Modifier.height(8.dp))
            Surface(modifier = Modifier.fillMaxWidth().weight(1f), color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.small) {
                when (selectedTab) {
                    0 -> {
                        Column(modifier = Modifier.fillMaxSize().padding(8.dp)) {
                            Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                                receivedMessages.forEach { msg -> Text("${msg.from}: ${msg.text}", modifier = Modifier.padding(4.dp)) }
                            }
                            Row {
                                OutlinedTextField(value = messageText, onValueChange = { messageText = it }, modifier = Modifier.weight(1f))
                                Button(onClick = { onSendMessage(messageText); messageText = "" }, enabled = isConnected) { Text("Send") }
                            }
                            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                                Button(onClick = onSendWorldEntity, enabled = isConnected) { Text("World") }
                                Button(onClick = onSendSensorEntity, enabled = isConnected) { Text("Sensor") }
                            }
                        }
                    }
                    1 -> Text(logText, modifier = Modifier.padding(10.dp).verticalScroll(rememberScrollState()), fontFamily = FontFamily.Monospace)
                    2 -> {
                        Column(modifier = Modifier.padding(16.dp).verticalScroll(rememberScrollState())) {
                            if (isModelLoading) Text("Loading Model...")
                            else if (isModelReady) {
                                Text("BERT Ready", color = Color.Green)
                                Spacer(modifier = Modifier.height(8.dp))
                                OutlinedTextField(value = aiPrompt, onValueChange = onAiPromptChange, label = { Text("Text to Analyze") }, modifier = Modifier.fillMaxWidth())
                                Spacer(modifier = Modifier.height(8.dp))
                                Button(onClick = onGenerateAiResponse, enabled = !isGenerating && aiPrompt.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                                    Text(if (isGenerating) "Analyzing..." else "Classify")
                                }
                                if (aiResponse.isNotBlank()) {
                                    Spacer(modifier = Modifier.height(16.dp))
                                    Text(aiResponse)
                                }
                            } else {
                                Text("Model Error", color = Color.Red)
                            }
                        }
                    }
                }
            }
        }
    }
}
