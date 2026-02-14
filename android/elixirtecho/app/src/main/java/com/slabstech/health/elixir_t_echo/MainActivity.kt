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
import androidx.compose.material3.ExperimentalMaterial3Api
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
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.meshtastic.proto.MeshProtos
import org.meshtastic.proto.Portnums
import java.io.IOException
import java.util.*

private const val RISK_GREEN = "green"
private const val RISK_YELLOW = "yellow"
private const val RISK_RED = "red"

private val RECOMMENDATIONS = mapOf(
    RISK_GREEN to "Continue normal activity. Stay hydrated.",
    RISK_YELLOW to "Monitor vital signs. Consider rest and hydration soon.",
    RISK_RED to "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."
)

private fun parseRiskFromAiResult(aiResult: String): Pair<String, Float> {
    var risk = RISK_GREEN
    var confidence = 0f
    val normalized = aiResult.trim().lowercase()
    if (normalized.contains(RECOMMENDATIONS[RISK_RED]!!.lowercase())) risk = RISK_RED
    else if (normalized.contains(RECOMMENDATIONS[RISK_YELLOW]!!.lowercase())) risk = RISK_YELLOW
    else if (normalized.contains(RECOMMENDATIONS[RISK_GREEN]!!.lowercase())) risk = RISK_GREEN
    val lines = aiResult.split("\n")
    for (line in lines) {
        if (line.startsWith("Confidence:", ignoreCase = true)) {
            val num = line.replace(Regex("[^0-9.]+"), "").trim()
            confidence = num.toFloatOrNull() ?: 0f
        }
    }
    return risk to confidence
}

private fun getRecommendationForRisk(risk: String): String = RECOMMENDATIONS[risk] ?: RECOMMENDATIONS[RISK_GREEN]!!

private fun escapeJson(s: String): String = s
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")
    .replace("\n", " ")
    .replace("\r", "")

private fun buildStructuredMessage(
    person: String,
    input: String,
    risk: String,
    analysis: String,
    alert: Boolean
): String {
    val ts = System.currentTimeMillis() / 1000
    return """{"v":1,"person":"${escapeJson(person)}","ts":$ts,"risk":"$risk","analysis":"${escapeJson(analysis)}","alert":$alert,"input":"${escapeJson(input)}"}"""
}

class MainActivity : ComponentActivity(), SerialInputOutputManager.Listener {

    private var serialPort: UsbSerialPort? = null
    private var ioManager: SerialInputOutputManager? = null
    private var heartbeatJob: Job? = null
    private val framer = MeshtasticFramer()
    private lateinit var aiManager: TextClassifierManager

    // UI State
    private var statusText by mutableStateOf("Not connected")
    private var logText by mutableStateOf("")
    private var isConnected by mutableStateOf(false)
    private var myNodeNum by mutableStateOf<Int?>(null)

    // Health + AI State
    private var isModelLoading by mutableStateOf(false)
    private var isModelReady by mutableStateOf(false)
    private var healthInputText by mutableStateOf("")
    private var lastAiLevel by mutableStateOf("")
    private var isSending by mutableStateOf(false)
    private var showAlertDialog by mutableStateOf(false)
    private var alertDialogMessage by mutableStateOf("")

    private val ACTION_USB_PERMISSION = "com.slabstech.health.elixir_t_echo.USB_PERMISSION"
    private val TAG = "TechoApp"
    private val MAX_LOG_CHARS = 50_000

