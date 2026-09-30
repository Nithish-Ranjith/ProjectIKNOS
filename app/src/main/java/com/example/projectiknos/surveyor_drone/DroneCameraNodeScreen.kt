package com.example.projectiknos.surveyor_drone

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.FiberManualRecord
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.projectiknos.api.RetrofitClient
import com.example.projectiknos.ui.camera.CameraPreview
import com.example.projectiknos.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DroneCameraNodeScreen(
    missionId: String,
    onMissionComplete: (String) -> Unit,
    onAbort: () -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Captured photos log
    val capturedPhotos = remember { mutableStateListOf<String>() }

    // External capture signal: increments trigger a headless capture
    var externalCaptureSignal by remember { mutableIntStateOf(0) }
    var missionStatus by remember { mutableStateOf("STANDBY") }
    var pollActive by remember { mutableStateOf(false) }

    // Live location state
    var latStr by remember { mutableStateOf("Acquiring...") }
    var lonStr by remember { mutableStateOf("Acquiring...") }

    // Location permission
    var hasLocationPerm by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
                    PackageManager.PERMISSION_GRANTED
        )
    }
    val locationPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { hasLocationPerm = it }

    // Start polling backend for capture commands
    LaunchedEffect(pollActive) {
        if (!pollActive) return@LaunchedEffect
        while (true) {
            delay(2000)
            try {
                val resp = RetrofitClient.instance.pollCaptureCommand()
                if (resp.active) {
                    externalCaptureSignal++
                    missionStatus = "CAPTURING"
                }
            } catch (_: Exception) { /* no-op */ }
        }
    }

    // Live GPS updates
    @SuppressLint("MissingPermission")
    fun startGps() {
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            val provider = if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER))
                LocationManager.GPS_PROVIDER else LocationManager.NETWORK_PROVIDER
            lm.requestLocationUpdates(provider, 1000L, 0.5f) { loc ->
                latStr = String.format(Locale.US, "%.6f", loc.latitude)
                lonStr = String.format(Locale.US, "%.6f", loc.longitude)
            }
        } catch (_: Exception) {}
    }

    LaunchedEffect(hasLocationPerm) {
        if (hasLocationPerm) startGps()
        else locationPermLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
    }

    // Blinking REC indicator
    val infiniteTransition = rememberInfiniteTransition(label = "rec")
    val recAlpha by infiniteTransition.animateFloat(
        initialValue = 1f, targetValue = 0.2f,
        animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
        label = "recAlpha"
    )
    val statusColor by animateColorAsState(
        when (missionStatus) {
            "CAPTURING" -> Color(0xFF22C55E)
            "STANDBY" -> Color(0xFFFBBF24)
            else -> Color(0xFFEF4444)
        }, label = "statusColor"
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Drone Camera Node", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                        Text("Mission: $missionId", fontSize = 11.sp, color = TextSecondary, fontFamily = FontFamily.Monospace)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back", tint = TextPrimary) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PanelColor),
                actions = {
                    // REC indicator
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(end = 16.dp)) {
                        Icon(
                            Icons.Default.FiberManualRecord, null,
                            tint = statusColor.copy(alpha = if (pollActive) recAlpha else 0.4f),
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(missionStatus, color = statusColor, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    }
                }
            )
        },
        containerColor = BgColor
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {

            // ── Live Camera Preview (fills most of the screen) ────────────────
            CameraPreview(
                modifier = Modifier.fillMaxWidth().weight(1f),
                showCaptureButton = true,
                externalCaptureSignal = externalCaptureSignal,
                onPhotoCaptured = { file ->
                    val label = "seq${capturedPhotos.size + 1} • ${
                        SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
                    } • ${file.length() / 1024}KB"
                    capturedPhotos.add(0, label)
                    if (capturedPhotos.size > 20) capturedPhotos.removeLast()
                    missionStatus = if (pollActive) "CAPTURING" else "STANDBY"
                    // Upload to backend
                    scope.launch {
                        try {
                            val token = RetrofitClient.authToken ?: return@launch
                            val intent = Intent(context, CameraSchedulerService::class.java).apply {
                                action = CameraSchedulerService.ACTION_START_MISSION
                                putExtra(CameraSchedulerService.EXTRA_MISSION_ID, missionId)
                                putExtra(CameraSchedulerService.EXTRA_AUTH_TOKEN, token)
                            }
                            // Service handles upload; individual manual captures we upload inline
                        } catch (_: Exception) {}
                    }
                },
                overlayContent = {
                    // GPS Overlay
                    Surface(
                        color = Color(0xAA000000),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.align(Alignment.TopStart).padding(12.dp)
                    ) {
                        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                            Text("📍 GPS", color = AccentSage, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            Text("Lat: $latStr", color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            Text("Lon: $lonStr", color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                        }
                    }

                    // Photo count badge
                    Surface(
                        color = Color(0xAA000000),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.align(Alignment.TopEnd).padding(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.PhotoCamera, null, tint = Color.White, modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("${capturedPhotos.size} captured", color = Color.White, fontSize = 12.sp)
                        }
                    }
                }
            )

            // ── Captured log ──────────────────────────────────────────────────
            if (capturedPhotos.isNotEmpty()) {
                Surface(color = PanelColor) {
                    LazyColumn(
                        modifier = Modifier.fillMaxWidth().heightIn(max = 120.dp).padding(horizontal = 16.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(2.dp)
                    ) {
                        items(capturedPhotos.take(5)) { entry ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.CheckCircle, null, tint = AccentSage, modifier = Modifier.size(12.dp))
                                Spacer(Modifier.width(6.dp))
                                Text(entry, color = TextSecondary, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                            }
                        }
                    }
                }
            }

            // ── Control panel ─────────────────────────────────────────────────
            Column(
                modifier = Modifier.fillMaxWidth().background(PanelColor).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Auto-capture toggle
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text("Auto-Capture (Field Commander signal)", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                        Text("Polls server every 2s for capture commands", color = TextSecondary, fontSize = 11.sp)
                    }
                    Switch(
                        checked = pollActive,
                        onCheckedChange = {
                            pollActive = it
                            missionStatus = if (it) "STANDBY" else "OFFLINE"
                        },
                        colors = SwitchDefaults.colors(checkedThumbColor = AccentSage, checkedTrackColor = AccentSage.copy(alpha = 0.4f))
                    )
                }

                Button(
                    onClick = { onAbort() },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AccentRust),
                    shape = RoundedCornerShape(8.dp)
                ) { Text("Abort Mission", fontSize = 15.sp, fontWeight = FontWeight.Bold) }
            }
        }
    }
}
