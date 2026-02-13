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
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
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
import java.io.IOException

class MainActivity : ComponentActivity(), SerialInputOutputManager.Listener {

    private var serialPort: UsbSerialPort? = null
    private var ioManager: SerialInputOutputManager? = null
    private val framer = MeshtasticFramer()

    private var statusText by mutableStateOf("Not connected")
    private var logText by mutableStateOf("")
    private var isConnected by mutableStateOf(false)

    private val ACTION_USB_PERMISSION = "com.slabstech.health.elixir_t_echo.USB_PERMISSION"
    private val TAG = "TechoApp"

    private val usbPermissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (ACTION_USB_PERMISSION != intent.action) return

            val device: UsbDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
            }

            val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
            if (granted && device != null) {
                log("✓ USB permission granted")
                connectToDevice(device)
            } else {
                setStatus("USB permission denied")
                log("✗ USB permission denied")
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

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
                    onConnect = { findAndRequestUsbPermission() },
                    onDisconnect = { disconnect() },
                    onSendMessage = { msg -> sendTextMessage(msg) },
                    onSendWorldEntity = { sendWorldEntity() }
                )
            }
        }

        intent?.let { handleIntent(it) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent) {
        if (UsbManager.ACTION_USB_DEVICE_ATTACHED == intent.action) {
            log("USB device attached")
            findAndRequestUsbPermission()
        }
    }

    private fun findAndRequestUsbPermission() {
        val usbManager = getSystemService(Context.USB_SERVICE) as? UsbManager
        if (usbManager == null) {
            setStatus("USB Manager not available")
            log("✗ UsbManager is null")
            return
        }

        log("=== USB DEBUG ===")
        log("USB devices: ${usbManager.deviceList.size}")

        usbManager.deviceList.values.forEachIndexed { i, device ->
            log("Device $i: ${device.deviceName}")
            log("  VID:PID = 0x${device.vendorId.toString(16)}:0x${device.productId.toString(16)}")
            log("  Class: ${device.deviceClass}")
            log("  Interfaces: ${device.interfaceCount}")
        }

        val drivers = UsbSerialProber.getDefaultProber().findAllDrivers(usbManager)
        log("Serial drivers found: ${drivers.size}")

        if (drivers.isEmpty()) {
            setStatus("No USB serial drivers found")
            log("✗ No devices matched usb-serial-for-android")
            return
        }

        val driver = drivers.first()
        val device = driver.device
        log("✓ Matched: ${device.deviceName} (0x${device.vendorId.toString(16)}:0x${device.productId.toString(16)})")

        if (usbManager.hasPermission(device)) {
            log("Already have permission")
            connectToDevice(device)
        } else {
            log("Requesting permission...")
            val piFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                PendingIntent.FLAG_MUTABLE
            } else {
                0
            }
            val permissionIntent = PendingIntent.getBroadcast(
                this, 0, Intent(ACTION_USB_PERMISSION), piFlags
            )
            usbManager.requestPermission(device, permissionIntent)
            setStatus("Requesting USB permission…")
        }
    }

    private fun connectToDevice(device: UsbDevice) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
                val driver = UsbSerialProber.getDefaultProber().probeDevice(device)

                if (driver == null) {
                    withContext(Dispatchers.Main) {
                        setStatus("No serial driver")
                        log("✗ No driver for device")
                    }
                    return@launch
                }

                val connection = usbManager.openDevice(driver.device)
                if (connection == null) {
                    withContext(Dispatchers.Main) {
                        setStatus("Failed to open device")
                        log("✗ openDevice() returned null")
                    }
                    return@launch
                }

                withContext(Dispatchers.Main) { disconnectInternal(keepLog = true) }

                val port = driver.ports.firstOrNull()
                if (port == null) {
                    withContext(Dispatchers.Main) {
                        setStatus("No ports on device")
                        log("✗ Driver has 0 ports")
                    }
                    connection.close()
                    return@launch
                }

                port.open(connection)
                port.setParameters(115200, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)

                serialPort = port
                ioManager = SerialInputOutputManager(port, this@MainActivity).also { it.start() }

                withContext(Dispatchers.Main) {
                    isConnected = true
                    setStatus("Connected (115200 baud)")
                    log("✓ USB serial connected")
                }

                requestDeviceConfig()

            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    setStatus("Error: ${e.message}")
                    log("✗ ${e.javaClass.simpleName}: ${e.message}")
                    Log.e(TAG, "Connection error", e)
                    disconnectInternal(keepLog = true)
                }
            }
        }
    }

    private fun requestDeviceConfig() {
        try {
            val toRadio = MeshProtos.ToRadio.newBuilder()
                .setWantConfigId((System.currentTimeMillis() and 0x7fffffff).toInt())
                .build()
            sendToRadio(toRadio)
            log("→ Requested device config")
        } catch (e: Exception) {
            log("✗ Failed to request config: ${e.message}")
        }
    }

    private fun sendTextMessage(text: String) {
        if (text.isBlank()) return

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val data = MeshProtos.Data.newBuilder()
                    .setPortnum(Portnums.PortNum.TEXT_MESSAGE_APP)
                    .setPayload(com.google.protobuf.ByteString.copyFromUtf8(text))
                    .build()

                // Generate non-zero packet ID for reliable delivery
                val packetId = kotlin.random.Random.nextInt(1, Int.MAX_VALUE)

                val packet = MeshProtos.MeshPacket.newBuilder()
                    .setTo(0xFFFFFFFF.toInt())  // Broadcast to all nodes
                    .setDecoded(data)
                    .setWantAck(true)           // Request acknowledgment
                    .setId(packetId)
                    .setHopLimit(3)             // Max 3 hops
                    .build()

                val toRadio = MeshProtos.ToRadio.newBuilder()
                    .setPacket(packet)
                    .build()

                sendToRadio(toRadio)

                withContext(Dispatchers.Main) {
                    log("→ Sent text [id=$packetId]: $text")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    log("✗ Send failed: ${e.message}")
                }
                Log.e(TAG, "Send error", e)
            }
        }
    }

    private fun sendWorldEntity() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // Create a world.Entity protobuf message
                val entity = world.World.Entity.newBuilder()
                    .setId("lilygo-techo-001")
                    .setLabel("T-Echo Drone Node")
                    .setPriority(world.World.Priority.PriorityRoutine)
                    .setGeo(
                        world.World.GeoSpatialComponent.newBuilder()
                            .setLongitude(8.6821)
                            .setLatitude(50.1109)
                            .setAltitude(100.0)
                            .build()
                    )
                    .setDevice(
                        world.World.DeviceComponent.newBuilder()
                            .setUniqueHardwareId("nRF52840:ABC123")
                            .putLabels("node", "techo-node")
                            .putLabels("role", "sensor")
                            .setSerial(
                                world.World.SerialDevice.newBuilder()
                                    .setPath("/dev/ttyACM0")
                                    .setBaudRate(115200)
                                    .build()
                            )
                            .build()
                    )
                    .build()

                val entityBytes = entity.toByteArray()

                // Check payload size (Meshtastic limit ~237 bytes)
                if (entityBytes.size > 230) {
                    withContext(Dispatchers.Main) {
                        log("⚠ Entity too large: ${entityBytes.size} bytes (max ~230)")
                    }
                    return@launch
                }

                val data = MeshProtos.Data.newBuilder()
                    .setPortnum(Portnums.PortNum.PRIVATE_APP)  // Private app portnum 256
                    .setPayload(com.google.protobuf.ByteString.copyFrom(entityBytes))
                    .build()

                val packetId = kotlin.random.Random.nextInt(1, Int.MAX_VALUE)

                val packet = MeshProtos.MeshPacket.newBuilder()
                    .setTo(0xFFFFFFFF.toInt())  // Broadcast
                    .setDecoded(data)
                    .setWantAck(true)
                    .setId(packetId)
                    .setHopLimit(3)
                    .build()

                val toRadio = MeshProtos.ToRadio.newBuilder()
                    .setPacket(packet)
                    .build()

                sendToRadio(toRadio)

                withContext(Dispatchers.Main) {
                    log("→ Sent world.Entity [id=$packetId, ${entityBytes.size} bytes]")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    log("✗ Send world.Entity failed: ${e.message}")
                }
                Log.e(TAG, "Send world.Entity error", e)
            }
        }
    }

    private fun sendToRadio(toRadio: MeshProtos.ToRadio) {
        val port = serialPort ?: run {
            log("✗ Not connected")
            return
        }
        try {
            val payload = toRadio.toByteArray()
            val framed = framer.frame(payload)
            port.write(framed, 1000)
            Log.d(TAG, "Wrote ${framed.size} bytes to serial")
        } catch (e: IOException) {
            runOnUiThread { log("✗ USB write error: ${e.message}") }
            Log.e(TAG, "Write error", e)
        }
    }

    // SerialInputOutputManager.Listener
    override fun onNewData(data: ByteArray) {
        Log.d(TAG, "Received ${data.size} bytes from serial")
        framer.feed(data) { payload ->
            try {
                val fromRadio = MeshProtos.FromRadio.parseFrom(payload)
                runOnUiThread { handleFromRadio(fromRadio) }
            } catch (e: Exception) {
                runOnUiThread { log("✗ Parse error: ${e.message}") }
                Log.e(TAG, "Parse error", e)
            }
        }
    }

    override fun onRunError(e: Exception) {
        runOnUiThread {
            log("✗ Serial IO error: ${e.message}")
            setStatus("Connection lost")
            Log.e(TAG, "IO error", e)
            disconnect()
        }
    }

    private fun handleFromRadio(fromRadio: MeshProtos.FromRadio) {
        // Log all FromRadio types for debugging
        Log.d(TAG, "FromRadio: ${fromRadio.payloadVariantCase}")

        when {
            fromRadio.hasMyInfo() -> {
                val nodeId = "0x${fromRadio.myInfo.myNodeNum.toString(16)}"
                log("✓ MyInfo: $nodeId")
            }

            fromRadio.hasNodeInfo() -> {
                val node = fromRadio.nodeInfo
                val nodeId = "0x${node.num.toString(16)}"
                val name = node.user.longName.ifEmpty { node.user.shortName.ifEmpty { "Unknown" } }
                log("✓ NodeInfo: $name ($nodeId)")
            }

            fromRadio.hasConfig() -> {
                log("✓ Config received")
            }

            fromRadio.hasModuleConfig() -> {
                log("✓ ModuleConfig received")
            }

            fromRadio.hasChannel() -> {
                val ch = fromRadio.channel
                val name = ch.settings.name.ifEmpty { "Channel ${ch.index}" }
                log("✓ Channel ${ch.index}: $name")
            }

            fromRadio.hasConfigCompleteId() -> {
                log("✓ Config complete (id=${fromRadio.configCompleteId})")
            }

            fromRadio.hasLogRecord() -> {
                val logRecord = fromRadio.logRecord
                log("← Log: ${logRecord.message}")
            }

            fromRadio.hasPacket() -> {
                val packet = fromRadio.packet
                val fromNode = "0x${packet.from.toString(16)}"

                // Check if it's an ACK/routing response
                if (packet.hasDecoded()) {
                    val decoded = packet.decoded

                    when (decoded.portnum) {
                        Portnums.PortNum.TEXT_MESSAGE_APP -> {
                            val text = decoded.payload.toStringUtf8()
                            log("← $fromNode: $text")
                        }

                        Portnums.PortNum.ROUTING_APP -> {
                            log("← $fromNode: Routing (ACK/NAK)")
                        }

                        Portnums.PortNum.TELEMETRY_APP ->
                            log("← $fromNode: Telemetry")

                        Portnums.PortNum.POSITION_APP ->
                            log("← $fromNode: Position")

                        Portnums.PortNum.NODEINFO_APP ->
                            log("← $fromNode: NodeInfo")

                        Portnums.PortNum.PRIVATE_APP -> {
                            val bytes = decoded.payload.toByteArray()
                            log("← $fromNode: PRIVATE_APP (${bytes.size} bytes)")

                            // Try to parse as world.Entity
                            try {
                                val entity = world.World.Entity.parseFrom(bytes)
                                log("  └─ Entity: ${entity.id} (${entity.label})")
                                if (entity.hasGeo()) {
                                    log("     Lat/Lon: ${entity.geo.latitude}, ${entity.geo.longitude}")
                                }
                            } catch (e: Exception) {
                                log("  └─ (not a world.Entity)")
                            }
                        }

                        else ->
                            log("← $fromNode: ${decoded.portnum.name}")
                    }
                } else {
                    log("← $fromNode: Encrypted packet")
                }
            }

            fromRadio.hasRebooted() -> {
                log("⚠ Device rebooted")
            }

            else -> {
                log("← FromRadio: ${fromRadio.payloadVariantCase}")
            }
        }
    }

    private fun disconnect() {
        log("Disconnecting...")
        disconnectInternal(keepLog = true)
    }

    private fun disconnectInternal(keepLog: Boolean) {
        try { ioManager?.stop() } catch (_: Exception) { }
        ioManager = null
        try { serialPort?.close() } catch (_: Exception) { }
        serialPort = null
        isConnected = false
        setStatus("Disconnected")
        if (!keepLog) logText = ""
    }

    private fun setStatus(s: String) {
        statusText = s
    }

    private fun log(message: String) {
        val t = System.currentTimeMillis() % 100000
        logText += "[$t] $message\n"
        Log.d(TAG, message)
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            unregisterReceiver(usbPermissionReceiver)
        } catch (_: Exception) { }
        disconnectInternal(keepLog = false)
    }
}