    companion object {
        val PEOPLE = listOf("Person 1", "Person 2", "Person 3")
    }
    private var selectedPersonIndex by mutableStateOf(0)

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
            if (isModelReady) log("AI model loaded") else log("AI model failed")
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
                    people = PEOPLE,
                    selectedPersonIndex = selectedPersonIndex,
                    onPersonSelect = { selectedPersonIndex = it },
                    healthInput = healthInputText,
                    onHealthInputChange = { healthInputText = it },
                    lastAiLevel = lastAiLevel,
                    isModelLoading = isModelLoading,
                    isModelReady = isModelReady,
                    isSending = isSending,
                    onClassifyAndSend = { classifyAndSendToMesh() },
                    onConnect = { findAndRequestUsbPermission() },
                    onDisconnect = { disconnect() },
                    showAlertDialog = showAlertDialog,
                    alertDialogMessage = alertDialogMessage,
                    onDismissAlert = { showAlertDialog = false; alertDialogMessage = "" }
                )
            }
        }

        intent?.let { handleIntent(it) }
    }

    private fun classifyAndSendToMesh() {
        val input = healthInputText.trim()
        if (input.isBlank() || !isModelReady || !isConnected) {
            log(if (!isConnected) "Connect device first" else "Enter health parameters")
            return
        }
        isSending = true
        lastAiLevel = ""
        showAlertDialog = false
        lifecycleScope.launch {
            var aiResult = ""
            aiManager.classify(input).collect { aiResult = it }
            lastAiLevel = aiResult
            val personName = PEOPLE.getOrNull(selectedPersonIndex) ?: PEOPLE.first()
            val (risk, _) = parseRiskFromAiResult(aiResult)
            val recommendation = getRecommendationForRisk(risk)
            val alert = risk == RISK_YELLOW || risk == RISK_RED
            if (alert) {
                alertDialogMessage = recommendation
                showAlertDialog = true
            }
            val message = buildStructuredMessage(personName, input, risk, recommendation, alert)
            sendToMesh(message)
            isSending = false
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
                framer.reset()
                serialPort = port
                ioManager = SerialInputOutputManager(port, this@MainActivity).also { it.start() }
                withContext(Dispatchers.Main) {
                    isConnected = true
                    setStatus("Connected")
                    requestDeviceConfig()
                    startHeartbeat()
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

    private fun sendToMesh(text: String) {
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
                withContext(Dispatchers.Main) { if (!isDestroyed) log("Sent to mesh: $text") }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { if (!isDestroyed) log("Send failed: ${e.message}") }
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
            runOnUiThread { if (!isDestroyed) log("Write error") }
        }
    }

    override fun onNewData(data: ByteArray) {
        if (data.isEmpty()) return
        // PROTO mode: framed FromRadio packets
        framer.feed(data) { payload ->
            try {
                val fromRadio = MeshProtos.FromRadio.parseFrom(payload)
                runOnUiThread {
                    if (!isDestroyed) handleFromRadio(fromRadio)
                }
            } catch (e: Exception) {
                if (!isDestroyed) runOnUiThread { log("Rx parse error: ${e.message}") }
            }
        }
    }

    override fun onRunError(e: Exception) {
        runOnUiThread {
            if (!isDestroyed) disconnectInternal(true)
        }
    }

    private fun handleFromRadio(fromRadio: MeshProtos.FromRadio) {
        if (isDestroyed) return
        if (fromRadio.hasMyInfo()) myNodeNum = fromRadio.myInfo.myNodeNum
    }

    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = lifecycleScope.launch(Dispatchers.IO) {
            while (isActive && isConnected) {
                delay(10_000L)
                if (!isConnected) break
                try {
                    val toRadio = MeshProtos.ToRadio.newBuilder()
                        .setHeartbeat(MeshProtos.Heartbeat.newBuilder().setNonce((System.currentTimeMillis() % 0xFFFF).toInt()).build())
                        .build()
                    sendToRadio(toRadio)
                    Log.d(TAG, "Heartbeat sent")
                } catch (_: Exception) {}
            }
        }
    }

    private fun disconnect() { disconnectInternal(true) }

    private fun disconnectInternal(keepLog: Boolean) {
        heartbeatJob?.cancel()
        heartbeatJob = null
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
        if (isDestroyed) return
        val t = System.currentTimeMillis() % 100000
        logText = "[$t] $message\n$logText".take(MAX_LOG_CHARS)
        Log.d(TAG, message)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TechoScreen(
    statusText: String,
    logText: String,
    isConnected: Boolean,
    myNodeNum: Int?,
    people: List<String>,
    selectedPersonIndex: Int,
    onPersonSelect: (Int) -> Unit,
    healthInput: String,
    onHealthInputChange: (String) -> Unit,
    lastAiLevel: String,
    isModelLoading: Boolean,
    isModelReady: Boolean,
    isSending: Boolean,
    onClassifyAndSend: () -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    showAlertDialog: Boolean,
    alertDialogMessage: String,
    onDismissAlert: () -> Unit
) {
    var personDropdownExpanded by remember { mutableStateOf(false) }
    if (showAlertDialog) {
        AlertDialog(
            onDismissRequest = onDismissAlert,
            title = { Text("Risk alert", color = MaterialTheme.colorScheme.error) },
            text = { Text(alertDialogMessage) },
            confirmButton = { Button(onClick = onDismissAlert) { Text("OK") } }
        )
    }
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("Health → Mesh", style = MaterialTheme.typography.headlineSmall)
                    myNodeNum?.let { Text("Node: 0x${it.toString(16)}", style = MaterialTheme.typography.bodySmall) }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onConnect, enabled = !isConnected) { Text("Connect") }
                    Button(onClick = onDisconnect, enabled = isConnected, colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) { Text("Disconnect") }
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(statusText, style = MaterialTheme.typography.bodyMedium)
            Spacer(modifier = Modifier.height(16.dp))
            if (isModelLoading) {
                Text("Loading AI model...", style = MaterialTheme.typography.bodyMedium)
            } else if (!isModelReady) {
                Text("AI model failed", color = MaterialTheme.colorScheme.error)
            } else {
                Text("Person", style = MaterialTheme.typography.labelMedium)
                Spacer(modifier = Modifier.height(4.dp))
                ExposedDropdownMenuBox(
                    expanded = personDropdownExpanded,
                    onExpandedChange = { personDropdownExpanded = it }
                ) {
                    OutlinedTextField(
                        value = people.getOrNull(selectedPersonIndex) ?: "",
                        onValueChange = {},
                        readOnly = true,
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = personDropdownExpanded) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor()
                    )
                    ExposedDropdownMenu(
                        expanded = personDropdownExpanded,
                        onDismissRequest = { personDropdownExpanded = false }
                    ) {
                        people.forEachIndexed { index, name ->
                            DropdownMenuItem(
                                text = { Text(name) },
                                onClick = {
                                    onPersonSelect(index)
                                    personDropdownExpanded = false
                                }
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = healthInput,
                    onValueChange = onHealthInputChange,
                    label = { Text("Health parameters") },
                    placeholder = { Text("e.g. HR average 65 bpm HR max 85 SpO2 98 percent steps 2000 active 5 minutes sleep 7h") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = false,
                    minLines = 2
                )
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = onClassifyAndSend,
                    enabled = isConnected && healthInput.isNotBlank() && !isSending,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (isSending) "Classifying & sending…" else "Classify & send to mesh")
                }
                if (lastAiLevel.isNotBlank()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Last classification:", style = MaterialTheme.typography.labelMedium)
                    Text(lastAiLevel, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 4.dp))
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text("Log", style = MaterialTheme.typography.labelMedium)
            Surface(modifier = Modifier.fillMaxWidth().weight(1f), color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.small) {
                Text(logText, modifier = Modifier.padding(10.dp).verticalScroll(rememberScrollState()), fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
