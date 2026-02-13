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
                connectToDevice(device)
            } else {
                statusText = "USB permission denied"
                log("Permission denied for USB device")
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
                    onSendMessage = { msg -> sendTextMessage(msg) }
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
            findAndRequestUsbPermission()
        }
    }

    private fun findAndRequestUsbPermission() {
        val usbManager = getSystemService(Context.USB_SERVICE) as? UsbManager
        if (usbManager == null) {
            setStatus("USB Manager not available")
            log("UsbManager is null")
            return
        }

        log("=== USB DEBUG ===")
        log("USB devices count: ${usbManager.deviceList.size}")

        usbManager.deviceList.values.forEachIndexed { i, device ->
            log("Device $i:")
            log("  Name: ${device.deviceName}")
            log("  VID: 0x${device.vendorId.toString(16)}")
            log("  PID: 0x${device.productId.toString(16)}")
            log("  Class: ${device.deviceClass}")
            log("  Interfaces: ${device.interfaceCount}")
            for (j in 0 until device.interfaceCount) {
                val intf = device.getInterface(j)
                log("    Intf $j: class=${intf.interfaceClass}, subclass=${intf.interfaceSubclass}, protocol=${intf.interfaceProtocol}")
            }
        }

        val drivers = UsbSerialProber.getDefaultProber().findAllDrivers(usbManager)
        log("Default drivers found: ${drivers.size}")

        if (drivers.isEmpty()) {
            setStatus("No serial drivers matched")
            log("No devices matched usb-serial-for-android default drivers.")
            log("If you see a device above, note its VID/PID and we'll add custom driver support.")
            return
        }

        val driver = drivers.first()
        val device = driver.device
        log("Matched: ${device.deviceName} (VID=0x${device.vendorId.toString(16)}, PID=0x${device.productId.toString(16)})")

        if (usbManager.hasPermission(device)) {
            connectToDevice(device)
        } else {
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
                        log("No driver for device")
                    }
                    return@launch
                }

                val connection = usbManager.openDevice(driver.device)
                if (connection == null) {
                    withContext(Dispatchers.Main) {
                        setStatus("Failed to open device")
                        log("openDevice() returned null")
                    }
                    return@launch
                }

                withContext(Dispatchers.Main) { disconnectInternal(keepLog = true) }

                val port = driver.ports.firstOrNull()
                if (port == null) {
                    withContext(Dispatchers.Main) {
                        setStatus("No ports on device")
                        log("Driver has 0 ports")
                    }
                    return@launch
                }

                port.open(connection)
                port.setParameters(115200, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)

                serialPort = port
                ioManager = SerialInputOutputManager(port, this@MainActivity).also { it.start() }

                withContext(Dispatchers.Main) {
                    isConnected = true
                    setStatus("Connected (115200)")
                    log("✓ Connected")
                }

                requestDeviceConfig()

            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    setStatus("Error: ${e.message}")
                    log("✗ ${e.javaClass.simpleName}: ${e.message}")
                    disconnectInternal(keepLog = true)
                }
            }
        }
    }

    private fun requestDeviceConfig() {
        val toRadio = MeshProtos.ToRadio.newBuilder()
            .setWantConfigId((System.currentTimeMillis() and 0x7fffffff).toInt())
            .build()
        sendToRadio(toRadio)
        log("→ Requested config")
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
                    .setDecoded(data)
                    .build()

                val toRadio = MeshProtos.ToRadio.newBuilder()
                    .setPacket(packet)
                    .build()

                sendToRadio(toRadio)
                withContext(Dispatchers.Main) { log("→ Sent: $text") }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { log("✗ Send failed: ${e.message}") }
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
            runOnUiThread { log("✗ Write error: ${e.message}") }
        }
    }

    override fun onNewData(data: ByteArray) {
        framer.feed(data) { payload ->
            try {
                val fromRadio = MeshProtos.FromRadio.parseFrom(payload)
                runOnUiThread { handleFromRadio(fromRadio) }
            } catch (e: Exception) {
                runOnUiThread { log("✗ Parse: ${e.message}") }
            }
        }
    }

    override fun onRunError(e: Exception) {
        runOnUiThread {
            log("✗ Serial error: ${e.message}")
            setStatus("Connection lost")
            disconnect()
        }
    }

    private fun handleFromRadio(fromRadio: MeshProtos.FromRadio) {
        when {
            fromRadio.hasMyInfo() -> log("✓ MyInfo: 0x${fromRadio.myInfo.myNodeNum.toString(16)}")
            fromRadio.hasNodeInfo() -> {
                val node = fromRadio.nodeInfo
                log("✓ Node: ${node.user.longName} (0x${node.num.toString(16)})")
            }
            fromRadio.hasConfigCompleteId() -> log("✓ Config complete")
            fromRadio.hasPacket() -> {
                val packet = fromRadio.packet
                if (packet.hasDecoded()) {
                    val decoded = packet.decoded
                    when (decoded.portnum) {
                        Portnums.PortNum.TEXT_MESSAGE_APP ->
                            log("← 0x${packet.from.toString(16)}: ${decoded.payload.toStringUtf8()}")
                        else ->
                            log("← Packet portnum=${decoded.portnum.name}")
                    }
                }
            }
        }
    }

    private fun disconnect() {
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
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            unregisterReceiver(usbPermissionReceiver)
        } catch (_: Exception) { }
        disconnectInternal(keepLog = true)
    }
}

@Composable
fun TechoScreen(
    statusText: String,
    logText: String,
    isConnected: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onSendMessage: (String) -> Unit
) {
    var messageText by remember { mutableStateOf("") }
    val scrollState = rememberScrollState()

    LaunchedEffect(logText) {
        scrollState.animateScrollTo(scrollState.maxValue)
    }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("T‑Echo USB", style = MaterialTheme.typography.headlineSmall)
            Spacer(modifier = Modifier.height(12.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onConnect, enabled = !isConnected, modifier = Modifier.weight(1f)) {
                    Text("Connect")
                }
                Button(onClick = onDisconnect, enabled = isConnected, modifier = Modifier.weight(1f)) {
                    Text("Disconnect")
                }
            }

            Spacer(modifier = Modifier.height(10.dp))
            Text("Status: $statusText", style = MaterialTheme.typography.bodyMedium)
            Spacer(modifier = Modifier.height(14.dp))

            OutlinedTextField(
                value = messageText,
                onValueChange = { messageText = it },
                label = { Text("Message") },
                modifier = Modifier.fillMaxWidth(),
                enabled = isConnected,
                singleLine = true
            )

            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = { onSendMessage(messageText); messageText = "" },
                enabled = isConnected && messageText.isNotBlank(),
                modifier = Modifier.fillMaxWidth()
            ) { Text("Send") }

            Spacer(modifier = Modifier.height(14.dp))
            Text("Log", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(6.dp))

            Surface(
                modifier = Modifier.fillMaxWidth().weight(1f),
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = MaterialTheme.shapes.small
            ) {
                Text(
                    text = if (logText.isBlank()) "Waiting..." else logText,
                    modifier = Modifier.padding(10.dp).verticalScroll(scrollState),
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}