@Composable
fun TechoScreen(
    statusText: String,
    logText: String,
    isConnected: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onSendMessage: (String) -> Unit,
    onSendWorldEntity: () -> Unit
) {
    var messageText by remember { mutableStateOf("") }
    val scrollState = rememberScrollState()

    LaunchedEffect(logText) {
        scrollState.animateScrollTo(scrollState.maxValue)
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                "T‑Echo Meshtastic",
                style = MaterialTheme.typography.headlineSmall
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onConnect,
                    enabled = !isConnected,
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Connect USB")
                }

                Button(
                    onClick = onDisconnect,
                    enabled = isConnected,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isConnected)
                            MaterialTheme.colorScheme.error
                        else
                            MaterialTheme.colorScheme.primary
                    )
                ) {
                    Text("Disconnect")
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = if (isConnected)
                        MaterialTheme.colorScheme.primaryContainer
                    else
                        MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Text(
                    text = statusText,
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            OutlinedTextField(
                value = messageText,
                onValueChange = { messageText = it },
                label = { Text("Message") },
                placeholder = { Text("Type a message...") },
                modifier = Modifier.fillMaxWidth(),
                enabled = isConnected,
                singleLine = true
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        onSendMessage(messageText)
                        messageText = ""
                    },
                    enabled = isConnected && messageText.isNotBlank(),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Send Text")
                }

                Button(
                    onClick = onSendWorldEntity,
                    enabled = isConnected,
                    modifier = Modifier.weight(1f)
                ) {
                    Text("Send Entity")
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Text("Activity Log", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(6.dp))

            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = MaterialTheme.shapes.small,
                tonalElevation = 2.dp
            ) {
                Text(
                    text = if (logText.isBlank()) "Waiting for connection..." else logText,
                    modifier = Modifier
                        .padding(10.dp)
                        .verticalScroll(scrollState),
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}
